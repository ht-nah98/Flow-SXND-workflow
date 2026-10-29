import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api.assets import router as assets_router
from agent.api.characters import router as characters_router
from agent.db import crud
from agent.services.versions import compute_prompt_snapshot
from agent.utils.slugify import slugify

MEDIA = "99999999-8888-7777-6666-555555555555"


@pytest.fixture
def api(test_db):
    app = FastAPI()
    app.include_router(assets_router, prefix="/api")
    app.include_router(characters_router, prefix="/api")
    return TestClient(app)


@pytest.fixture
async def world(test_db):
    p = await crud.create_project(name="P")
    v = await crud.create_video(project_id=p["id"], title="V", orientation="HORIZONTAL")
    c = await crud.create_character(name="Teacher Lan", slug=slugify("Teacher Lan"), entity_type="character",
                                    description="desc", image_prompt="lan prompt")
    await crud.link_character_to_project(p["id"], c["id"])
    root = await crud.create_scene(video_id=v["id"], display_order=0, prompt="root prompt",
                                   video_prompt="root video", character_names=["Teacher Lan"])
    return {"pid": p["id"], "vid": v["id"], "cid": c["id"], "sid": root["id"]}


async def _completed(req_type, **kw):
    r = await crud.create_request(req_type=req_type, **kw)
    return await crud.update_request(r["id"], status="COMPLETED", media_id=MEDIA,
                                     output_url="https://x/" + r["id"])


async def test_snapshot_written_on_create(world):
    r = await crud.create_request(req_type="GENERATE_IMAGE", scene_id=world["sid"],
                                  video_id=world["vid"], orientation="HORIZONTAL")
    assert r["prompt_snapshot"] == "root prompt"
    r = await crud.create_request(req_type="GENERATE_VIDEO", scene_id=world["sid"],
                                  video_id=world["vid"], orientation="HORIZONTAL")
    assert r["prompt_snapshot"] == "root video"
    r = await crud.create_request(req_type="REGENERATE_CHARACTER_IMAGE", character_id=world["cid"])
    assert r["prompt_snapshot"] == "lan prompt"


async def test_snapshot_none_for_unknown_type(world):
    assert await compute_prompt_snapshot("UPSCALE_VIDEO", world["sid"], None, "HORIZONTAL") is None


async def test_scene_versions_and_restore_image_clears_video(api, world):
    sid = world["sid"]
    old = await _completed("GENERATE_IMAGE", scene_id=sid, video_id=world["vid"], orientation="HORIZONTAL")
    await crud.update_scene(sid, prompt="new prompt", horizontal_image_url="https://x/new",
                            horizontal_video_url="https://x/vid", horizontal_video_status="COMPLETED")
    vs = api.get(f"/api/scenes/{sid}/versions", params={"kind": "image", "orientation": "HORIZONTAL"}).json()
    assert [v["request_id"] for v in vs] == [old["id"]]
    assert vs[0]["prompt_snapshot"] == "root prompt"
    r = api.post(f"/api/scenes/{sid}/restore", json={
        "request_id": old["id"], "kind": "image", "orientation": "HORIZONTAL", "restore_prompt": True})
    assert r.status_code == 200
    s = await crud.get_scene(sid)
    assert s["horizontal_image_url"] == old["output_url"]
    assert s["horizontal_video_url"] is None
    assert s["horizontal_video_status"] == "PENDING"
    assert s["prompt"] == "root prompt"


async def test_restore_rejects_foreign_request(api, world):
    other = await _completed("GENERATE_CHARACTER_IMAGE", character_id=world["cid"])
    r = api.post(f"/api/scenes/{world['sid']}/restore", json={
        "request_id": other["id"], "kind": "image", "orientation": "HORIZONTAL", "restore_prompt": False})
    assert r.status_code == 404


async def test_character_versions_and_restore(api, world):
    cid = world["cid"]
    old = await _completed("GENERATE_CHARACTER_IMAGE", character_id=cid)
    await crud.update_character(cid, image_prompt="changed", media_id="other")
    assert [v["request_id"] for v in api.get(f"/api/characters/{cid}/versions").json()] == [old["id"]]
    c = api.post(f"/api/characters/{cid}/restore", json={"request_id": old["id"], "restore_prompt": True}).json()
    assert c["media_id"] == MEDIA and c["image_prompt"] == "lan prompt"


async def test_upload_records_history(api, world, monkeypatch):
    from agent.api import assets as assets_api

    class FakeClient:
        connected = True

    async def fake_upload(client, image_bytes, *, project_id, mime_type, file_name):
        assert image_bytes == b"PNGDATA"
        return {"media_id": MEDIA, "project_id": project_id, "raw": {}}

    async def fake_signed(client, media_id):
        return "https://signed/" + media_id

    monkeypatch.setattr(assets_api, "get_flow_client", lambda: FakeClient())
    monkeypatch.setattr(assets_api, "_upload_image_bytes", fake_upload)
    monkeypatch.setattr(assets_api, "_signed_image_url", fake_signed)
    cid = world["cid"]
    r = api.post(f"/api/characters/{cid}/upload", data={"project_id": world["pid"]},
                 files={"file": ("me.png", b"PNGDATA", "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["media_id"] == MEDIA
    assert r.json()["reference_image_url"] == "https://signed/" + MEDIA
    vs = api.get(f"/api/characters/{cid}/versions").json()
    assert vs[0]["type"] == "EDIT_CHARACTER_IMAGE" and vs[0]["prompt_snapshot"] == "upload: me.png"


async def test_usage_and_clone(api, world):
    cid, pid = world["cid"], world["pid"]
    p2 = await crud.create_project(name="P2")
    await crud.link_character_to_project(p2["id"], cid)
    assert {p["id"] for p in api.get(f"/api/characters/{cid}/projects").json()} == {pid, p2["id"]}
    new = api.post(f"/api/characters/{cid}/clone", json={"project_id": pid}).json()
    assert new["name"] == "Teacher Lan (2)" and new["id"] != cid
    linked = {c["id"] for c in await crud.get_project_characters(pid)}
    assert linked == {new["id"]}
    s = await crud.get_scene(world["sid"])
    assert json.loads(s["character_names"]) == ["Teacher Lan (2)"]


async def test_rename_cascades_to_scenes(api, world):
    r = api.patch(f"/api/characters/{world['cid']}", json={"name": "Co Lan"})
    assert r.status_code == 200
    s = await crud.get_scene(world["sid"])
    assert json.loads(s["character_names"]) == ["Co Lan"]


async def test_upload_history_row_is_never_pending(api, world, monkeypatch):
    """A PENDING EDIT_CHARACTER_IMAGE row could be picked up by the worker and spend Flow credits."""
    from agent.api import assets as assets_api

    class FakeClient:
        connected = True

    async def fake_upload(client, image_bytes, *, project_id, mime_type, file_name):
        return {"media_id": MEDIA, "project_id": project_id, "raw": {}}

    async def fake_signed(client, media_id):
        return "https://signed/" + media_id

    async def no_pending_requests(*a, **kw):
        raise AssertionError("upload must not create a PENDING request")

    monkeypatch.setattr(assets_api, "get_flow_client", lambda: FakeClient())
    monkeypatch.setattr(assets_api, "_upload_image_bytes", fake_upload)
    monkeypatch.setattr(assets_api, "_signed_image_url", fake_signed)
    monkeypatch.setattr(assets_api.crud, "create_request", no_pending_requests)
    r = api.post(f"/api/characters/{world['cid']}/upload", data={"project_id": world["pid"]},
                 files={"file": ("me.png", b"PNGDATA", "image/png")})
    assert r.status_code == 200, r.text
    rows = await assets_api.list_versions(character_id=world["cid"], types=("EDIT_CHARACTER_IMAGE",))
    assert len(rows) == 1


async def test_rename_cascades_slug_references(api, world):
    """FlowKit matches character_names by name OR slug; slug references must follow a rename too."""
    s2 = await crud.create_scene(video_id=world["vid"], display_order=1, prompt="p",
                                 character_names=[slugify("Teacher Lan"), "Other"])
    api.patch(f"/api/characters/{world['cid']}", json={"name": "Co Lan"})
    s = await crud.get_scene(s2["id"])
    assert json.loads(s["character_names"]) == ["Co Lan", "Other"]


async def test_clone_rewrites_slug_references(api, world):
    s2 = await crud.create_scene(video_id=world["vid"], display_order=1, prompt="p",
                                 character_names=[slugify("Teacher Lan")])
    api.post(f"/api/characters/{world['cid']}/clone", json={"project_id": world["pid"]})
    s = await crud.get_scene(s2["id"])
    assert json.loads(s["character_names"]) == ["Teacher Lan (2)"]


async def _other(world, name, link=True, project_id=None):
    o = await crud.create_character(name=name, slug=slugify(name), entity_type="character")
    if link:
        await crud.link_character_to_project(project_id or world["pid"], o["id"])
    return o


async def test_rename_collision_by_name_returns_409_and_changes_nothing(api, world):
    await _other(world, "Co Lan")
    r = api.patch(f"/api/characters/{world['cid']}", json={"name": "Co Lan"})
    assert r.status_code == 409
    assert "Co Lan" in r.json()["detail"] and "P" in r.json()["detail"]
    assert (await crud.get_character(world["cid"]))["name"] == "Teacher Lan"
    assert json.loads((await crud.get_scene(world["sid"]))["character_names"]) == ["Teacher Lan"]


async def test_rename_collision_by_slug_returns_409(api, world):
    await _other(world, "co-lan")
    r = api.patch(f"/api/characters/{world['cid']}", json={"name": "Co Lan"})  # slug "co-lan"
    assert r.status_code == 409
    assert (await crud.get_character(world["cid"]))["name"] == "Teacher Lan"


async def test_rename_ok_when_collision_only_in_unrelated_project_or_self(api, world):
    p2 = await crud.create_project(name="P2")
    await _other(world, "Co Lan", project_id=p2["id"])
    assert api.patch(f"/api/characters/{world['cid']}", json={"name": "Co Lan"}).status_code == 200
    assert api.patch(f"/api/characters/{world['cid']}", json={"name": "Co Lan"}).status_code == 200


async def test_clone_twice_gets_unique_names(api, world):
    pid, cid = world["pid"], world["cid"]
    n1 = api.post(f"/api/characters/{cid}/clone", json={"project_id": pid}).json()
    await crud.link_character_to_project(pid, cid)
    n2 = api.post(f"/api/characters/{cid}/clone", json={"project_id": pid}).json()
    assert n1["name"] == "Teacher Lan (2)" and n2["name"] == "Teacher Lan (3)"
    assert n1["slug"] != n2["slug"]


async def test_resigning_a_version_url_keeps_its_place_in_history(world):
    """Refreshing an expired output_url must not reorder the version strip."""
    old = await _completed("GENERATE_IMAGE", scene_id=world["sid"], video_id=world["vid"],
                           orientation="HORIZONTAL")
    await crud.set_request_output_url(old["id"], "https://x/fresh")
    after = await crud.get_request(old["id"])
    assert after["output_url"] == "https://x/fresh"
    assert after["updated_at"] == old["updated_at"]
