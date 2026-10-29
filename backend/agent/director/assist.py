"""The canvas "ask AI" bar (learned from the SciCloud sample, 19/10): the user selects nodes, writes what they want,
and gets proposed edits to apply. Free of Flow credit; nothing is changed until the user applies it."""
import re

from agent.db import crud
from agent.director import brain, store
from agent.director.schemas import AssistReply

MODELS = {"haiku", "sonnet", "opus"}
SPINE = ("synopsis", "story_line", "message", "viewer_value", "director_notes")


async def _targets(targets: list[dict]) -> list[dict]:
    out = []
    for t in targets:
        if t["kind"] == "scene" and (row := await crud.get_scene(t["id"])):
            out.append({"kind": "scene", "id": row["id"], "order": row.get("display_order", 0) + 1,
                        "prompt": row.get("prompt"), "video_prompt": row.get("video_prompt"),
                        "cast": row.get("character_names") or []})
        elif t["kind"] == "character" and (row := await crud.get_character(t["id"])):
            out.append({"kind": "character", "id": row["id"], "name": row["name"],
                        "entity_type": row.get("entity_type"), "description": row.get("description"),
                        "image_prompt": row.get("image_prompt")})
    return out


_SCENE_NO = re.compile(r"(?:cảnh|canh|scene|shot|clip)\s*(?:số\s*)?(\d{1,3})", re.I)


async def _scenes(project_id: str) -> list[dict]:
    out = []
    for v in await crud.list_videos(project_id):
        out += await crud.list_scenes(v["id"])
    return sorted(out, key=lambda r: r.get("display_order", 0))


async def _by_number(project_id: str, instruction: str, scenes: list[dict]) -> list[dict]:
    """19/10: the user wrote "cảnh 7 … cảnh 8" and the bar answered "select scenes 7 and 8 and send again". A scene
    named by its number IS a target."""
    wanted = {int(n) for n in _SCENE_NO.findall(instruction)}
    return [{"kind": "scene", "id": r["id"]} for r in scenes if r.get("display_order", 0) + 1 in wanted]


def _neighbours(found: list[dict], scenes: list[dict]) -> list[dict]:
    """Read-only context: the clip before and after each target, so a fix keeps the film continuous (directive B11)."""
    orders = {t["order"] for t in found if t["kind"] == "scene"}
    near = {o + d for o in orders for d in (-1, 1)} - orders
    return [{"order": r.get("display_order", 0) + 1, "prompt": r.get("prompt"), "video_prompt": r.get("video_prompt")}
            for r in scenes if r.get("display_order", 0) + 1 in near]


async def _film(project_id: str) -> dict:
    runs = [r for r in await store.list_runs(project_id=project_id) if r["plan"].get("story")]
    if not runs:
        return {}
    plan = sorted(runs, key=lambda r: r.get("created_at") or "")[-1]["plan"]
    brief = plan.get("brief") or {}
    return {"language": brief.get("language", "en"), "orientation": brief.get("orientation"),
            "voice": brief.get("voice"), **{k: plan["story"].get(k) for k in SPINE if plan["story"].get(k)}}


async def ask(project_id: str, instruction: str, targets: list[dict], model: str | None = None) -> dict:
    scenes = await _scenes(project_id)
    named = [t for t in await _by_number(project_id, instruction, scenes)
             if (t["kind"], t["id"]) not in {(x["kind"], x["id"]) for x in targets}]
    found = await _targets(list(targets) + named)
    reply = await brain.think("assistant", {"instruction": instruction, "targets": found,
                                            "neighbours": _neighbours(found, scenes),
                                            "film": await _film(project_id)},
                              AssistReply, model=model if model in MODELS else None)
    allowed = {(t["kind"], t["id"]) for t in found}
    changes = [c.model_dump() for c in reply.changes if (c.kind, c.id) in allowed
               and (c.kind == "scene") == (c.field in ("video_prompt", "prompt"))]
    return {"answer": reply.answer, "changes": changes}
