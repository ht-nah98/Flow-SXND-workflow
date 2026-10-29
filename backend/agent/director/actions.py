"""What the user does to a run from the canvas: approve a gate, revise, rewrite a clip, re-cut. Split from pipeline.py on 23/10 (code moved, not changed)."""
from typing import Literal


from agent.db import account_crud, crud
from agent.director import brain
from agent.director import budget as budget_mod
from agent.director import lessons, lint, store, targeted
from agent.director.schemas import (EditorReport, Retro, ShotList, ShotPrompt, ShotPrompts)
from agent.services.event_bus import event_bus
from agent.director.stage_common import STAGES, _keyframe_budget, _keyframe_mode, _models, _shot_ctx, think_with_lint
from agent.director.stages_media import _check_refs, _missing_keyframes, _refs_needed
from agent.director.stages_film import h_cut, h_publish

AFTER_GATE = {"SCRIPT": "REFS", "ASSETS": "VIDEOS", "KEYFRAMES": "VIDEOS"}   # ASSETS → KEYFRAMES in keyframe mode


async def approve(rid: str, gate: str, budget: dict | None = None,
                  mode: Literal["step", "auto"] = "step") -> dict:
    """`mode="auto"` at the SCRIPT gate grants the whole film's credit at once: references, videos and
    regens, and the run goes on past the ASSETS gate by itself (it still stops there if a reference fails)."""
    run = await store.get_run(rid)
    if run["status"] != "WAITING_GATE" or run["gate"] != gate:
        raise ValueError(f"run is not waiting at gate {gate}")
    budget = budget if budget is not None else (run["plan"].get("gate_budget") or {}).get(gate)
    if gate == "ASSETS":
        await _check_refs(run)
    if gate == "KEYFRAMES" and (missing := await _missing_keyframes(run)):
        raise ValueError(f"cảnh {', '.join(map(str, missing))} chưa có ảnh keyframe")
    if gate == "ACCOUNT_EXHAUSTED":   # the user says the account has credit again (new day / topped up): retry there
        account = (run["plan"].get("gate_payload") or {}).get("account")
        if account:
            await account_crud.reactivate(account)
    kw = {"status": "RUNNING", "gate": None, "error": None}
    if gate == "SCRIPT":
        run["plan"]["mode"] = mode
        if mode == "auto":
            est = budget_mod.estimate(ShotList.model_validate(run["plan"]["shotlist"]))
            budget = dict(budget or {}) | {"videos": est["videos"], "regens": est["regens"]} | _keyframe_budget(run)
        kw["plan"] = run["plan"]
    if budget:
        await store.add_budget(rid, {k: int(v) for k, v in budget.items()})
    if gate in AFTER_GATE:
        kw["stage"] = "KEYFRAMES" if gate == "ASSETS" and _keyframe_mode(run) else AFTER_GATE[gate]
    return await store.update_run(rid, **kw)


async def make_missing_refs(rid: str) -> dict:
    """At the ASSETS gate: generate every asset image still missing, one queued request each, then ask again."""
    run = await store.get_run(rid)
    if run["status"] != "WAITING_GATE" or run["gate"] != "ASSETS":
        raise ValueError("missing images can only be made at the ASSETS gate")
    missing = await _refs_needed(run["plan"]["ids"])
    if not missing:
        raise ValueError("no asset image is missing")
    await store.add_budget(rid, {"refs": len(missing)})
    return await store.update_run(rid, status="RUNNING", gate=None, error=None, stage="REFS")


async def revise(rid: str, feedback: str) -> dict:
    run = await store.get_run(rid)
    if run["gate"] != "SCRIPT":
        raise ValueError("revisions are only accepted at the SCRIPT gate")
    plan = run["plan"]
    report = await brain.think("editor", {k: plan[k] for k in ("brief", "story", "shotlist", "prompts")}
                               | {"idea": run["brief"].get("text", ""), "user_feedback": feedback}, EditorReport)
    retro = await brain.think("coach", {"user_feedback": feedback}, Retro)
    await lessons.apply_retro(retro, rid, source="user")
    plan.setdefault("revision_notes", []).append(f"[USER] {feedback}")
    plan["revision_notes"] += [f"[{f.target_stage}] {f.issue}" for f in report.fixes]
    now = await store.get_run(rid)
    if now["status"] != "WAITING_GATE" or now["gate"] != "SCRIPT":
        raise ValueError("run left the SCRIPT gate while the revision was being prepared")
    target = min((f.target_stage for f in report.fixes), key=STAGES.index, default="STORY")
    plan["revise"] = targeted.plan_revision(report.fixes)
    return await store.update_run(rid, plan=plan, stage=target, status="RUNNING", gate=None)


async def resolve_shot_failure(rid: str, action: Literal["drop", "stop", "retry"]) -> dict:
    """drop: cut without the failed clips; retry: cut again after the user re-made them (h_cut checks); stop."""
    run = await store.get_run(rid)
    if run["gate"] != "SHOT_FAILED":
        raise ValueError("no failed shots to resolve")
    if action == "stop":
        return await store.update_run(rid, status="FAILED", gate=None, error="stopped by user")
    if action == "retry":
        return await store.update_run(rid, status="RUNNING", gate=None)
    run["plan"]["drop"] = list(run["plan"].get("failed", {}))
    return await store.update_run(rid, plan=run["plan"], status="RUNNING", gate=None)


def _one_prompt(p: ShotPrompt, shot_id: str, blocks: dict, mode: str) -> ShotPrompts:
    sp = ShotPrompts(prompts=[p.model_copy(update={"shot_id": shot_id})], **blocks)
    return lint.assemble(sp) if mode in ("continuous", "ambient") else sp


def rewrite_issues(p: ShotPrompt, shot_id: str, shots: ShotList, story, blocks: dict, mode: str) -> list[lint.LintIssue]:
    """A rewritten clip is linted by its film's mode, in its place in the film (the next shot's keyframe / chain).
    23/10 Blue Morning: a keyframe film was linted by the cut-mode template (Bối cảnh / Góc quay … blocks), so every
    "Claude viết lại prompt" failed after 3 tries."""
    one = _one_prompt(p, shot_id, blocks, mode)
    if mode == "cut":
        shot = next(s for s in shots.shots if s.id == shot_id)
        return lint.lint_prompts(one, ShotList(shots=[shot]), story)
    return [i for i in lint.lint_prompts(one, shots, story, None, mode) if i.shot_id in (shot_id, None)]


async def rewrite_shot(rid: str, shot_id: str, feedback: str, review: dict | None = None) -> dict:
    """The user's words about one clip — or the video review's errors (22/10: "Claude đánh giá" found 5 errors and the
    user asked whether Claude rewrites the prompt itself) → a new prompt for that clip, proposed, not applied (no credit).
    A continuous film is linted as one: template, style/avoid blocks, its place in the chain."""
    run = await store.get_run(rid)
    if run["status"] == "RUNNING":
        raise ValueError("the director is busy; pause it or wait for a gate before rewriting a clip")
    plan = run["plan"]
    story, shots = _models(plan)
    shot = next((s for s in shots.shots if s.id == shot_id), None)
    current = next((p for p in plan.get("prompts", {}).get("prompts", []) if p["shot_id"] == shot_id), None)
    if not shot or not current:
        raise LookupError("shot not found")
    mode = (plan.get("brief") or {}).get("film_mode") or "cut"
    blocks = {k: (plan.get("prompts") or {}).get(k) or "" for k in ("style_block", "avoid_block")}

    def one(p: ShotPrompt) -> ShotPrompts:
        return _one_prompt(p, shot_id, blocks, mode)

    def check(p: ShotPrompt) -> list[lint.LintIssue]:
        return rewrite_issues(p, shot_id, shots, story, blocks, mode)

    ask = {"brief": plan["brief"], "cast": [c.model_dump() for c in story.cast], "shot": shot.model_dump(),
           "current_prompt": current["video_prompt"], "feedback": feedback}
    if review:
        ask["review"] = review
    out = await think_with_lint(run, "RESHOOT", "reshoot", ask, ShotPrompt, check)
    proposal = one(out).prompts[0].model_dump()
    plan.setdefault("proposals", {})[shot_id] = proposal | {"feedback": feedback}
    await store.update_run(rid, plan=plan)
    return {"shot_id": shot_id, "feedback": feedback, "old": current["video_prompt"], "new": proposal["video_prompt"]}


async def apply_rewrite(rid: str, shot_id: str) -> dict:
    """Make the proposed prompt the clip's prompt (plan + scene). Regenerating the clip is a separate,
    credit-confirmed click on the scene."""
    run = await store.get_run(rid)
    plan = run["plan"]
    proposal = plan.get("proposals", {}).pop(shot_id, None)
    if not proposal:
        raise LookupError("no proposal for this shot")
    for p in plan["prompts"]["prompts"]:
        if p["shot_id"] == shot_id:
            p["video_prompt"], p["end_frame"] = proposal["video_prompt"], proposal["end_frame"]
    scene_id = plan["ids"]["scenes"].get(shot_id)
    if scene_id:
        await crud.update_scene(scene_id, video_prompt=proposal["video_prompt"])
    return await store.update_run(rid, plan=plan)


async def clips_missing(run: dict) -> list[int]:
    """Scene numbers of the film that have no video yet."""
    ids, ori, shots = _shot_ctx(run)
    prefix = "vertical" if ori == "VERTICAL" else "horizontal"
    out = []
    for s in shots:
        scene = await crud.get_scene(ids["scenes"].get(s.id, "")) if ids.get("scenes", {}).get(s.id) else None
        if not (scene and scene.get(f"{prefix}_video_status") == "COMPLETED"):
            out.append(s.order)
    return sorted(out)


async def recut(rid: str) -> dict:
    """Cut the film from each scene's current take (after a regenerated clip or a version swap) — or for the first
    time when the user made every clip by hand after the run stopped (22/10: Old Walt was cancelled at REFS, all 6
    clips were then made on the canvas, and the film node had no button). Free: ffmpeg only."""
    run = await store.get_run(rid)
    if not run["plan"].get("qc") and await clips_missing(run):
        raise ValueError("this film has not been cut yet")
    await h_cut(run)
    await store.update_run(rid, plan=run["plan"])
    await h_publish(run)
    run = await store.update_run(rid, status="DONE", stage="DONE", error=None)
    # 22/10 Leo Marsh: without this the open canvas kept showing "bấm ghép phim" after the film was cut
    await event_bus.emit("director_stage", {"run_id": rid, "stage": "DONE", "status": "DONE"})
    return run
