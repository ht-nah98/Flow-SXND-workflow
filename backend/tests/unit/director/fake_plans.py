from tests.unit.director.fixtures import fmv_prompts, fmv_shotlist, fmv_story


def fake_responses(target_s: int = 15, editor_score: int = 90) -> dict[str, list[dict]]:
    shots = fmv_shotlist().model_dump()
    return {
        "producer": [{"logline": "Two lovers bake, then part.", "genre": "romance", "tone": "bittersweet",
                      "target_s": target_s, "orientation": "HORIZONTAL", "material": "realistic", "language": "vi"}],
        "writer": [fmv_story().model_dump()],
        "director": [shots],
        "dp": [fmv_prompts().model_dump()],
        "editor": [{"score": editor_score, "checklist": {"story": True}, "fixes": []}],
        "qc": [{"items": [{"shot_id": s["id"], "verdict": "PASS", "issues": [], "trim_in_s": 0.5,
                           "trim_out_s": s["duration_s"] - 0.3} for s in shots["shots"]]}],
        "coach": [{"lessons": []}],
    }


async def finish(rid: str, status: str = "COMPLETED"):
    """Settle a request the way the real worker does: a finished reference image lands on its entity."""
    from agent.db import crud
    await crud.update_request(rid, status=status)
    row = await crud.get_request(rid)
    if status == "COMPLETED" and row.get("character_id"):
        await crud.update_character(row["character_id"], media_id=f"media-{rid[:8]}")
    if status == "COMPLETED" and row.get("type") == "GENERATE_IMAGE" and row.get("scene_id"):   # a keyframe still
        await crud.update_scene(row["scene_id"], horizontal_image_media_id=f"key-{rid[:8]}",
                                horizontal_image_status="COMPLETED")
    return row
