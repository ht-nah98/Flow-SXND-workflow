"""FK-LOCAL: prompt snapshots + version listing for canvas history."""

from agent.db import crud

IMAGE_TYPES = ("GENERATE_IMAGE", "REGENERATE_IMAGE", "EDIT_IMAGE")
VIDEO_TYPES = ("GENERATE_VIDEO", "REGENERATE_VIDEO", "GENERATE_VIDEO_REFS")
CHARACTER_TYPES = ("GENERATE_CHARACTER_IMAGE", "REGENERATE_CHARACTER_IMAGE",
                   "EDIT_CHARACTER_IMAGE")


async def compute_prompt_snapshot(req_type: str, scene_id: str | None,
                                  character_id: str | None,
                                  orientation: str | None) -> str | None:
    if req_type in CHARACTER_TYPES and character_id:
        c = await crud.get_character(character_id)
        return (c.get("image_prompt") or c.get("description")) if c else None
    if not scene_id:
        return None
    s = await crud.get_scene(scene_id)
    if not s:
        return None
    if req_type in IMAGE_TYPES:
        return s.get("image_prompt") or s.get("prompt")
    if req_type in VIDEO_TYPES:
        prefix = (orientation or "HORIZONTAL").lower()
        if s.get(f"{prefix}_end_scene_media_id") and s.get("transition_prompt"):
            return s["transition_prompt"]
        return s.get("video_prompt")
    return None


async def list_versions(*, scene_id: str | None = None, character_id: str | None = None,
                        types: tuple[str, ...], orientation: str | None = None) -> list[dict]:
    db = await crud.get_db()
    q = (f"SELECT * FROM request WHERE status='COMPLETED' AND media_id IS NOT NULL "
         f"AND type IN ({','.join('?' * len(types))})")
    params: list = list(types)
    if scene_id:
        q += " AND scene_id=?"; params.append(scene_id)
    if character_id:
        q += " AND character_id=?"; params.append(character_id)
    if orientation:
        q += " AND orientation=?"; params.append(orientation)
    q += " ORDER BY updated_at DESC, created_at DESC LIMIT 50"
    cur = await db.execute(q, params)
    return [{
        "request_id": r["id"], "type": r["type"], "media_id": r["media_id"],
        "output_url": r["output_url"], "prompt_snapshot": r["prompt_snapshot"],
        "created_at": r["created_at"], "updated_at": r["updated_at"],
    } for r in await cur.fetchall()]
