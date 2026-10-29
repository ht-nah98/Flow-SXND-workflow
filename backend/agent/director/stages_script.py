"""Director stages that write the film: brief, story, shot list, prompts, the editor's review. Split from pipeline.py on 23/10 (code moved, not changed)."""
import re
from pathlib import Path


from agent.db import crud
from agent.director import lint, styles, targeted, venues
from agent.director.schemas import (BriefAnalysis, EditorReport, ShotList, ShotPrompts,
                                    Story)
from agent.director.stage_common import STAGES, StageFailed, _models, agent_on, think_with_lint

EDITOR_PASS_SCORE = 75
MAX_EDIT_LOOPS = 2


_ASKS_VOICE = re.compile(r"lồng tiếng|giọng (?:đọc|kể)|người kể|lời kể|thuyết minh|voice[- ]?over|narrat|lời thoại|đọc lời", re.I)


def _plain_brief(b: dict) -> BriefAnalysis:
    """The brief without the producer: the idea node's own choices, no AI call."""
    text = re.sub(r"\s+", " ", b.get("text", "")).strip()
    return BriefAnalysis(logline=text[:300], genre="", tone="", target_s=b.get("target_s", 60),
                         orientation=b.get("orientation", "HORIZONTAL"), material=b.get("style") or "realistic",
                         voice="voiceover" if _ASKS_VOICE.search(text) else "none")


async def h_brief(run):
    b = run["brief"]
    images = b.get("images") or []
    kw = {"tools": ["Read"], "add_dirs": sorted({str(Path(i["file"]).parent) for i in images})} if images else {}
    # The producer is the one who reads the user's pictures, so it still runs when the idea has any.
    if agent_on(run, "producer") or images:
        out = await think_with_lint(run, "BRIEF", "producer", {"brief": b}, BriefAnalysis, **kw)
    else:
        out = _plain_brief(b)
    # The user's own choices win over the producer's reading of the idea.
    given = {i["file"] for i in images}
    out = out.model_copy(update={
        "target_s": b.get("target_s", out.target_s), "orientation": b.get("orientation", out.orientation),
        "material": b.get("style") or out.material,
        "images": [i for i in out.images if i.file in given]})
    out = out.model_copy(update={"language": b.get("language") or "en",   # directive B4: English unless asked
                                 "creativity": b.get("creativity") or "balanced",
                                 "film_mode": b.get("film_mode") or "cut",
                                 "style_pack": b.get("style_pack") if styles.get(b.get("style_pack")) else None})
    if out.film_mode == "ambient":            # B14: no story, no voice; the reel is what gets written and looped
        out = out.model_copy(update={"venue": b.get("venue"), "reel_s": b.get("reel_s"), "loop_s": b.get("loop_s"),
                                     "target_s": b.get("reel_s") or out.target_s, "voice": "none", "voice_style": None})
        run["plan"]["brief"] = out.model_dump()
        return "STORY"
    voice = b.get("voice") or "auto"
    if voice == "auto" and out.voice == "none" and _ASKS_VOICE.search(b.get("text", "")):
        voice = "voiceover"                       # the idea names a voice: never drop it
    if voice != "auto":                           # the user's choice on the idea node wins
        out = out.model_copy(update={"voice": voice})
    if out.voice != "none" and not out.voice_style:
        out = out.model_copy(update={"voice_style": "a young female voice, clear, warm, medium pace"
                                     if out.language == "en" else "giọng nữ trẻ, trong, ấm, rõ ràng, tốc độ vừa"})
    run["plan"]["brief"] = out.model_dump()
    return "STORY"


AMBIENT_STORY = ("Ambient mode (directive B14, playbook 11): there is NO story. Write only the venue sheet: exactly one "
                 "location (the venue DURING the live performance, from `venue` and the user's idea, its seats full "
                 "of an anonymous audience with phone lights — never an empty venue), at most two "
                 "visual_asset details (stage, an instrument), no characters, one sequence and one beat. story_line, "
                 "message, viewer_value, hooks and source_map stay empty. synopsis and director_notes are Vietnamese: "
                 "what the reel shows and its one look.")


async def _ambient_story(run):
    brief = run["plan"]["brief"]
    venue = venues.get(brief.get("venue"))
    payload = {"idea": run["brief"].get("text", ""), "brief": brief, "venue": venue.__dict__ if venue else None,
               "task": AMBIENT_STORY}
    out = await think_with_lint(run, "STORY", "writer", payload, Story, lint.lint_story_ambient)
    run["plan"]["story"] = out.model_dump()
    return "SHOTLIST"


async def h_story(run):
    if run["plan"]["brief"].get("film_mode") == "ambient":
        return await _ambient_story(run)
    # Names that already have reference images must survive a rewrite, or each
    # rename becomes a new entity with a new (paid) ref image.
    ids = run["plan"].get("ids") or {}
    # Assets the user put on the project (e.g. dragged from the library) that already have a picture:
    # the writer casts them by name and ingest reuses them, so no new image is paid for.
    existing = []
    if ids.get("project_id"):
        for c in await crud.get_project_characters(ids["project_id"]):
            if c.get("media_id") and c["name"] not in ids.setdefault("entities", {}):
                ids["entities"][c["name"]] = c["id"]
            if c.get("media_id"):
                existing.append({"name": c["name"], "entity_type": c.get("entity_type"),
                                 "description": c.get("description") or ""})
    locked = sorted(ids.get("entities", {}))
    idea = run["brief"].get("text", "")   # the user's own words, in full: the brief is only a reading of them
    payload = {"idea": idea, "brief": run["plan"]["brief"], "locked_cast": locked, "existing_assets": existing}
    rev, prev = run["plan"].get("revise"), run["plan"].get("story")
    if rev is not None and prev:              # targeted revision: fix what the notes say, copy the rest
        payload |= {"previous_story": prev, "task": REVISE_STORY}
    out = await think_with_lint(run, "STORY", "writer", payload, Story,
                                lambda st: lint.lint_story(st, idea, run["plan"]["brief"].get("target_s")))
    if rev is not None and prev:
        changed = targeted.story_changes(Story.model_validate(prev), out)
        rev["story"] = None if changed is None else {"beats": sorted(changed[0]), "cast": sorted(changed[1])}
    usable = {i["file"] for i in run["plan"]["brief"].get("images", []) if i["use"] != "mood"}
    out.cast = [c.model_copy(update={"provided_image": c.provided_image if c.provided_image in usable else None})
                for c in out.cast]
    run["plan"]["story"] = out.model_dump()
    return "SHOTLIST"


REVISE_STORY = ("Revise previous_story: change only what revision_notes ask. Copy every other beat, cast member and "
                "field unchanged, with the same ids, so the shots already planned for them stay valid.")


def _revision_beats(run, old: ShotList) -> set[str] | None:
    """Beats whose shots a targeted revision re-plans; None = re-plan the whole shotlist."""
    rev = run["plan"].get("revise")
    if rev is None or "SHOTLIST" in rev["film_wide"] or rev.get("story", {}) is None:
        return None
    named = set(rev["shots"].get("SHOTLIST", []))
    return set((rev.get("story") or {}).get("beats", [])) | {s.beat_id for s in old.shots if s.id in named}


async def h_shotlist(run):
    story = Story.model_validate(run["plan"]["story"])
    target = run["plan"]["brief"]["target_s"]
    base = {"idea": run["brief"].get("text", ""), "brief": run["plan"]["brief"], "story": run["plan"]["story"]}
    brief = run["plan"]["brief"]
    check = lambda sl: lint.lint_shotlist(sl, story, target, brief.get("language", "en"),  # noqa: E731
                                          brief.get("film_mode", "cut"))
    old = ShotList.model_validate(run["plan"]["shotlist"]) if run["plan"].get("shotlist") else None
    beats = _revision_beats(run, old) if old else None
    out = None
    if beats is not None:
        touched: set[str] = set()

        def fold(part: ShotList) -> ShotList:
            merged, ids = targeted.merge_shots(old, part.shots, beats, story)
            touched.clear(); touched.update(ids)
            return merged
        if not beats:
            out = old                         # the story change did not reach any shot
        else:
            sub = old.model_copy(update={"shots": [s for s in old.shots if s.beat_id in beats]})
            ask = base | {"previous_shots": sub.model_dump()["shots"], "task":
                          f"Re-plan ONLY the shots of beats {sorted(beats)}: return just those shots (the rest of the "
                          "film is kept). Fix what revision_notes say about them."}
            try:
                out = await think_with_lint(run, "SHOTLIST", "director", ask, ShotList, check, merge=fold)
            except StageFailed:
                out = None                    # a targeted answer that cannot pass lint: re-plan the whole film
        if out is not None:
            run["plan"]["revise"]["touched"] = sorted(touched)
    if out is None:
        out = await think_with_lint(run, "SHOTLIST", "director", base, ShotList, check)
        if run["plan"].get("revise") is not None:
            run["plan"]["revise"]["touched"] = None
    pack = styles.get(run["plan"]["brief"].get("style_pack"))
    if pack:                                  # the pack decides the edit grade too
        out = out.model_copy(update={"film_look": pack.film_look})
    run["plan"]["shotlist"] = out.model_dump()
    return "PROMPTS"


def _dp_shots(shots: ShotList, sub: ShotList | None = None) -> dict:
    """The shotlist as the DP reads it: each shot also carries `ends_on`, the bridge the NEXT shot opens on, so the
    shot before a time cut knows what to settle on (20/10: the DP could not fix a bridge it was never shown)."""
    nxt = {s.order - 1: s.bridge for s in shots.shots if s.bridge}
    # Continuous mode: a continuing shot carries the contract it opens on, so a repair of one prompt still sees it.
    final = {s.order + 1: s.final_frame for s in shots.shots if s.final_frame}
    out = (sub or shots).model_dump()
    for d in out["shots"]:
        if (b := nxt.get(d["order"])):
            d["ends_on"] = {"element": b.element, "how": b.outgoing}
        if d.get("continues") and final.get(d["order"]):
            d["opens_on"] = final[d["order"]]
    return out


async def h_prompts(run):
    story, shots = _models(run["plan"])
    base = {"brief": run["plan"]["brief"], "story": run["plan"]["story"], "shotlist": _dp_shots(shots)}
    pack = styles.get(run["plan"]["brief"].get("style_pack"))
    marker = pack.marker if pack else None
    mode = run["plan"]["brief"].get("film_mode", "cut")

    def repair(prev: ShotPrompts, issues):
        """Bước 7 (19/10): rewrite only the prompts the lint rejected; the good ones are kept as they are."""
        bad = {i.shot_id for i in lint.errors(issues)}
        if None in bad or len(bad) * 2 > len(shots.shots):     # a film-wide problem: redo everything
            return None
        sub = shots.model_copy(update={"shots": [s for s in shots.shots if s.id in bad]})

        def merge(fixed: ShotPrompts) -> ShotPrompts:
            new = {p.shot_id: p for p in fixed.prompts if p.shot_id in bad}
            return prev.model_copy(update={"prompts": [new.get(p.shot_id, p) for p in prev.prompts],
                                           "style_block": fixed.style_block or prev.style_block,
                                           "avoid_block": fixed.avoid_block or prev.avoid_block})
        return dict(base, shotlist=_dp_shots(shots, sub),
                    task="Rewrite ONLY the prompts of the shots in this shotlist; fix exactly the lint_errors."), merge

    check = lambda p: lint.lint_prompts(p, shots, story, marker, mode)  # noqa: E731
    redo = _revision_prompts(run, shots)
    if redo is not None and not redo:
        out = ShotPrompts.model_validate(run["plan"]["prompts"])   # nothing this revision touched needs new words
    elif redo is not None:
        old = ShotPrompts.model_validate(run["plan"]["prompts"])
        sub = shots.model_copy(update={"shots": [s for s in shots.shots if s.id in redo]})
        ask = dict(base, shotlist=_dp_shots(shots, sub),
                   task="Rewrite ONLY the prompts of the shots in this shotlist; fix what revision_notes say about them.")
        out = await think_with_lint(run, "PROMPTS", "dp", ask, ShotPrompts, check, repair=repair,
                                    merge=lambda part: targeted.merge_prompts(old, part, shots, redo))
    else:
        out = await think_with_lint(run, "PROMPTS", "dp", base, ShotPrompts, check, repair=repair)
    if mode in ("continuous", "ambient"):
        out = lint.assemble(out)   # the film's one style block and Avoid list, word for word in every prompt
    run["plan"]["prompts"] = out.model_dump()
    return "EDIT_REVIEW"


def _revision_prompts(run, shots: ShotList) -> set[str] | None:
    """Shots whose prompt a targeted revision rewrites; None = rewrite every prompt."""
    rev = run["plan"].get("revise")
    if rev is None or not run["plan"].get("prompts") or "PROMPTS" in rev["film_wide"] or rev.get("touched", []) is None:
        return None
    if rev.get("story", {}) is None:
        return None
    cast = set((rev.get("story") or {}).get("cast", []))
    ids = set(rev.get("touched", [])) | set(rev["shots"].get("PROMPTS", []))
    ids |= {s.id for s in shots.shots if cast & set(s.cast)}
    order = {s.order: s for s in shots.shots}
    for s in shots.shots:              # a bridged cut lives in two prompts: the shot before must end on the element
        if s.id in ids and s.bridge and (before := order.get(s.order - 1)):
            ids.add(before.id)
    have = {p["shot_id"] for p in run["plan"]["prompts"]["prompts"]}
    ids |= {s.id for s in shots.shots if s.id not in have}   # a shot with no prompt yet
    return {i for i in ids if i in {s.id for s in shots.shots}}


async def h_edit_review(run):
    plan = run["plan"]
    if not agent_on(run, "editor"):
        plan["editor"] = {"skipped": True}
        return "INGEST"
    rep = await think_with_lint(run, "EDIT_REVIEW", "editor",
                                {k: plan[k] for k in ("brief", "story", "shotlist", "prompts")}
                                | {"idea": run["brief"].get("text", ""), "warnings": plan.get("warnings", [])},
                                EditorReport)
    plan["editor"] = rep.model_dump()
    loops = plan.get("edit_loops", 0)
    plan.pop("revise", None)                  # the previous revision is done
    if rep.score >= EDITOR_PASS_SCORE or not rep.fixes:
        return "INGEST"
    if loops >= MAX_EDIT_LOOPS:
        plan.setdefault("warnings", []).append(f"editor score {rep.score} after {loops} revisions")
        return "INGEST"
    plan["edit_loops"] = loops + 1
    plan["revise"] = targeted.plan_revision(rep.fixes)
    plan.setdefault("revision_notes", []).extend(
        f"[{f.target_stage}{' ' + f.shot_id if f.shot_id else ''}] {f.issue}" for f in rep.fixes)
    return min((f.target_stage for f in rep.fixes), key=STAGES.index)
