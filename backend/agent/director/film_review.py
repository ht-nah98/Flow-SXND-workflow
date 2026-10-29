"""Agent Review (21/10): the whole film judged at once — script, each clip, the seams between clips, root causes.

The user used to paste frames into the Claude chat and ask "why did the pot become a saucepan?". This does that review
on the canvas: one contact sheet per clip (1 frame/s), one image per seam (last frame used of clip N beside the first
frame used of clip N+1), the asset images, and the full plan (idea, story, shots, prompts, trims) go to the
`reviewer` role, which returns scored layers and findings with a cause and a proposed fix.

Reviews live in a JSON file per run, not in the run's plan: a recut writing its own copy of the plan must never wipe a
review that finished meanwhile. Free: Claude only, no Flow request."""
import asyncio
import json
import logging
import subprocess
import time
import uuid
from pathlib import Path

from agent import config
from agent.db import crud
from agent.director import brain, cut as cut_mod, lessons, store
from agent.director.schemas import FilmReview, ShotList, ShotPrompts, Story
from agent.utils.tasks import spawn

logger = logging.getLogger(__name__)
KEEP = 10                 # reviews kept per run, newest first
FRAME_W = 320             # px per frame on a clip sheet
_jobs: dict[str, dict] = {}   # run id → {"status": RUNNING|FAILED, "error", "started"}; done reviews are on disk


def _dir(rid: str) -> Path:
    return Path(config.DATA_DIR) / "film_review" / rid


def _file(rid: str) -> Path:
    return Path(config.DATA_DIR) / "film_review" / f"{rid}.json"


def list_reviews(rid: str) -> list[dict]:
    try:
        return json.loads(_file(rid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def job(rid: str) -> dict | None:
    return _jobs.get(rid)


def _save(rid: str, entry: dict) -> None:
    f = _file(rid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(([entry] + list_reviews(rid))[:KEEP], ensure_ascii=False, indent=1), encoding="utf-8")


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True, capture_output=True, timeout=120)


def clip_sheet(clip: Path, out: Path, duration: float) -> Path:
    """One frame per second (at k+0.5 s), five per row: frame k of the sheet is second k of the clip."""
    n = max(1, int(duration))
    rows = (n + 4) // 5
    _ffmpeg("-ss", "0.5", "-i", str(clip), "-vf", f"fps=1,scale={FRAME_W}:-2,tile=5x{rows}", "-frames:v", "1", str(out))
    return out


def seam_image(a: Path, a_t: float, b: Path, b_t: float, out: Path) -> Path:
    """The last frame the film shows of clip a beside the first frame it shows of clip b."""
    _ffmpeg("-ss", f"{max(0.0, a_t - 0.1):.2f}", "-i", str(a), "-ss", f"{b_t + 0.05:.2f}", "-i", str(b),
            "-filter_complex", f"[0:v]scale={FRAME_W * 2}:-2[l];[1:v]scale={FRAME_W * 2}:-2[r];[l][r]hstack",
            "-frames:v", "1", str(out))
    return out


async def _asset_images(names: set[str], project_id: str, work: Path) -> dict[str, str]:
    """name → local image path, for the cast/props/places the clips use. A link that fails is just left out."""
    from agent.services import video_reviewer
    out = {}
    for c in await crud.get_project_characters(project_id):
        url = c.get("reference_image_url")
        if c["name"] not in names or not url:
            continue
        dest = work / "assets" / f"{c['id']}.jpg"
        try:
            local = video_reviewer._local_media_path(url)
            if not local:
                dest.parent.mkdir(parents=True, exist_ok=True)
                await video_reviewer._download_video(url, dest)   # plain GET; works for images too
                local = dest
            out[c["name"]] = str(local)
        except Exception as e:  # noqa: BLE001 — a missing picture weakens the review, it does not stop it
            logger.info("film review: no image for %s: %s", c["name"], e)
    return out


async def build_payload(run: dict, note: str, work: Path) -> dict:
    plan = run["plan"]
    ids, ori = plan["ids"], plan["brief"]["orientation"]
    drop = set(plan.get("drop", []))
    shots = [s for s in sorted(ShotList.model_validate(plan["shotlist"]).shots, key=lambda s: s.order) if s.id not in drop]
    prompts = {p.shot_id: p.video_prompt for p in ShotPrompts.model_validate(plan["prompts"]).prompts}
    story = Story.model_validate(plan["story"])
    trims = plan.get("trims") or [[0.0, s.duration_s] for s in shots]
    edit = (plan.get("edit") or {}).get("clips") or []
    clips, paths, film_t = [], [], 0.0
    for n, s in enumerate(shots):
        scene = await crud.get_scene(ids["scenes"][s.id])
        path = await cut_mod.local_clip(scene, ori, work / "clips")
        paths.append(path)
        t_in, t_out = trims[n] if n < len(trims) else (0.0, s.duration_s)
        sheet = await asyncio.to_thread(clip_sheet, path, work / f"clip-{n + 1:02d}.jpg", s.duration_s)
        clips.append({"scene": n + 1, "shot_id": s.id, "idea": s.idea, "story_beat": s.story_beat, "period": s.period,
                      "bridge": s.bridge.model_dump() if s.bridge else None, "props": s.props,
                      "actions": [a.model_dump() for a in s.actions], "video_prompt": prompts.get(s.id, ""),
                      "used_in_film_s": [round(t_in, 2), round(t_out, 2)], "film_start_s": round(film_t, 2),
                      "transition_out": (edit[n].get("transition_out") if n < len(edit) else s.edit_transition_out),
                      "sheet": str(sheet)})
        film_t += t_out - t_in
    seams = []
    for n in range(len(shots) - 1):
        img = await asyncio.to_thread(seam_image, paths[n], trims[n][1], paths[n + 1], trims[n + 1][0],
                                      work / f"seam-{n + 1:02d}-{n + 2:02d}.jpg")
        seams.append({"from_scene": n + 1, "to_scene": n + 2, "image": str(img)})
    names = {c.name for c in story.cast} | {x for s in shots for x in s.cast}
    return {
        "idea": run["brief"].get("text", ""), "brief": plan["brief"],
        "story": story.model_dump(), "clips": clips, "seams": seams,
        "asset_images": await _asset_images(names, ids["project_id"], work),
        "film_duration_s": round(film_t, 2), "user_note": note.strip(),
        "_context": await lessons.context_for("reviewer"),
    }


def film_time(entry_clips: list[dict], scene: int | None, clip_t: float | None) -> float | None:
    """Where a finding sits in the film: the clip's start in the film + its offset inside the used window."""
    if not scene or scene < 1 or scene > len(entry_clips):
        return None
    c = entry_clips[scene - 1]
    t_in, t_out = c["used_in_film_s"]
    off = min(max((clip_t if clip_t is not None else t_in) - t_in, 0.0), t_out - t_in)
    return round(c["film_start_s"] + off, 1)


async def review(rid: str, note: str = "") -> dict:
    run = await store.get_run(rid)
    work = _dir(rid) / uuid.uuid4().hex[:8]
    work.mkdir(parents=True, exist_ok=True)
    payload = await build_payload(run, note, work)
    rep: FilmReview = await brain.think("reviewer", payload, FilmReview, tools=["Read"], add_dirs=[str(work)])
    clips = [{k: c[k] for k in ("scene", "shot_id", "idea", "used_in_film_s", "film_start_s")} for c in payload["clips"]]
    findings = []
    for i, f in enumerate(rep.findings, 1):
        d = f.model_dump()
        if d.get("scene") and not d.get("shot_id") and d["scene"] <= len(clips):
            d["shot_id"] = clips[d["scene"] - 1]["shot_id"]
        findings.append(d | {"id": f"F{i}", "film_t": film_time(clips, d.get("scene"), d.get("clip_t"))})
    entry = {"id": uuid.uuid4().hex[:12], "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "final_path": run.get("final_path"), "note": note.strip(), "clips": clips,
             "film_duration_s": payload["film_duration_s"], "summary": rep.summary, "strengths": rep.strengths,
             "scores": [s.model_dump() for s in rep.scores], "findings": findings}
    _save(rid, entry)
    await lessons.learn_from_film_review(findings, rid)       # the next film reads these rules
    return entry


def start(rid: str, note: str = "") -> dict:
    """Run a review in the background; the canvas polls the job and the list."""
    if (_jobs.get(rid) or {}).get("status") == "RUNNING":
        raise ValueError("a review of this film is already running")
    state = _jobs[rid] = {"status": "RUNNING", "error": None, "started": time.time(), "note": note}

    async def go():
        from agent.services.event_bus import event_bus
        try:
            await review(rid, note)
            _jobs.pop(rid, None)
        except Exception as e:  # noqa: BLE001 — surfaced on the review node
            logger.exception("film review failed for %s", rid)
            state.update(status="FAILED", error=f"{type(e).__name__}: {e}")
        await event_bus.emit("film_review", {"run_id": rid})
    spawn(go(), name=f"film-review:{rid[:8]}")
    return state
