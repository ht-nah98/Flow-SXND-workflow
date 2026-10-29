"""Directive D1 (said four times): videos come from prompt + asset references, never from a first-frame image,
unless the user switches the project to image → video."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api.projects import router as projects_router
from agent.api.requests import router as requests_router
from agent.db import crud


def _client():
    app = FastAPI()
    app.include_router(projects_router, prefix="/api")
    app.include_router(requests_router, prefix="/api")
    return TestClient(app)


async def _scene(pid):
    vid = (await crud.create_video(project_id=pid, title="v"))["id"]
    sid = (await crud.create_scene(video_id=vid, display_order=0, prompt="shot"))["id"]
    return vid, sid


async def test_new_projects_default_to_refs_and_refuse_image_first_requests(test_db):
    p = await crud.create_project(name="phim")
    assert p["video_mode"] == "refs"
    vid, sid = await _scene(p["id"])
    c = _client()
    for t in ("GENERATE_IMAGE", "GENERATE_VIDEO", "EDIT_IMAGE"):
        r = c.post("/api/requests", json={"type": t, "project_id": p["id"], "video_id": vid, "scene_id": sid})
        assert r.status_code == 409 and "prompt + asset" in r.json()["detail"], t
    r = c.post("/api/requests/batch", json={"requests": [
        {"type": "GENERATE_IMAGE", "project_id": p["id"], "video_id": vid, "scene_id": sid}]})
    assert r.status_code == 409
    ok = c.post("/api/requests", json={"type": "GENERATE_VIDEO_REFS", "project_id": p["id"], "video_id": vid,
                                       "scene_id": sid})
    assert ok.status_code == 200


async def test_image_mode_is_an_explicit_project_choice(test_db):
    p = await crud.create_project(name="phim tay")
    vid, sid = await _scene(p["id"])
    c = _client()
    got = c.patch(f"/api/projects/{p['id']}", json={"video_mode": "image"})
    assert got.status_code == 200 and got.json()["video_mode"] == "image"
    assert c.patch(f"/api/projects/{p['id']}", json={"video_mode": "keyframe"}).status_code == 422
    r = c.post("/api/requests", json={"type": "GENERATE_IMAGE", "project_id": p["id"], "video_id": vid, "scene_id": sid})
    assert r.status_code == 200


async def test_regenerating_a_finished_clip_really_makes_a_new_one(test_db):
    """19/10: "Gen lại video" sent GENERATE_VIDEO_REFS for a finished scene; the worker skipped it as already done
    and copied the old clip as version 2 — two identical versions, both "in use"."""
    from agent.worker import processor
    p = await crud.create_project(name="phim")
    vid, sid = await _scene(p["id"])
    await crud.update_scene(sid, horizontal_video_status="COMPLETED", horizontal_video_media_id="old")
    r = _client().post("/api/requests/batch", json={"requests": [
        {"type": "GENERATE_VIDEO_REFS", "project_id": p["id"], "video_id": vid, "scene_id": sid,
         "orientation": "HORIZONTAL"}]})
    assert r.status_code == 200
    req = r.json()[0]
    assert (await crud.get_scene(sid))["horizontal_video_status"] == "PENDING"
    assert not await processor._is_already_completed(req, "HORIZONTAL")
