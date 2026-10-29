"""FK-LOCAL: AI Director API (spec §6)."""
import base64
import binascii
import copy
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from agent import config
from agent.db import crud
from agent.director import brain, ingest, lint, pipeline, production, runner, store
from agent.director.schemas import ShotList, ShotPrompts, Story
from agent.utils.tasks import spawn

router = APIRouter(prefix="/director", tags=["director"])
MUSIC_EXT = {".mp3", ".m4a", ".wav", ".aac"}
MAX_MUSIC_BYTES = 30 * 1024 * 1024
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGES = 6


class IdeaImageIn(BaseModel):
    base64: str = Field(max_length=14_000_000)   # ~10 MB decoded
    filename: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=500)
BUDGET_KEYS = {"refs", "images", "videos", "regens"}


# "auto": the producer reads it from the idea; the others are the user's explicit choice.
Voice = Literal["auto", "none", "voiceover", "dialogue"]
Language = Literal["en", "vi"]
# How freely the writer develops the idea (directive B9): faithful = stay close to what the user wrote;
# balanced = build a full story world around it (default); bold = free to invent subplots, places and times.
Creativity = Literal["faithful", "balanced", "bold"]
FilmMode = Literal["continuous", "cut", "keyframe", "ambient"]   # B12 (09), B13 keyframe (10), B14 ambient (11)
REEL_S = (60, 120)    # ambient: the reel that loops, 1–2 minutes (directive B14)
LOOP_MAX_S = 4 * 3600


class Agents(BaseModel):
    """Optional AI roles in the film's pipeline (directive A5). The writer, director and DP always run."""
    producer: bool = True   # reads the idea into a brief; off = the brief comes from the idea node's choices
    editor: bool = True     # scores and revises the script before the user reads it
    qc: bool = True         # watches every clip and picks its trim; off = a default middle window
    coach: bool = True      # learns lessons after the film
IDEA_MAX_CHARS = 20_000   # a full story synopsis fits; the canvas enforces the same limit


class RunCreate(BaseModel):
    text: str = Field(min_length=3, max_length=IDEA_MAX_CHARS)
    target_s: int = Field(default=60, ge=15, le=300)
    orientation: Literal["HORIZONTAL", "VERTICAL"] = "HORIZONTAL"
    style: str = "realistic"
    voice: Voice = "auto"
    language: Language = "en"       # spoken words and prompts; most films are set in an English-speaking world
    creativity: Creativity = "balanced"
    style_pack: str | None = None     # styles.PACKS id; None = the director picks the look
    film_mode: FilmMode = "continuous"   # directive B12, repeated 24/10: "Liền mạch là mặc định"
    venue: str | None = None             # ambient: venues.VENUES id
    reel_s: int | None = Field(default=None, ge=REEL_S[0], le=REEL_S[1])
    loop_s: int | None = Field(default=None, ge=REEL_S[0], le=LOOP_MAX_S)   # None = as long as the music
    agents: Agents = Agents()
    images: list[IdeaImageIn] = Field(default=[], max_length=MAX_IMAGES)
    music_base64: str | None = Field(default=None, max_length=41_000_000)  # ~30 MB decoded
    music_filename: str | None = None


class Approve(BaseModel):
    gate: str
    budget: dict[str, int] | None = None
    mode: Literal["step", "auto"] = "step"

    @field_validator("budget")
    @classmethod
    def _budget_ok(cls, v):
        if v is not None:
            if set(v) - BUDGET_KEYS:
                raise ValueError(f"budget keys must be within {sorted(BUDGET_KEYS)}")
            if any(n < 0 for n in v.values()):
                raise ValueError("budget values must be non-negative")
        return v


class IdeaPatch(BaseModel):
    text: str | None = Field(default=None, min_length=3, max_length=IDEA_MAX_CHARS)
    target_s: int | None = Field(default=None, ge=15, le=300)
    orientation: Literal["HORIZONTAL", "VERTICAL"] | None = None
    voice: Voice | None = None
    language: Language | None = None
    creativity: Creativity | None = None
    style_pack: str | None = None
    film_mode: FilmMode | None = None
    venue: str | None = None
    reel_s: int | None = Field(default=None, ge=REEL_S[0], le=REEL_S[1])
    loop_s: int | None = Field(default=None, ge=REEL_S[0], le=LOOP_MAX_S)
    agents: Agents | None = None
    notes: dict[str, str | None] | None = None    # image file -> the user's note on it


class Revise(BaseModel):
    feedback: str = Field(min_length=2, max_length=4000)


class ShotFailure(BaseModel):
    action: Literal["drop", "stop", "retry"]


class ShotPatch(BaseModel):
    mode: Literal["r2v"] | None = None
    duration_s: Literal[10] | None = None
    commands: list[str] | None = None
    video_prompt: str | None = None
    keyframe_prompt: str | None = None


class LessonPatch(BaseModel):
    status: Literal["ACTIVE", "RETIRED"]


async def _run_or_404(rid: str) -> dict:
    run = await store.get_run(rid)
    if not run:
        raise HTTPException(404, "run not found")
    return run


def _save_music(b64: str, name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext not in MUSIC_EXT:
        raise HTTPException(400, f"music must be one of {sorted(MUSIC_EXT)}")
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(400, "music_base64 is not valid base64") from e
    if len(data) > MAX_MUSIC_BYTES:
        raise HTTPException(400, "music file too large (max 30 MB)")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)[:80]
    path = Path(config.DATA_DIR) / "uploads" / "music" / f"{uuid.uuid4().hex[:8]}-{safe}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def _save_images(images: list[IdeaImageIn]) -> list[dict]:
    """Validate every picture before anything is written, then store them in one folder per idea."""
    decoded = []
    for i, img in enumerate(images, 1):
        ext = Path(img.filename).suffix.lower()
        if ext not in IMAGE_EXT:
            raise HTTPException(400, f"image {img.filename!r} must be one of {sorted(IMAGE_EXT)}")
        try:
            data = base64.b64decode(img.base64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise HTTPException(400, f"image {img.filename!r} is not valid base64") from e
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(400, f"image {img.filename!r} is too large (max 10 MB)")
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(img.filename).name)[:80]
        decoded.append((f"{i}-{safe}", data, img.note))
    if not decoded:
        return []
    folder = Path(config.DATA_DIR) / "uploads" / "ideas" / uuid.uuid4().hex[:12]
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for name, data, note in decoded:
        (folder / name).write_bytes(data)
        out.append({"file": str((folder / name).resolve()), "note": note})
    return out


@router.post("/runs", status_code=201)
async def create_run(body: RunCreate):
    brief = {"text": body.text, "target_s": body.target_s, "orientation": body.orientation, "style": body.style,
             "voice": body.voice, "language": body.language, "creativity": body.creativity,
             "agents": body.agents.model_dump(), "style_pack": _pack(body.style_pack), "film_mode": body.film_mode,
             **_ambient(body.film_mode, body.venue, body.reel_s, body.loop_s),
             "images": _save_images(body.images)}
    if body.music_base64:
        brief["music_path"] = _save_music(body.music_base64, body.music_filename or "music.mp3")
    # v2: no credit before the SCRIPT gate; each gate grants what it asked for.
    run = await store.create_run(brief, {})
    # The project exists from the start, so the canvas can follow the director at work.
    name = re.sub(r"\s+", " ", body.text).strip()[:60]
    ids = await ingest.create_project(name, brief)
    # The idea waits on the canvas until the user asks for the script (approve gate IDEA).
    return await store.update_run(run["id"], project_id=ids["project_id"], plan={"ids": ids},
                                  status="WAITING_GATE", gate="IDEA")


@router.get("/runs")
async def list_runs(project_id: str | None = None):
    return await store.list_runs(project_id=project_id)


class AssistTarget(BaseModel):
    kind: Literal["scene", "character"]
    id: str


class AssistIn(BaseModel):
    project_id: str
    instruction: str = Field(min_length=2, max_length=4000)
    targets: list[AssistTarget] = Field(default=[], max_length=20)
    model: Literal["haiku", "sonnet", "opus"] | None = None


@router.post("/assist")
async def assist_nodes(body: AssistIn):
    """Canvas 'ask AI' bar: proposals for the selected nodes; the user applies them (no Flow credit)."""
    from agent.director import assist
    try:
        return await assist.ask(body.project_id, body.instruction, [t.model_dump() for t in body.targets], body.model)
    except brain.BrainError as e:
        raise HTTPException(502, str(e))


@router.get("/runs/{rid}/package")
async def get_package(rid: str):
    """The script package as three Markdown files (no AI call), also saved to phim/<project>/kich-ban/."""
    from agent.director import package
    run = await _run_or_404(rid)
    if not (run["plan"].get("story") and run["plan"].get("shotlist")):
        raise HTTPException(409, "the script is not written yet")
    project = await crud.get_project(run["project_id"]) if run.get("project_id") else None
    scenes = {}
    for shot_id, scene_id in ((run["plan"].get("ids") or {}).get("scenes") or {}).items():
        row = await crud.get_scene(scene_id)
        if row:
            scenes[shot_id] = row
    title = (project or {}).get("name") or run["brief"].get("text", "")[:60]
    files = package.build(run, title, scenes)
    folder = package.write(project, files) if project else None
    return {"folder": str(folder) if folder else None,
            "files": [{"name": n, "content": files[n]} for n in package.FILES]}


@router.get("/runs/{rid}")
async def get_run(rid: str):
    run = await _run_or_404(rid)
    run["steps"] = [{k: v for k, v in s.items() if k != "input"} for s in await store.list_steps(rid)]
    return run


@router.get("/runs/{rid}/timeline")
async def timeline(rid: str):
    """What the director has done so far, how long each step took, and how long steps usually take."""
    run = await _run_or_404(rid)
    steps = [{k: s[k] for k in ("stage", "attempt", "status", "duration_ms", "created_at")}
             for s in await store.list_steps(rid)]
    since = steps[-1]["created_at"] if steps else run.get("updated_at") or run.get("created_at")
    return {"status": run["status"], "stage": run["stage"], "gate": run["gate"],
            "edit_loops": (run.get("plan") or {}).get("edit_loops", 0), "since": since,
            "steps": steps, "typical_ms": await store.typical_stage_ms()}


@router.get("/runs/{rid}/log")
async def run_log(rid: str):
    """📋 Nhật ký: steps with their sent-back reasons, AI calls, Flow requests, gates — for the canvas side panel."""
    from agent.director import runlog
    return await runlog.build(await _run_or_404(rid))


@router.post("/runs/{rid}/approve")
async def approve(rid: str, body: Approve):
    await _run_or_404(rid)
    try:
        run = await pipeline.approve(rid, body.gate, body.budget, body.mode)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    runner.kick(rid)
    return run


AMBIENT_DEFAULT_REEL_S = 120   # the sample loops every 124.75s
AMBIENT_DEFAULT_LOOP_S = 1800  # the looped video, when the idea names no length (the sample runs 45 min)


def _ambient(mode: str | None, venue: str | None, reel_s: int | None, loop_s: int | None) -> dict:
    """An ambient idea names its venue and reel length (directive B14); other modes carry neither."""
    from agent.director import venues
    if venue and not venues.get(venue):
        raise HTTPException(422, f"unknown venue {venue!r}")
    if mode != "ambient":
        return {}
    return {"venue": venue or next(iter(venues.VENUES)), "reel_s": reel_s or AMBIENT_DEFAULT_REEL_S,
            "loop_s": loop_s or AMBIENT_DEFAULT_LOOP_S}


def _pack(pack_id: str | None) -> str | None:
    from agent.director import styles
    if pack_id and not styles.get(pack_id):
        raise HTTPException(422, f"unknown style pack {pack_id!r}")
    return pack_id or None


@router.get("/venues")
async def list_venues():
    """The live-performance venues of the ambient mode (directive B14), with their Vietnamese explanations."""
    from agent.director import venues
    return venues.catalog()


@router.get("/styles")
async def list_styles():
    """The style packs the user can pick on the idea (one look for the whole film)."""
    from agent.director import styles
    return styles.catalog()


@router.put("/runs/{rid}/agents")
async def set_agents(rid: str, body: Agents):
    """Turn optional roles on or off at any time (free): the change applies to the stages still to come."""
    run = await _run_or_404(rid)
    return await store.update_run(rid, brief=dict(run["brief"], agents=body.model_dump()))


@router.patch("/runs/{rid}/idea")
async def patch_idea(rid: str, body: IdeaPatch):
    run = await _run_or_404(rid)
    if run["gate"] != "IDEA":
        raise HTTPException(409, "the idea can only be edited before the script is written")
    brief = dict(run["brief"])
    brief.update(body.model_dump(exclude_none=True, exclude={"notes"}))
    if brief.get("film_mode") != "ambient":        # ambient choices live only on an ambient idea (directive B14)
        for k in ("venue", "reel_s", "loop_s"):
            brief.pop(k, None)
    brief.update(_ambient(brief.get("film_mode"), brief.get("venue"), brief.get("reel_s"), brief.get("loop_s")))
    if "style_pack" in body.model_fields_set:      # "" clears the choice: the director picks the look again
        brief["style_pack"] = _pack(body.style_pack)
    for img in brief.get("images") or []:
        if body.notes and img["file"] in body.notes:
            img["note"] = (body.notes[img["file"]] or "").strip() or None
    if body.text and run.get("project_id"):
        await crud.update_project(run["project_id"], name=re.sub(r"\s+", " ", body.text).strip()[:60])
    if body.film_mode and run.get("project_id"):
        await crud.update_project(run["project_id"], video_mode=ingest.video_mode_for(body.film_mode))
    return await store.update_run(rid, brief=brief)


@router.post("/runs/{rid}/refs")
async def make_missing_refs(rid: str):
    await _run_or_404(rid)
    try:
        run = await pipeline.make_missing_refs(rid)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    runner.kick(rid)
    return run


@router.post("/runs/{rid}/revise")
async def revise(rid: str, body: Revise):
    await _run_or_404(rid)
    try:
        run = await pipeline.revise(rid, body.feedback)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    runner.kick(rid)
    return run


@router.post("/runs/{rid}/shot-failure")
async def shot_failure(rid: str, body: ShotFailure):
    await _run_or_404(rid)
    try:
        run = await pipeline.resolve_shot_failure(rid, body.action)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    if run["status"] == "RUNNING":
        runner.kick(rid)
    return run


@router.post("/runs/{rid}/pause")
async def pause(rid: str):
    run = await _run_or_404(rid)
    if run["status"] not in ("RUNNING", "PAUSED"):   # pausing again still stops anything left in the queue
        raise HTTPException(409, "only running runs can be paused")
    run = await store.update_run(rid, status="PAUSED")
    await _stop_queued(run)
    return run


async def _stop_queued(run: dict) -> int:
    """Pause means nothing more goes to Flow: queued requests (never sent, or waiting to retry) are failed.
    Clips already generating finish and are kept. Resume re-requests what is missing."""
    pid = (run["plan"].get("ids") or {}).get("project_id")
    if not pid:
        return 0
    queued = await crud.list_requests(project_id=pid, status="PENDING")
    for r in queued:
        await crud.update_request(r["id"], status="FAILED", error_message=production.STOPPED)
    return len(queued)


@router.post("/runs/{rid}/cancel")
async def cancel(rid: str):
    """Stop a run for good: its task and Claude call end, nothing queued reaches Flow, no step can restart it.
    Clips Flow is already rendering finish on Flow's side and stay on the canvas."""
    run = await _run_or_404(rid)
    if run["status"] in ("DONE", "CANCELLED"):
        raise HTTPException(409, "run is already finished")
    await runner.cancel(rid)
    run = await store.update_run(rid, status="CANCELLED", gate=None, error="Đã huỷ theo yêu cầu.")
    await _stop_queued(run)
    return run


@router.post("/runs/{rid}/resume")
async def resume(rid: str):
    run = await _run_or_404(rid)
    if run["status"] != "PAUSED":
        raise HTTPException(409, "run is not paused")
    run = await store.update_run(rid, status="RUNNING")
    runner.kick(rid)
    return run


@router.post("/runs/{rid}/retry")
async def retry(rid: str):
    run = await _run_or_404(rid)
    if run["status"] != "FAILED":
        raise HTTPException(409, "only failed runs can be retried")
    run = await store.update_run(rid, status="RUNNING", error=None)
    runner.kick(rid)
    return run


@router.patch("/runs/{rid}/shots/{shot_id}")
async def patch_shot(rid: str, shot_id: str, body: ShotPatch):
    run = await _run_or_404(rid)
    if run["gate"] != "SCRIPT":
        raise HTTPException(409, "shots can only be edited at the script gate")
    plan = copy.deepcopy(run["plan"])   # edit a copy; the stored plan changes only if lint passes
    shots, prompts = plan["shotlist"]["shots"], plan["prompts"]["prompts"]
    shot = next((s for s in shots if s["id"] == shot_id), None)
    prompt = next((p for p in prompts if p["shot_id"] == shot_id), None)
    if not shot or not prompt:
        raise HTTPException(404, "shot not found")
    upd = body.model_dump(exclude_none=True)
    shot.update({k: upd[k] for k in ("mode", "duration_s", "commands") if k in upd})
    prompt.update({k: upd[k] for k in ("video_prompt", "keyframe_prompt") if k in upd})
    story, sl, sp = Story.model_validate(plan["story"]), ShotList.model_validate(plan["shotlist"]), \
        ShotPrompts.model_validate(plan["prompts"])
    issues = lint.errors(lint.lint_shotlist(sl, story, plan["brief"]["target_s"], plan["brief"].get("language", "en"),
                                            plan["brief"].get("film_mode", "cut"))
                         + lint.lint_prompts(sp, sl, story, None, plan["brief"].get("film_mode", "cut")))
    if issues:
        raise HTTPException(422, [i.__dict__ for i in issues])
    run = await store.update_run(rid, plan=plan)
    await ingest.sync_scenes(run)
    return run


class Rewrite(BaseModel):
    feedback: str = Field(default="", max_length=2000)
    review: dict | None = None      # the video review (score, errors with time ranges): rewrite from its findings

    @model_validator(mode="after")
    def _something_to_fix(self):
        if len(self.feedback.strip()) < 2 and not (self.review or {}).get("errors"):
            raise ValueError("say what to change, or pass a review with errors")
        return self


@router.post("/runs/{rid}/shots/{shot_id}/rewrite")
async def rewrite_shot(rid: str, shot_id: str, body: Rewrite):
    """Claude rewrites one clip's prompt from the user's words; nothing is applied or spent yet."""
    await _run_or_404(rid)
    try:
        return await pipeline.rewrite_shot(rid, shot_id, body.feedback.strip(), body.review)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    except pipeline.StageFailed as e:
        raise HTTPException(422, str(e)) from e


@router.post("/runs/{rid}/shots/{shot_id}/apply-rewrite")
async def apply_rewrite(rid: str, shot_id: str):
    await _run_or_404(rid)
    try:
        return await pipeline.apply_rewrite(rid, shot_id)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/effects")
async def effects_catalog():
    """Looks, transitions and clip effects the editor can use (CapCut-style, rebuilt in ffmpeg)."""
    from agent.director import effects
    return {kind: [{"id": k, "label": v.label, "use": v.use} for k, v in table.items()]
            for kind, table in (("looks", effects.LOOKS), ("transitions", effects.TRANSITIONS),
                                ("fx", effects.CLIP_FX))}


@router.get("/runs/{rid}/edit")
async def get_edit(rid: str):
    run = await _run_or_404(rid)
    if not run["plan"].get("shotlist"):
        raise HTTPException(409, "no script yet")
    return pipeline.current_edit(run["plan"])


class EditBody(BaseModel):
    look: str | None = None
    clips: list[dict] = []


@router.put("/runs/{rid}/edit")
async def put_edit(rid: str, body: EditBody):
    """Save the effects the user picked (free); 🎬 Dựng lại phim applies them."""
    await _run_or_404(rid)
    try:
        return await pipeline.save_edit(rid, body.model_dump())
    except LookupError as e:
        raise HTTPException(409, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/runs/{rid}/recut")
async def recut(rid: str):
    """Re-cut the film from the scenes' current takes, in the background (about a minute)."""
    run = await _run_or_404(rid)
    if run["status"] == "RUNNING":
        raise HTTPException(409, "the director is busy")
    if not run["plan"].get("qc") and (missing := await pipeline.clips_missing(run)):
        raise HTTPException(409, f"chưa có video cho cảnh {', '.join(map(str, missing))}")
    run = await store.update_run(rid, status="RUNNING", stage="CUT", error=None, gate=None)

    async def job():
        try:
            await pipeline.recut(rid)
        except Exception as e:  # noqa: BLE001 — surface any failure on the film node
            await store.update_run(rid, status="FAILED", error=f"{type(e).__name__}: {e}")
    spawn(job(), name=f"recut:{rid[:8]}")
    return run


class FilmReviewBody(BaseModel):
    note: str = ""


@router.post("/runs/{rid}/film-review")
async def film_review_start(rid: str, body: FilmReviewBody):
    """Agent Review: judge the cut film (script, clips, seams, causes) in the background. Claude only, no credit."""
    from agent.director import film_review
    run = await _run_or_404(rid)
    if not run.get("final_path") or not run["plan"].get("shotlist"):
        raise HTTPException(409, "the film has not been cut yet")
    try:
        return film_review.start(rid, body.note)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/runs/{rid}/film-review")
async def film_review_list(rid: str):
    from agent.director import film_review
    await _run_or_404(rid)
    return {"job": film_review.job(rid), "reviews": film_review.list_reviews(rid)}


@router.get("/lessons")
async def list_lessons():
    return await store.list_lessons()


@router.patch("/lessons/{lid}")
async def patch_lesson(lid: str, body: LessonPatch):
    if not await store.get_lesson(lid):
        raise HTTPException(404, "lesson not found")
    return await store.update_lesson(lid, status=body.status)
