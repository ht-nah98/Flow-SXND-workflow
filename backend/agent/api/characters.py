from fastapi import APIRouter, HTTPException
from agent.models.character import Character, CharacterCreate, CharacterUpdate
from agent.sdk.persistence.sqlite_repository import SQLiteRepository
from agent.utils.slugify import slugify

router = APIRouter(prefix="/characters", tags=["characters"])


def _get_repo() -> SQLiteRepository:
    return SQLiteRepository()


@router.post("", response_model=Character)
async def create(body: CharacterCreate):
    repo = _get_repo()
    return await repo.create_character(**body.model_dump(exclude_none=True))


@router.get("", response_model=list[Character])
async def list_all():
    repo = _get_repo()
    rows = await repo.list("character", order_by="created_at DESC")
    return [repo._row_to_character(r) for r in rows]


@router.get("/{cid}", response_model=Character)
async def get(cid: str):
    repo = _get_repo()
    c = await repo.get_character(cid)
    if not c:
        raise HTTPException(404, "Character not found")
    return c


@router.patch("/{cid}", response_model=Character)
async def update(cid: str, body: CharacterUpdate):
    repo = _get_repo()
    updates = body.model_dump(exclude_unset=True)
    before = None
    if "name" in updates:
        updates["slug"] = slugify(updates["name"])
        before = await repo.get_character(cid)
        from agent.api.assets import find_rename_collision
        hit = await find_rename_collision(cid, updates["name"], updates["slug"])
        if hit:
            raise HTTPException(409, f"name collides with character '{hit[0]}' in project '{hit[1]}'")
    row = await repo.update("character", cid, **updates)
    if not row:
        raise HTTPException(404, "Character not found")
    # FK-LOCAL: keep scene references valid when an asset is renamed
    if before is not None and before.name != updates["name"]:
        from agent.api.assets import _rename_in_scenes, project_ids_for_character
        await _rename_in_scenes(await project_ids_for_character(cid), before.name, updates["name"],
                                before.slug)
    return repo._row_to_character(row)


@router.delete("/{cid}")
async def delete(cid: str):
    repo = _get_repo()
    if not await repo.delete_character(cid):
        raise HTTPException(404, "Character not found")
    return {"ok": True}
