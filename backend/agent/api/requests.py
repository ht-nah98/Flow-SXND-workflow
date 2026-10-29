from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agent.models.request import Request, RequestCreate
from agent.models.enums import StatusType
from agent.db import crud

router = APIRouter(prefix="/requests", tags=["requests"])


class RequestUpdate(BaseModel):
    status: StatusType | None = None
    media_id: str | None = None
    output_url: str | None = None
    error_message: str | None = None
    request_id: str | None = None


class BatchRequestCreate(BaseModel):
    requests: list[RequestCreate]


class BatchStatus(BaseModel):
    total: int
    pending: int
    processing: int
    completed: int
    failed: int
    done: bool
    all_succeeded: bool
    orientation: str | None = None


# Scene requests that go through a first-frame image. A project in "refs" mode (the default, directive D1:
# prompt + asset references) never makes them, so a stray click or an old script cannot spend credit on them.
IMAGE_FIRST_TYPES = {"GENERATE_IMAGE", "REGENERATE_IMAGE", "EDIT_IMAGE", "GENERATE_VIDEO", "REGENERATE_VIDEO"}
REFS_MODE_MSG = ("Dự án đang ở chế độ 'prompt + asset' (không tạo ảnh trước). "
                 "Muốn làm video từ ảnh thì bật chế độ 'Ảnh → video' của dự án.")


async def _check_video_mode(items: list[RequestCreate]) -> None:
    modes: dict[str, str] = {}
    for item in items:
        if item.type not in IMAGE_FIRST_TYPES or not item.project_id or not item.scene_id:
            continue
        if item.project_id not in modes:
            project = await crud.get_project(item.project_id)
            modes[item.project_id] = (project or {}).get("video_mode") or "refs"
        if modes[item.project_id] == "refs":
            raise HTTPException(409, REFS_MODE_MSG)


REGEN_AS_GENERATE = ("GENERATE_VIDEO", "GENERATE_VIDEO_REFS")


async def _reopen_finished_video(data: dict) -> None:
    """FK-LOCAL (19/10): "Gen lại video" on a scene that already has a video arrives as GENERATE_VIDEO(_REFS), and the
    worker skips a generate whose scene is COMPLETED — it copied the old clip as "version 2" and spent nothing. A new
    request for a finished scene IS a regeneration: reopen the scene (as the director's QC regen does)."""
    if data.get("req_type") not in REGEN_AS_GENERATE or not data.get("scene_id"):
        return
    scene = await crud.get_scene(data["scene_id"])
    orient = data.get("orientation")
    if not orient and data.get("video_id"):
        orient = ((await crud.get_video(data["video_id"])) or {}).get("orientation")
    prefix = "vertical" if orient == "VERTICAL" else "horizontal"
    if scene and scene.get(f"{prefix}_video_status") == "COMPLETED":
        await crud.update_scene(scene["id"], **{f"{prefix}_video_status": "PENDING"})


@router.post("", response_model=Request)
async def create(body: RequestCreate):
    await _check_video_mode([body])
    data = body.model_dump(exclude_none=True)
    data["req_type"] = data.pop("type")

    scene_id = data.get("scene_id")
    req_type = data.get("req_type")
    orient = data.get("orientation")
    if scene_id and req_type:
        existing = await crud.list_requests(scene_id=scene_id)
        active = [r for r in existing
                  if r.get("type") == req_type
                  and (not orient or r.get("orientation") == orient)
                  and r.get("status") in ("PENDING", "PROCESSING")]
        if active:
            raise HTTPException(
                409,
                f"Active {req_type} request already exists for scene {scene_id[:8]} "
                f"(status={active[0]['status']}, id={active[0]['id'][:8]})"
            )

    # Auto-set video orientation (symmetric with batch endpoint)
    vid = data.get("video_id")
    orient = data.get("orientation")
    if vid and orient:
        await crud.update_video(vid, orientation=orient)

    await _reopen_finished_video(data)
    return await crud.create_request(**data)


@router.post("/batch", response_model=list[Request])
async def create_batch(body: BatchRequestCreate):
    """Submit multiple requests atomically. Server handles throttling (max 5 concurrent, 10s cooldown).
    Duplicate active requests for the same scene+type are skipped (not errors)."""
    await _check_video_mode(body.requests)
    # Auto-set video orientation from the batch (tracks current active orientation)
    _seen_vids: set[str] = set()
    for item in body.requests:
        vid = item.video_id
        orient = item.orientation
        if vid and orient and vid not in _seen_vids:
            _seen_vids.add(vid)
            await crud.update_video(vid, orientation=orient)
    results = []
    for item in body.requests:
        data = item.model_dump(exclude_none=True)
        data["req_type"] = data.pop("type")
        scene_id = data.get("scene_id")
        character_id = data.get("character_id")
        req_type = data.get("req_type")
        orient = data.get("orientation")
        # Idempotent: skip if active request already exists
        if scene_id and req_type:
            existing = await crud.list_requests(scene_id=scene_id)
            active = [r for r in existing
                      if r.get("type") == req_type
                      and (not orient or r.get("orientation") == orient)
                      and r.get("status") in ("PENDING", "PROCESSING")]
            if active:
                results.append(active[0])
                continue
        if character_id and req_type:
            existing = await crud.list_requests(project_id=data.get("project_id"))
            active = [r for r in existing
                      if r.get("character_id") == character_id
                      and r.get("type") == req_type
                      and r.get("status") in ("PENDING", "PROCESSING")]
            if active:
                results.append(active[0])
                continue
        await _reopen_finished_video(data)
        results.append(await crud.create_request(**data))
    return results


@router.get("", response_model=list[Request])
async def list_all(scene_id: str = None, status: str = None,
                   video_id: str = None, project_id: str = None):
    return await crud.list_requests(scene_id=scene_id, status=status,
                                    video_id=video_id, project_id=project_id)


@router.get("/pending", response_model=list[Request])
async def list_pending():
    return await crud.list_pending_requests()


@router.get("/batch-status", response_model=BatchStatus)
async def batch_status(video_id: str = None, project_id: str = None,
                       type: str = None, orientation: str = None):
    """Aggregate status for all requests matching the filter.
    Poll this instead of polling N individual request IDs."""
    rows = await crud.list_requests(video_id=video_id, project_id=project_id)
    if type:
        rows = [r for r in rows if r.get("type") == type]
    if orientation:
        rows = [r for r in rows if r.get("orientation") == orientation]
    counts = {"PENDING": 0, "PROCESSING": 0, "COMPLETED": 0, "FAILED": 0}
    for r in rows:
        s = r.get("status", "PENDING")
        counts[s] = counts.get(s, 0) + 1
    total = len(rows)
    return BatchStatus(
        total=total,
        pending=counts["PENDING"],
        processing=counts["PROCESSING"],
        orientation=orientation,
        completed=counts["COMPLETED"],
        failed=counts["FAILED"],
        done=(counts["PENDING"] == 0 and counts["PROCESSING"] == 0),
        all_succeeded=(counts["COMPLETED"] == total and total > 0),
    )


@router.get("/{rid}", response_model=Request)
async def get(rid: str):
    r = await crud.get_request(rid)
    if not r:
        raise HTTPException(404, "Request not found")
    return r


@router.patch("/{rid}", response_model=Request)
async def update(rid: str, body: RequestUpdate):
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "No fields to update")
    r = await crud.update_request(rid, **data)
    if not r:
        raise HTTPException(404, "Request not found")
    return r
