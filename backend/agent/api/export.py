"""FK-LOCAL: download a project's current media locally and zip it for sharing.

Generated images/videos live only as remote Flow signed URLs until this runs
— nothing is persisted to disk otherwise, and those URLs expire. This walks
every character and scene the project currently references, copies their
latest (not historical) media into output/<project-slug>/, and zips the
result for a single shareable file.
"""
import shutil
import urllib.request
import zipfile
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

from agent.utils.paths import project_folder
from agent.config import OUTPUT_DIR
from agent.db import crud
from agent.utils.paths import file_url_to_path
from agent.utils.slugify import slugify

router = APIRouter(tags=["export"])

_IMAGE_EXT_FALLBACK = ".jpg"
_VIDEO_EXT_FALLBACK = ".mp4"


def _ext(url: str, fallback: str) -> str:
    suffix = Path(urlparse(url).path).suffix
    return suffix if suffix else fallback


def _download(url: str, dest: Path) -> bool:
    """Copy/download a media URL to dest. Returns False (no exception) on failure."""
    local = file_url_to_path(url)
    if local is not None:
        if not local.is_file():
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, dest)
        return True
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception:
        return False


async def _export_character(char: dict, project_dir: Path, downloaded: list, skipped: list) -> None:
    url = char.get("reference_image_url")
    if not url:
        return
    dest = project_dir / "characters" / f"{char.get('slug') or slugify(char['name'])}{_ext(url, _IMAGE_EXT_FALLBACK)}"
    if _download(url, dest):
        downloaded.append(dest)
    else:
        skipped.append({"kind": "character", "id": char["id"], "name": char["name"], "reason": "unreachable or expired"})


async def _export_scene_media(scene: dict, orientation: str, project_dir: Path,
                              downloaded: list, skipped: list) -> None:
    p = orientation.lower()
    order = scene["display_order"]
    sid = scene["id"]
    for kind, fallback in (("image", _IMAGE_EXT_FALLBACK), ("video", _VIDEO_EXT_FALLBACK)):
        url = scene.get(f"{p}_{kind}_url")
        if not url:
            continue
        dest = project_dir / "scenes" / p / f"scene_{order:03d}_{sid}_{kind}{_ext(url, fallback)}"
        if _download(url, dest):
            downloaded.append(dest)
        else:
            skipped.append({"kind": f"scene_{kind}", "id": sid, "orientation": orientation,
                           "reason": "unreachable or expired"})


def _zip_project_dir(project_dir: Path, slug: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    zip_dir = project_dir / "_export"
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_path = zip_dir / f"{slug}-{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in project_dir.rglob("*"):
            if f.is_file() and zip_dir not in f.parents:
                zf.write(f, f.relative_to(project_dir))
    return zip_path


@router.post("/projects/{pid}/export")
async def export_project(pid: str):
    project = await crud.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")

    slug = project_folder(project)
    project_dir = OUTPUT_DIR / slug
    downloaded: list[Path] = []
    skipped: list[dict] = []

    for char in await crud.get_project_characters(pid):
        await _export_character(char, project_dir, downloaded, skipped)

    for video in await crud.list_videos(pid):
        orientation = video.get("orientation") or "HORIZONTAL"
        for scene in await crud.list_scenes(video["id"]):
            await _export_scene_media(scene, orientation, project_dir, downloaded, skipped)

    project_dir.mkdir(parents=True, exist_ok=True)
    zip_path = _zip_project_dir(project_dir, slug)

    return {
        "project_dir": "file://" + str(project_dir.resolve()),
        "zip_path": "file://" + str(zip_path.resolve()),
        "downloaded": len(downloaded),
        "skipped": skipped,
    }
