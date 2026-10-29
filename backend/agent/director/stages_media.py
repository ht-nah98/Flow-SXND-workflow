"""Director stages that make the pictures and clips: canvas nodes, references, keyframes, videos. Split from pipeline.py on 23/10 (code moved, not changed)."""


from agent import config
from agent.db import crud
from agent.director import budget as budget_mod
from agent.director import chain as chain_mod
from agent.director import ingest as ingest_mod
from agent.director import production
from agent.director.schemas import (ShotList)
from agent.director.stage_common import Gate, _ask, _gen, _keyframe_budget, _keyframe_mode, _shot_ctx

async def _refs_needed(ids: dict) -> dict[str, str]:
    """Entities that still need a generated reference: the user's uploaded pictures are already references."""
    out = {}
    for name, cid in ids["entities"].items():
        ch = await crud.get_character(cid)
        if not (ch and ch.get("media_id")):
            out[name] = cid
    return out


async def h_ingest(run):
    if (run["plan"].get("ids") or {}).get("video_id"):
        await ingest_mod.sync_scenes(run)
    else:
        await ingest_mod.ingest(run)
    ids = run["plan"]["ids"]
    need = await _refs_needed(ids)
    raise _ask(run, "SCRIPT", {"refs": len(need)}, script_payload(run, len(need), len(ids["entities"]) - len(need)))


def script_payload(run, refs: int, provided: int) -> dict:
    """What the SCRIPT gate shows and "⏩ Chạy toàn bộ" grants. 23/10 Blue Morning: the keyframe stills (one per shot)
    were granted but left out of the shown total."""
    est = budget_mod.estimate_refs(refs)
    vid = budget_mod.estimate(ShotList.model_validate(run["plan"]["shotlist"]))
    keyframes = _keyframe_budget(run).get("images", 0)
    keyframe_credits = keyframes * config.DIRECTOR_CREDIT_TABLE["image"]
    return {"shots": len(run["plan"]["shotlist"]["shots"]), "refs": refs, "provided": provided,
            "credits_est": est["credits_est"], "videos": vid["videos"], "regens": vid["regens"],
            "video_credits_est": vid["credits_est"],
            **({"keyframes": keyframes, "keyframe_credits_est": keyframe_credits} if keyframes else {}),
            "total_credits_est": est["credits_est"] + keyframe_credits + vid["credits_est"]}


async def h_refs(run):
    ids = run["plan"]["ids"]
    orientation = run["plan"]["brief"]["orientation"]   # locations are framed like the film
    try:
        req_ids = [await production.request_for(run, f"ref:{name}", "refs", retry_failed=True,
                                                 req_type="GENERATE_CHARACTER_IMAGE", orientation=orientation,
                                                 character_id=cid, project_id=ids["project_id"])
                   for name, cid in (await _refs_needed(ids)).items()]
    except budget_mod.BudgetExceeded as e:
        raise Gate("BUDGET_EXCEEDED", {"kind": e.kind}) from e
    rows = await production.wait_requests(req_ids, run_id=run["id"]) if req_ids else {}
    failed = [r["id"] for r in rows.values() if r["status"] == "FAILED"]
    est = budget_mod.estimate(ShotList.model_validate(run["plan"]["shotlist"]))
    run["plan"]["estimate"] = est
    if run["plan"].get("mode") == "auto" and not failed:   # video credit was granted with the script
        return "KEYFRAMES" if _keyframe_mode(run) else "VIDEOS"
    granted = run["plan"].get("mode") == "auto"
    keys = _keyframe_budget(run)
    ask = {} if granted else {"videos": est["videos"], "regens": est["regens"]} | keys
    raise _ask(run, "ASSETS", ask, {"refs": len(req_ids), "failed_refs": failed} | est | keys
               | ({"credits_est": 0} if granted else
                  {"credits_est": est["credits_est"] + keys.get("images", 0) * config.DIRECTOR_CREDIT_TABLE["image"]}))


async def h_keyframes(run):
    """Keyframe mode (directive B13, playbook 10 §5): one still per shot, generated from the cast pictures; the user
    looks at them (one is cheap to redo on its scene) before any video credit is spent. Other modes skip this stage."""
    if not _keyframe_mode(run):
        return "VIDEOS"
    ids, ori, shots = _shot_ctx(run)
    prefix = "vertical" if ori == "VERTICAL" else "horizontal"
    keys = {}
    for s in shots:
        scene = await crud.get_scene(ids["scenes"][s.id])
        if scene.get(f"{prefix}_image_status") == "COMPLETED" and scene.get(f"{prefix}_image_media_id"):
            continue
        keys[s.id] = await _gen(run, f"key:{s.id}", "images", retry_failed=True, req_type="GENERATE_IMAGE",
                                scene_id=ids["scenes"][s.id], video_id=ids["video_id"],
                                project_id=ids["project_id"], orientation=ori)
    rows = await production.wait_requests(list(keys.values()), run_id=run["id"]) if keys else {}
    failed = sorted(s.order for s in shots if s.id in keys and rows[keys[s.id]]["status"] == "FAILED")
    # Even "⏩ Chạy toàn bộ" stops here: the stills are the cheap step to check (23/10 Blue Morning: 21 videos went out
    # unseen, and a character who looked like a celebrity was refused clip after clip).
    raise _ask(run, "KEYFRAMES", {}, {"keyframes": len(shots), "made": len(keys), "failed_scenes": failed})


async def _missing_keyframes(run) -> list[int]:
    ids, ori, shots = _shot_ctx(run)
    prefix = "vertical" if ori == "VERTICAL" else "horizontal"
    out = []
    for s in shots:
        scene = await crud.get_scene(ids["scenes"][s.id])
        if not (scene or {}).get(f"{prefix}_image_media_id"):
            out.append(s.order)
    return sorted(out)


class MissingRefs(ValueError):
    pass


async def _check_refs(run) -> None:
    """Every clip is r2v: a missing character/location/prop picture would make Flow invent one."""
    missing = sorted(await _refs_needed(run["plan"]["ids"]))
    if missing:
        raise MissingRefs(f"asset images still missing: {', '.join(missing)}")


async def h_videos(run):
    try:
        await _check_refs(run)
    except MissingRefs as e:
        raise _ask(run, "ASSETS", {}, dict(run["plan"].get("gate_payload") or {}) | {"missing": str(e)}) from e
    ids, ori, shots = _shot_ctx(run)
    failed = run["plan"].setdefault("failed", {})

    keyframe = _keyframe_mode(run)
    if keyframe:
        await _pin_keyframes(ids, ori, shots)

    async def gen(s):
        return await _gen(run, f"vid:{s.id}", "videos", req_type="GENERATE_VIDEO" if keyframe else "GENERATE_VIDEO_REFS",
                          scene_id=ids["scenes"][s.id], video_id=ids["video_id"],
                          project_id=ids["project_id"], orientation=ori)
    if run["plan"]["brief"].get("film_mode") == "continuous":
        await chain_mod.make_all(run, shots, gen)   # one chain clip after another, each from the last frame before
        return "QC"
    keys = {}
    for s in shots:
        keys[s.id] = await gen(s)
    rows = await production.wait_requests(list(keys.values()), run_id=run["id"]) if keys else {}
    for sid, rid in keys.items():
        if rows[rid]["status"] == "FAILED":
            failed[sid] = "video"
    return "QC"


async def _pin_keyframes(ids: dict, ori: str, shots) -> None:
    """Keyframe mode: shot i ends on shot i+1's still when shot i+1 joins (playbook 10 §1) — the same picture on both
    sides of the join, so Omni first+last lands the cut exactly. "" (not None: the update skips None) = start frame only."""
    prefix = "vertical" if ori == "VERTICAL" else "horizontal"
    seq = sorted(shots, key=lambda x: x.order)
    for cur, nxt in zip(seq, seq[1:] + [None]):
        end = ""
        if nxt is not None and nxt.join_in != "cut":
            end = (await crud.get_scene(ids["scenes"][nxt.id])).get(f"{prefix}_image_media_id") or ""
        await crud.update_scene(ids["scenes"][cur.id], **{f"{prefix}_end_scene_media_id": end})
