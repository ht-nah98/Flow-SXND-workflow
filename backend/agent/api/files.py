"""FK-LOCAL: serve generated files (e.g. concat output) under OUTPUT_DIR only."""
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from agent.config import OUTPUT_DIR

router = APIRouter(tags=["files"])


@router.get("/files")
async def get_file(path: str):
    raw = unquote(urlparse(path).path) if path.startswith("file://") else path
    target = Path(raw).resolve()
    root = Path(OUTPUT_DIR).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(403, "path outside FlowKit output directory")
    if not target.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(target)
