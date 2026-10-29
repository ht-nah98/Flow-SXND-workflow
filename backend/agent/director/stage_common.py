"""What every director stage shares: the gate/failure signals, the lint-checked AI call, run helpers. Split from pipeline.py on 23/10 (code moved, not changed)."""
import time
from collections.abc import Callable

from pydantic import BaseModel

from agent.director import brain
from agent.director import budget as budget_mod
from agent.director import lessons, lint, production, store, styles
from agent.director.schemas import (ShotList, Story)

# v2 (spec 2026-10-15-ai-director-v2): r2v only, the user reads the script before any credit is spent.
STAGES = ["BRIEF", "STORY", "SHOTLIST", "PROMPTS", "EDIT_REVIEW", "INGEST", "REFS", "KEYFRAMES", "VIDEOS", "QC", "CUT",
          "PUBLISH", "RETRO", "DONE"]
MAX_LINT_ATTEMPTS = 3


class Gate(Exception):
    def __init__(self, gate: str, payload: dict | None = None):
        super().__init__(gate)
        self.gate, self.payload = gate, payload or {}


class StageFailed(Exception):
    pass


# Roles that read playbook 09 in a continuous film (reshoot keeps the cut rules: it only rewrites one failed clip).
CONTINUOUS_ROLES = {"writer", "director", "dp", "reshoot", "editor", "qc", "reviewer"}


async def think_with_lint(run: dict, stage: str, role: str, payload: dict, schema: type[BaseModel],
                          lint_fn: Callable[[BaseModel], list[lint.LintIssue]] | None = None,
                          repair: Callable | None = None, merge: Callable | None = None, **brain_kw) -> BaseModel:
    """Ask, lint, and retry with the lint errors. `repair(prev, issues)` may return (payload, merge) so that a retry
    rewrites only the broken parts (e.g. 3 bad prompts out of 44) instead of the whole answer. `merge(answer)` folds a
    partial answer (a targeted revision) into the full one before it is linted."""
    payload = dict(payload, revision_notes=run["plan"].get("revision_notes", []))
    pack = styles.as_payload((run["plan"].get("brief") or {}).get("style_pack"))
    if pack:                                  # one look for the whole film: every role sees the same pack
        payload["style_pack"] = pack
    payload["_context"] = await lessons.context_for(role)
    mode = (run["plan"].get("brief") or {}).get("film_mode")
    if mode == "continuous" and role in CONTINUOUS_ROLES:
        payload["_context"] = brain.continuous_playbook() + "\n\n" + payload["_context"]
    elif mode == "keyframe" and role in CONTINUOUS_ROLES:      # the same roles read the mode's playbook (B13)
        payload["_context"] = brain.keyframe_playbook() + "\n\n" + payload["_context"]
    elif mode == "ambient" and role in CONTINUOUS_ROLES:       # B14: no story — every role reads playbook 11
        payload["_context"] = brain.ambient_playbook() + "\n\n" + payload["_context"]
    last: list[lint.LintIssue] = []
    prev: BaseModel | None = None
    for attempt in range(1, MAX_LINT_ATTEMPTS + 1):
        if last:
            payload["lint_errors"] = [f"{i.rule} [{i.shot_id}]: {i.message}" for i in lint.errors(last)]
        fix = repair(prev, last) if repair and prev is not None and last else None
        ask, combine = (dict(fix[0], revision_notes=payload["revision_notes"], _context=payload["_context"],
                             lint_errors=payload["lint_errors"]), fix[1]) if fix else (payload, merge)
        t0 = time.monotonic()
        try:
            # A cheaper role model gets one try; a lint-rejected answer is redone by the strong model. A small
            # targeted repair stays on the role's model once before escalating.
            strong = attempt > 2 if fix else attempt > 1
            out = await brain.think(role, ask, schema, escalate=strong, **brain_kw)
            if combine:
                out = combine(out)
        except brain.BrainError as e:
            await store.add_step(run["id"], stage, attempt, _public(payload), None, [], "FAILED",
                                 int((time.monotonic() - t0) * 1000))
            raise StageFailed(str(e)) from e
        issues = lint_fn(out) if lint_fn else []
        ok = not lint.errors(issues)
        await store.add_step(run["id"], stage, attempt, _public(ask), out.model_dump(),
                             [i.__dict__ for i in issues], "OK" if ok else "LINT_FAILED",
                             int((time.monotonic() - t0) * 1000))
        prev = out
        if ok:
            warn = [f"{i.rule}: {i.message}" for i in issues]
            if warn:
                ws = run["plan"].setdefault("warnings", [])
                ws.extend(w for w in warn if w not in ws)
            return out
        last = issues
    raise StageFailed("; ".join(f"{i.rule} [{i.shot_id}]: {i.message}" for i in lint.errors(last)))


def _public(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if k != "_context"}


def _models(plan: dict):
    return (Story.model_validate(plan["story"]), ShotList.model_validate(plan["shotlist"]))


def agent_on(run, role: str) -> bool:
    """Directive A5: the user can turn the optional roles (producer, editor, qc, coach) off per film."""
    return (run["brief"].get("agents") or {}).get(role, True)


def _ask(run, gate: str, budget: dict, payload: dict) -> Gate:
    """Remember what approving this gate grants, so the canvas can approve without re-deriving it."""
    run["plan"].setdefault("gate_budget", {})[gate] = budget
    return Gate(gate, payload)


def _keyframe_mode(run) -> bool:
    return (run["plan"].get("brief") or {}).get("film_mode") == "keyframe"


def _keyframe_budget(run) -> dict:
    """Keyframe mode: one still per shot (playbook 10 §5), granted with the videos."""
    return {"images": len(run["plan"]["shotlist"]["shots"])} if _keyframe_mode(run) else {}


def _shot_ctx(run):
    plan = run["plan"]
    return plan["ids"], plan["brief"]["orientation"], ShotList.model_validate(plan["shotlist"]).shots


async def _gen(run, key, kind, **kw) -> str:
    try:
        return await production.request_for(run, key, kind, **kw)
    except budget_mod.BudgetExceeded as e:
        raise Gate("BUDGET_EXCEEDED", {"kind": e.kind}) from e
