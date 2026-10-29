"""FK-LOCAL: versions, restore, upload, usage, clone for canvas assets and scenes."""
import json
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from agent.api.flow import _upload_image_bytes
from agent.db import crud
from agent.services.flow_client import get_flow_client
from agent.services.versions import (CHARACTER_TYPES, IMAGE_TYPES, VIDEO_TYPES,
                                     list_versions)
from agent.utils.slugify import slugify
from datetime import UTC

router = APIRouter(tags=["assets"])


class CharacterRestore(BaseModel):
    request_id: str
    restore_prompt: bool = False


class SceneRestore(BaseModel):
    request_id: str
    kind: Literal["image", "video"]
    orientation: Literal["HORIZONTAL", "VERTICAL"]
    restore_prompt: bool = False


class CloneIn(BaseModel):
    project_id: str


async def _signed_image_url(client, media_id: str) -> str | None:
    from agent.services import flow_batch as fb
    res = await client.batch_rpc(fb.RPC_MEDIA, fb.media_request(media_id))
    raw = res.get("data") or ""
    if not raw:
        return None
    urls = fb.read_media_urls(fb.first_payload(raw, fb.RPC_MEDIA), media_id)
    return urls.image if urls else None


def _names(raw) -> list[str]:
    if not raw:
        return []
    return raw if isinstance(raw, list) else json.loads(raw)


async def _rename_in_scenes(project_ids: list[str], old: str, new: str,
                            old_slug: str | None = None) -> None:
    """Rewrite references to an asset. FlowKit matches character_names by name OR slug."""
    aliases = {old} | ({old_slug} if old_slug else set())
    db = await crud.get_db()
    for pid in project_ids:
        cur = await db.execute(
            "SELECT s.id, s.character_names FROM scene s JOIN video v ON s.video_id=v.id WHERE v.project_id=?",
            (pid,))
        for row in await cur.fetchall():
            names = _names(row["character_names"])
            if aliases & set(names):
                await crud.update_scene(row["id"], character_names=json.dumps(
                    [new if n in aliases else n for n in names]))


async def project_ids_for_character(cid: str) -> list[str]:
    db = await crud.get_db()
    cur = await db.execute("SELECT project_id FROM project_character WHERE character_id=?", (cid,))
    return [r["project_id"] for r in await cur.fetchall()]


async def find_rename_collision(cid: str, name: str, slug: str) -> tuple[str, str] | None:
    """(other character name, project name) if name/slug equals another character's name/slug in a shared project."""
    wanted = {name, slug}
    for pid in await project_ids_for_character(cid):
        for other in await crud.get_project_characters(pid):
            if other["id"] != cid and wanted & {other["name"], other.get("slug")}:
                proj = await crud.get_project(pid)
                return other["name"], (proj or {}).get("name", pid)
    return None


async def _record_upload(cid: str, project_id: str | None, media_id: str,
                         url: str | None, file_name: str) -> None:
    """Insert the upload's history row already COMPLETED, in one statement.

    request.type has a CHECK constraint without an UPLOAD type, so the row is an
    EDIT_CHARACTER_IMAGE tagged "upload: <file>". It must never exist as PENDING:
    the worker would pick it up and run a real (credit-spending) Flow edit.
    """
    import uuid
    from datetime import datetime
    from agent.config import DEFAULT_PROVIDER
    from agent.db.schema import _db_lock
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    db = await crud.get_db()
    async with _db_lock:
        await db.execute(
            """INSERT INTO request (id,project_id,character_id,type,status,media_id,output_url,
                                    provider,prompt_snapshot,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (str(uuid.uuid4()), project_id, cid, "EDIT_CHARACTER_IMAGE", "COMPLETED", media_id, url,
             DEFAULT_PROVIDER, f"upload: {file_name}", now, now))
        await db.commit()


@router.get("/characters/{cid}/versions")
async def character_versions(cid: str):
    return await list_versions(character_id=cid, types=CHARACTER_TYPES)


@router.get("/scenes/{sid}/versions")
async def scene_versions(sid: str, kind: Literal["image", "video"], orientation: str):
    return await list_versions(scene_id=sid, orientation=orientation,
                               types=IMAGE_TYPES if kind == "image" else VIDEO_TYPES)


@router.post("/characters/{cid}/restore")
async def restore_character(cid: str, body: CharacterRestore):
    req = await crud.get_request(body.request_id)
    if not req or req.get("character_id") != cid or req.get("status") != "COMPLETED":
        raise HTTPException(404, "version not found for this asset")
    updates = {"media_id": req["media_id"], "reference_image_url": req["output_url"]}
    snap = req.get("prompt_snapshot")
    if body.restore_prompt and snap and not snap.startswith("upload:"):
        updates["image_prompt"] = snap
    return await crud.update_character(cid, **updates)


@router.post("/scenes/{sid}/restore")
async def restore_scene(sid: str, body: SceneRestore):
    req = await crud.get_request(body.request_id)
    types = IMAGE_TYPES if body.kind == "image" else VIDEO_TYPES
    if (not req or req.get("scene_id") != sid or req.get("type") not in types
            or req.get("status") != "COMPLETED"):
        raise HTTPException(404, "version not found for this scene")
    scene = await crud.get_scene(sid)
    p = body.orientation.lower()
    updates = {
        f"{p}_{body.kind}_media_id": req["media_id"],
        f"{p}_{body.kind}_url": req["output_url"],
        f"{p}_{body.kind}_status": "COMPLETED",
        f"{p}_upscale_url": None, f"{p}_upscale_media_id": None, f"{p}_upscale_status": "PENDING",
    }
    if body.kind == "image":
        updates.update({f"{p}_video_url": None, f"{p}_video_media_id": None,
                        f"{p}_video_status": "PENDING"})
    snap = req.get("prompt_snapshot")
    if body.restore_prompt and snap:
        if body.kind == "video":
            updates["video_prompt"] = snap
        elif scene.get("image_prompt"):
            updates["image_prompt"] = snap
        else:
            updates["prompt"] = snap
    return await crud.update_scene(sid, **updates)


@router.post("/characters/{cid}/upload")
async def upload_character_image(cid: str, file: UploadFile = File(...),
                                 project_id: str = Form(default="")):
    if not await crud.get_character(cid):
        raise HTTPException(404, "Character not found")
    client = get_flow_client()
    if not client.connected:
        raise HTTPException(503, "Extension not connected")
    data = await file.read()
    name = file.filename or "image.png"
    mime = file.content_type or "image/png"
    up = await _upload_image_bytes(client, data, project_id=project_id, mime_type=mime, file_name=name)
    url = await _signed_image_url(client, up["media_id"])
    await _record_upload(cid, project_id or None, up["media_id"], url, name)
    return await crud.update_character(cid, media_id=up["media_id"], reference_image_url=url)


@router.get("/characters/{cid}/projects")
async def character_projects(cid: str):
    out = []
    for pid in await project_ids_for_character(cid):
        p = await crud.get_project(pid)
        if p:
            out.append({"id": p["id"], "name": p["name"]})
    return out


@router.post("/characters/{cid}/clone")
async def clone_character(cid: str, body: CloneIn):
    src = await crud.get_character(cid)
    if not src:
        raise HTTPException(404, "Character not found")
    taken = {v for c in await crud.list_characters() for v in (c["name"], c.get("slug"))}
    n = 2
    while f"{src['name']} ({n})" in taken or slugify(f"{src['name']} ({n})") in taken:
        n += 1
    name = f"{src['name']} ({n})"
    new = await crud.create_character(
        name=name, slug=slugify(name), entity_type=src["entity_type"], description=src.get("description"),
        image_prompt=src.get("image_prompt"), voice_description=src.get("voice_description"),
        reference_image_url=src.get("reference_image_url"), media_id=src.get("media_id"))
    await crud.link_character_to_project(body.project_id, new["id"])
    await crud.unlink_character_from_project(body.project_id, cid)
    await _rename_in_scenes([body.project_id], src["name"], new["name"], src.get("slug"))
    return new
