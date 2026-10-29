"""Director stages that finish the film: clip QC, the cut, publishing, the retro. Split from pipeline.py on 23/10 (code moved, not changed)."""
import asyncio
import logging
from pathlib import Path


from agent import config
from agent.db import crud
from agent.director import brain
from agent.director import budget as budget_mod
from agent.director import cut as cut_mod
from agent.director import effects
from agent.director import lessons, production, store
from agent.director.schemas import (QcReport, Retro, ShotList, ShotPrompts)
from agent.services import video_reviewer
from agent.utils.paths import project_folder
from agent.director.stage_common import Gate, StageFailed, _shot_ctx, agent_on

logger = logging.getLogger(__name__)

async def _clip_media(scene_id: str, ori: str) -> str | None:
    """The take QC judged; a different take on the scene later means its trims no longer apply."""
    scene = await crud.get_scene(scene_id)
    return (scene or {}).get(f"{'vertical' if ori == 'VERTICAL' else 'horizontal'}_video_media_id")


# A take the QC never saw (the user picked another version): keep its steady middle.
UNREVIEWED_TRIM = (1.0, 8.0)


def _contact_sheets(path, out_dir) -> list[str]:
    sheets, _, _ = video_reviewer._create_contact_sheets(str(path), 2.0, str(out_dir))
    return [str(s) for s in sheets]


def _video_type(shot) -> str:
    return "GENERATE_VIDEO_REFS"   # v2: every shot is reference-to-video


QC_BATCH = 4   # clips per QC call: one call re-reads the whole role prompt, so batching cuts the cost ~3x


async def _qc_batch(run, shots, prompts: dict, work: Path, attempt: int = 1) -> dict[str, dict]:
    """One QC call for several clips. A clip the reviewer leaves out passes unreviewed with the default trim."""
    work = work / f"attempt-{attempt}"   # a post-regen pass must not reuse the cached clip/sheets
    ids, ori = run["plan"]["ids"], run["plan"]["brief"]["orientation"]
    clips = []
    for shot in shots:
        scene = await crud.get_scene(ids["scenes"][shot.id])
        clip = await cut_mod.local_clip(scene, ori, work / "clips")
        sheet_dir = work / "sheets" / shot.id
        sheet_dir.mkdir(parents=True, exist_ok=True)
        clips.append({"shot": shot.model_dump(), "video_prompt": prompts[shot.id],
                      "contact_sheets": _contact_sheets(clip, sheet_dir)})
    payload = {"clips": clips, "_context": await lessons.context_for("qc")}
    rep = await brain.think("qc", payload, QcReport, tools=["Read"], add_dirs=[str(work / "sheets")])
    got = {i.shot_id: i.model_dump() for i in rep.items}
    if len(shots) == 1 and shots[0].id not in got and rep.items:   # a single clip answered under another id
        got[shots[0].id] = rep.items[0].model_dump()
    return {s.id: (got.get(s.id) or {"verdict": "PASS", "issues": ["QC did not return this clip"],
                                     "trim_in_s": UNREVIEWED_TRIM[0],
                                     "trim_out_s": min(UNREVIEWED_TRIM[1], s.duration_s)}) | {"shot_id": s.id}
            for s in shots}


async def _qc_one(run, shot, prompt, work: Path, attempt: int = 1) -> dict:
    return (await _qc_batch(run, [shot], {shot.id: prompt}, work, attempt))[shot.id]


async def h_qc(run):
    ids, ori, shots = _shot_ctx(run)
    prompts = {p.shot_id: p.video_prompt for p in ShotPrompts.model_validate(run["plan"]["prompts"]).prompts}
    failed = run["plan"].setdefault("failed", {})
    qc = run["plan"].setdefault("qc", {})
    work = Path(config.DATA_DIR) / "qc" / run["id"]          # contact sheets: internal, not output
    todo = [s for s in shots if s.id not in failed and not qc.get(s.id, {}).get("final")]
    if not agent_on(run, "qc"):     # no AI review: keep each clip's middle, no regen
        for s in todo:
            qc[s.id] = {"shot_id": s.id, "verdict": "PASS", "issues": [], "trim_in_s": UNREVIEWED_TRIM[0],
                        "trim_out_s": min(UNREVIEWED_TRIM[1], s.duration_s), "skipped": True, "final": True,
                        "media_id": await _clip_media(ids["scenes"][s.id], ori)}
        await store.update_run(run["id"], plan=run["plan"])
        return "CUT"
    for k in range(0, len(todo), QC_BATCH):
        batch = todo[k:k + QC_BATCH]
        try:
            items = await _qc_batch(run, batch, prompts, work)
        except brain.BrainError as e:
            items = {s.id: {"shot_id": s.id, "verdict": "PASS", "issues": [f"QC unavailable: {e}"],
                            "trim_in_s": 0, "trim_out_s": s.duration_s} for s in batch}
        for s in batch:
            item = items[s.id]
            # Continuous mode: a new take of a chain clip would not match the clip made from its last frame, so QC
            # reports and the user decides (Agent Review / regenerate the chain from there).
            regen = run["plan"]["brief"].get("film_mode", "cut") == "cut"   # other modes: report only
            if regen and item["verdict"] == "FAIL" and f"regen:{s.id}" not in run["plan"].get("requests", {}):
                try:
                    # the worker skips GENERATE_VIDEO* when the scene video is already COMPLETED (R14)
                    await crud.update_scene(ids["scenes"][s.id],
                                            **{f"{'vertical' if ori == 'VERTICAL' else 'horizontal'}_video_status": "PENDING"})
                    rid = await production.request_for(run, f"regen:{s.id}", "regens", req_type=_video_type(s),
                                                       scene_id=ids["scenes"][s.id], video_id=ids["video_id"],
                                                       project_id=ids["project_id"], orientation=ori)
                    row = (await production.wait_requests([rid], run_id=run["id"]))[rid]
                    if row["status"] == "COMPLETED":
                        item = await _qc_one(run, s, prompts[s.id], work, attempt=2)
                except budget_mod.BudgetExceeded:
                    item["issues"].append("no regen budget left")
            qc[s.id] = item | {"final": True, "media_id": await _clip_media(ids["scenes"][s.id], ori)}
            await store.log_event(run["id"], "qc", f"Cảnh {s.order}: {'đạt' if item['verdict'] == 'PASS' else 'lỗi'}",
                                  {"shot_id": s.id, "scene": s.order, "verdict": item["verdict"],
                                   "issues": item.get("issues", [])}, "ok" if item["verdict"] == "PASS" else "warn")
            await store.update_run(run["id"], plan=run["plan"])
    return "CUT"


def current_edit(plan: dict, shots: list | None = None) -> dict:
    """The film's effects, one entry per shot in film order: what the user saved (plan["edit"]) wins over what the
    director wrote (film_look, edit_fx, edit_transition_out). Names are not checked here; effects.py drops unknown ones."""
    if shots is None:
        drop = set(plan.get("drop", []))
        shots = [s for s in sorted(ShotList.model_validate(plan["shotlist"]).shots, key=lambda s: s.order)
                 if s.id not in drop]
    saved = plan.get("edit") or {}
    by_shot = {c.get("shot_id"): c for c in saved.get("clips", [])}
    look = saved["look"] if "look" in saved else plan["shotlist"].get("film_look")
    return {"look": look, "clips": [by_shot.get(s.id) or {"shot_id": s.id, "fx": list(s.edit_fx),
                                                           "transition_out": s.edit_transition_out}
                                     for s in shots]}


async def save_edit(rid: str, edit: dict) -> dict:
    """Store the user's choice of effects (free). It is used by the next cut or re-cut."""
    run = await store.get_run(rid)
    if not run or not run["plan"].get("shotlist"):
        raise LookupError("no script yet")
    known = {s["id"] for s in run["plan"]["shotlist"]["shots"]}
    clips = []
    for c in edit.get("clips", []):
        if c.get("shot_id") not in known:
            raise ValueError(f"unknown shot {c.get('shot_id')}")
        clips.append({"shot_id": c["shot_id"],
                      "fx": [f for f in (effects.resolve(x, effects.CLIP_FX) for x in c.get("fx") or []) if f][:2],
                      "transition_out": effects.resolve(c.get("transition_out"), effects.TRANSITIONS) or "cat"})
    run["plan"]["edit"] = {"look": effects.resolve(edit.get("look"), effects.LOOKS) or "goc", "clips": clips}
    await store.update_run(rid, plan=run["plan"])
    return current_edit(run["plan"])


async def h_cut(run):
    ids, ori, shots = _shot_ctx(run)
    plan = run["plan"]
    prefix = "vertical" if ori == "VERTICAL" else "horizontal"
    # A failed clip the user re-made on the canvas since (20/10) is no longer failed, nor dropped.
    for sid in list(plan.get("failed", {})) + list(plan.get("drop", [])):
        scene = await crud.get_scene(ids["scenes"].get(sid, "")) if ids["scenes"].get(sid) else None
        if scene and scene.get(f"{prefix}_video_status") == "COMPLETED":
            plan.get("failed", {}).pop(sid, None)
            plan["drop"] = [d for d in plan.get("drop", []) if d != sid]
    drop = set(plan.get("drop", []))
    pending = [sid for sid in plan.get("failed", {}) if sid not in drop]
    if pending:
        order = {s.id: s.order for s in shots}
        raise Gate("SHOT_FAILED", {"shots": pending, "scenes": sorted(order[sid] for sid in pending if sid in order)})
    use = [s for s in sorted(shots, key=lambda s: s.order) if s.id not in drop]
    if not use:
        raise StageFailed("no shots left to cut")
    project = await crud.get_project(ids["project_id"])
    # The film is the project's deliverable: OUTPUT_DIR/<project folder>/final.mp4, its parts in _dung-phim/.
    film_dir = Path(config.OUTPUT_DIR) / project_folder(project)
    out_dir = film_dir / "_dung-phim"
    if plan["brief"].get("film_mode") == "ambient":
        return await _cut_ambient(run, use, ids, ori, film_dir, out_dir)
    clips, paths = [], []
    for s in use:
        scene = await crud.get_scene(ids["scenes"][s.id])
        paths.append(str(await cut_mod.local_clip(scene, ori, out_dir / "clips")))
        q = plan.get("qc", {}).get(s.id, {})
        if not q or q.get("media_id") and q["media_id"] != scene.get(f"{prefix}_video_media_id"):
            q = {"trim_in_s": UNREVIEWED_TRIM[0], "trim_out_s": UNREVIEWED_TRIM[1]}
        clips.append({"duration": s.duration_s, "trim_in": q.get("trim_in_s", 0),
                      "trim_out": q.get("trim_out_s", s.duration_s), "voice": bool(s.voice_line),
                      # the action, plus half a second to land: windows sit on it, shortening spares its end (F3)
                      "focus": ((min(a.start_s for a in s.actions), max(a.end_s for a in s.actions) + 0.5)
                                if s.actions else None)})
    continuous = plan["brief"].get("film_mode") == "continuous"
    keyframe = plan["brief"].get("film_mode") == "keyframe"
    if continuous:   # playbook 09 §7: clips almost whole; the camera already made the transitions
        trims = cut_mod.chain_trims(use)
    elif keyframe:   # playbook 10 §6: use_s seconds, against the pinned stills
        trims = cut_mod.keyframe_trims(use)
    else:
        trims = cut_mod.plan_trims(clips, plan["brief"]["target_s"])
    plan["trims"] = trims
    size = cut_mod.FILM_SIZE[ori]
    edit = current_edit(plan, use)
    if continuous:
        edit = cut_mod.chain_edit(edit, use)
    elif keyframe:
        edit = cut_mod.keyframe_edit(edit, use)
    plan["edit"] = edit
    final = await cut_mod.render_cut(paths, trims, str(film_dir / "final.mp4"), size,
                                     run["brief"].get("music_path"), edit=edit)
    await store.update_run(run["id"], final_path=final)
    run["final_path"] = final
    return "PUBLISH"


async def _cut_ambient(run, use, ids, ori, film_dir: Path, out_dir: Path) -> str:
    """Directive B14 (playbook 11 §7): reel.mp4 = the clips whole, plain cuts, muted; final.mp4 = the reel looped to the
    music's length (or loop_s). Never the cut-mode trims or effects."""
    paths = [str(await cut_mod.local_clip(await crud.get_scene(ids["scenes"][s.id]), ori, out_dir / "clips"))
             for s in use]
    reel = await cut_mod.render_reel(paths, str(film_dir / "reel.mp4"), cut_mod.FILM_SIZE[ori])
    final = await cut_mod.loop_reel(reel, str(film_dir / "final.mp4"), run["plan"]["brief"].get("loop_s"),
                                    run["brief"].get("music_path"))
    run["plan"]["reel_path"] = reel
    await store.update_run(run["id"], final_path=final)
    run["final_path"] = final
    return "PUBLISH"


async def h_publish(run):
    """Put the film on the video, so the canvas shows the 🎞 node."""
    ids, ori = run["plan"]["ids"], run["plan"]["brief"]["orientation"]
    final = run.get("final_path") or (await store.get_run(run["id"]))["final_path"]
    duration = await asyncio.to_thread(cut_mod.probe_duration, final)
    await crud.update_video(ids["video_id"], status="COMPLETED",
                            **{f"{'vertical' if ori == 'VERTICAL' else 'horizontal'}_url": f"file://{final}"},
                            **({"duration": round(duration, 1)} if duration else {}))
    return "RETRO"


async def h_retro(run):
    plan = run["plan"]
    if not agent_on(run, "coach"):
        return "DONE"
    try:
        prompts = {p["shot_id"]: p["video_prompt"] for p in plan.get("prompts", {}).get("prompts", [])}
        flagged = [dict(q, shot_id=sid, video_prompt=prompts.get(sid, ""))
                   for sid, q in plan.get("qc", {}).items() if q.get("verdict") == "FAIL" or q.get("issues")]
        known = [{"id": l["id"], "rule": l["rule"], "status": l["status"]}
                 for st in ("ACTIVE", "PROPOSED") for l in await store.list_lessons(status=st)]
        payload = {"flagged": flagged, "stats": lessons.compute_stats(await store.list_runs()),
                   "known_lessons": known, "_context": ""}
        retro = await brain.think("coach", payload, Retro)
        await lessons.apply_retro(retro, run["id"])
    except Exception as e:  # learning must never block delivery
        logger.warning("retro failed for run %s: %s", run["id"], e)
    return "DONE"
