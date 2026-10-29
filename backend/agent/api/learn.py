"""Learn from sample videos: upload → analysis (Claude reads the frames) → the user adopts techniques."""

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent.director import learn
from agent.utils.tasks import spawn

router = APIRouter(prefix="/learn", tags=["learn"])
MAX_BYTES = 300 * 1024 * 1024
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


def _start(sid: str) -> None:
    spawn(learn.analyze(sid), name=f"learn:{sid[:8]}")


@router.post("/samples", status_code=201)
async def upload_sample(file: UploadFile):
    name = file.filename or "mau.mp4"
    if not any(name.lower().endswith(e) for e in VIDEO_EXT):
        raise HTTPException(422, "chỉ nhận video mp4, mov, webm, mkv")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "video quá lớn (tối đa 300 MB)")
    meta = learn.save_upload(name, data)
    _start(meta["id"])
    return meta


@router.get("/samples")
async def list_samples():
    return learn.list_samples()


@router.get("/samples/{sid}")
async def get_sample(sid: str):
    meta = learn.read_meta(sid)
    if not meta:
        raise HTTPException(404, "sample not found")
    a = learn.read_analysis(sid)
    return meta | {"analysis": a.model_dump() if a else None}


@router.get("/samples/{sid}/video")
async def sample_video(sid: str):
    meta = learn.read_meta(sid)
    if not meta:
        raise HTTPException(404, "sample not found")
    return FileResponse(meta["video"])


@router.post("/samples/{sid}/retry")
async def retry_sample(sid: str):
    if not learn.read_meta(sid):
        raise HTTPException(404, "sample not found")
    meta = learn._write_meta(sid, status="ANALYZING", error=None)
    _start(sid)
    return meta


class Adopt(BaseModel):
    techniques: list[int]


@router.post("/samples/{sid}/adopt")
async def adopt(sid: str, body: Adopt):
    try:
        return await learn.adopt(sid, body.techniques)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
