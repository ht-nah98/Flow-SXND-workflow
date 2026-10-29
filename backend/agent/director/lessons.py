"""Continuous learning (spec §9): seed rules, retro lessons, pass-rate stats, prompt context."""
from collections import defaultdict

from agent.director import store
from agent.director.schemas import Retro

ACTIVATE_AFTER = 2
ALL_SCOPES = ["story", "shotlist", "prompt", "omni_flash", "edit"]
ROLE_SCOPES = {"writer": ["story"], "director": ["shotlist", "omni_flash"], "dp": ["prompt", "omni_flash"],
               "editor": ALL_SCOPES, "qc": ["omni_flash", "edit"], "coach": ALL_SCOPES}

SEED_LESSONS = [
    {"id": "seed-actions", "scope": "omni_flash",
     "rule": "A clip of up to 10s holds at most 2 actions (a 4s clip holds 1). More actions break the video."},
    {"id": "seed-transition", "scope": "omni_flash",
     "rule": "At most 1 transition per clip, and only after 2–3s of stable framing "
             "(e.g. close on a coffee cup, hold, then pull back to the whole room)."},
    {"id": "seed-one-idea", "scope": "shotlist",
     "rule": "One main idea per clip. Prefer many short clips cut together over one clip doing everything."},
    {"id": "seed-one-move", "scope": "prompt",
     "rule": "One primary camera job per shot; action timeline and camera timeline are written separately."},
    {"id": "seed-end-frame", "scope": "prompt",
     "rule": "Design the end frame first and hold it 0.3–0.8s; it is where the next cut lands."},
    {"id": "seed-trim", "scope": "edit",
     "rule": "Trim the settle at the head and any drift at the tail; keep the cleanest stretch of each clip."},
]


async def ensure_seed() -> None:
    for s in SEED_LESSONS:
        if not await store.get_lesson(s["id"]):
            await store.add_lesson(s["scope"], s["rule"], "seed", "ACTIVE", id=s["id"])


def _bump(table, key, passed):
    table[key][0] += int(passed)
    table[key][1] += 1


def compute_stats(runs: list[dict]) -> dict:
    st = {k: defaultdict(lambda: [0, 0]) for k in ("mode", "duration", "command", "transition")}
    for r in runs:
        plan = r.get("plan") or {}
        qc = plan.get("qc") or {}
        for s in (plan.get("shotlist") or {}).get("shots", []):
            if not isinstance(s, dict) or s.get("id") is None:
                continue
            v = (qc.get(s["id"]) or {}).get("verdict")
            if v not in ("PASS", "FAIL"):
                continue
            ok = v == "PASS"
            if s.get("mode") is not None:
                _bump(st["mode"], s["mode"], ok)
            if s.get("duration_s") is not None:
                _bump(st["duration"], str(s["duration_s"]), ok)
            for c in s.get("commands") or []:
                _bump(st["command"], str(c).lstrip("/"), ok)
            technique = (s.get("transition") or {}).get("technique") if isinstance(s.get("transition"), dict) else None
            if technique:
                _bump(st["transition"], technique.lstrip("/"), ok)
    return {k: dict(v) for k, v in st.items()}


async def context_for(role: str) -> str:
    rules = await store.list_lessons(status="ACTIVE", scopes=ROLE_SCOPES.get(role, ALL_SCOPES))
    lines = ["## Lessons learned (apply them)"] + [f"- [{l['scope']}] {l['rule']}" for l in rules]
    stats = compute_stats(await store.list_runs())
    risky = [f"- {kind} {key}: PASS {p}/{t}" for kind, tbl in stats.items()
             for key, (p, t) in sorted(tbl.items()) if t >= 2]
    if risky:
        lines += ["", "## Past QC pass rates (prefer what works)"] + risky
    return "\n".join(lines)


def _merge_evidence(existing: list[dict], new: list[dict]) -> list[dict]:
    """Append new items, skipping any (run_id, shot_id, issue) already present."""
    seen = {(e.get("run_id"), e.get("shot_id"), e.get("issue")) for e in existing}
    merged = list(existing)
    for e in new:
        key = (e.get("run_id"), e.get("shot_id"), e.get("issue"))
        if key not in seen:
            seen.add(key)
            merged.append(e)
    return merged


async def apply_retro(retro: Retro, run_id: str, source: str = "retro") -> list[dict]:
    out = []
    for d in retro.lessons:
        ev = [dict(e, run_id=run_id) for e in d.evidence]
        if d.existing_id:
            cur = await store.get_lesson(d.existing_id)
            if not cur:
                continue
            evidence = _merge_evidence(cur["evidence"], ev)
            status = cur["status"]
            if status == "PROPOSED" and (source == "user" or len(evidence) >= ACTIVATE_AFTER):
                status = "ACTIVE"
            out.append(await store.update_lesson(cur["id"], evidence=evidence, status=status))
            continue
        if not d.rule.strip():
            continue
        ev = _merge_evidence([], ev)
        status = "ACTIVE" if source == "user" or len(ev) >= ACTIVATE_AFTER else "PROPOSED"
        out.append(await store.add_lesson(d.scope, d.rule, source, status, evidence=ev))
    return out


# Agent Review (film_review.py) writes a rule for the next film with each finding; until 22/10 none was kept, so the
# next film could not learn from the review (Old Walt: 3 rules lost). Layer → the roles that must read it.
REVIEW_SCOPE = {"story": "story", "continuity": "omni_flash", "clips": "prompt", "edit": "edit"}


async def learn_from_film_review(findings: list[dict], run_id: str) -> list[dict]:
    """Keep each finding's rule as a lesson: ACTIVE at once for a CRITICAL/HIGH fault seen in a real film, PROPOSED for
    a minor one (it activates when a second film shows it). The same rule text is stored once, with all its evidence."""
    out = []
    known = {l["rule"].strip().lower(): l for l in await store.list_lessons()}
    for f in findings:
        rule = (f.get("rule") or "").strip()
        if not rule:
            continue
        ev = [{"run_id": run_id, "shot_id": f.get("shot_id"), "issue": f.get("title")}]
        major = f.get("severity") in ("CRITICAL", "HIGH")
        cur = known.get(rule.lower())
        if cur:
            evidence = _merge_evidence(cur["evidence"], ev)
            status = "ACTIVE" if major or len(evidence) >= ACTIVATE_AFTER else cur["status"]
            out.append(await store.update_lesson(cur["id"], evidence=evidence, status=status))
            continue
        row = await store.add_lesson(REVIEW_SCOPE.get(f.get("layer"), "prompt"), rule, "film_review",
                                     "ACTIVE" if major else "PROPOSED", evidence=ev)
        known[rule.lower()] = row
        out.append(row)
    return out
