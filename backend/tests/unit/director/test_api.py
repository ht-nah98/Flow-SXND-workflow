import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api.director import router
from agent.director import runner, store


@pytest.fixture
def api(test_db, monkeypatch):
    # async tests + sync TestClient: same pattern as tests/unit/test_versions_assets.py
    kicked = []
    monkeypatch.setattr(runner, "kick", lambda rid: kicked.append(rid))
    app = FastAPI(); app.include_router(router, prefix="/api")
    c = TestClient(app); c.kicked = kicked
    return c


async def test_new_idea_waits_until_the_script_is_asked_for(api):
    assert api.post("/api/director/runs", json={"text": "x", "target_s": 5, "orientation": "HORIZONTAL"}).status_code == 422
    r = api.post("/api/director/runs", json={"text": "love"})
    assert r.status_code == 201 and api.kicked == []
    run = r.json()
    assert (run["status"], run["gate"], run["stage"]) == ("WAITING_GATE", "IDEA", "BRIEF")
    assert run["budget"] == {} and run["brief"]["target_s"] == 60 and run["brief"]["orientation"] == "HORIZONTAL"
    got = api.post(f"/api/director/runs/{run['id']}/approve", json={"gate": "IDEA"}).json()
    assert (got["status"], got["gate"], got["stage"]) == ("RUNNING", None, "BRIEF") and api.kicked == [run["id"]]
    assert got["budget"] == {}


async def test_idea_is_editable_only_before_the_script(api, tmp_path, monkeypatch):
    from agent import config
    from agent.db import crud
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    run = api.post("/api/director/runs", json={"text": "quán cà phê", "images": [_img(note="cũ")]}).json()
    f = run["brief"]["images"][0]["file"]
    got = api.patch(f"/api/director/runs/{run['id']}/idea",
                    json={"text": "quán cà phê  của tôi", "target_s": 30, "notes": {f: "đây là quán thật"}}).json()
    assert got["brief"]["text"] == "quán cà phê  của tôi" and got["brief"]["target_s"] == 30
    assert got["brief"]["images"][0]["note"] == "đây là quán thật"
    assert (await crud.get_project(run["project_id"]))["name"] == "quán cà phê của tôi"
    api.post(f"/api/director/runs/{run['id']}/approve", json={"gate": "IDEA"})
    assert api.patch(f"/api/director/runs/{run['id']}/idea", json={"text": "khác"}).status_code == 409


async def test_project_exists_as_soon_as_the_idea_is_sent(api):
    from agent.db import crud
    run = api.post("/api/director/runs", json={"text": "Hai bạn trẻ   làm bánh kem\ntrong bếp"}).json()
    p = await crud.get_project(run["project_id"])
    assert p["name"] == "Hai bạn trẻ làm bánh kem trong bếp" and p["video_model_family"] == "omni_flash"
    assert run["plan"]["ids"] == {"project_id": p["id"], "video_id": None, "entities": {}, "scenes": {}}


def _img(name="cafe.jpg", data=b"\xff\xd8jpeg", note=None):
    return {"base64": base64.b64encode(data).decode(), "filename": name, "note": note}


async def test_idea_images_are_stored_with_their_notes(api, tmp_path, monkeypatch):
    from agent import config
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    run = api.post("/api/director/runs", json={"text": "quán cà phê của tôi",
                                                "images": [_img(note="quán thật của tôi"), _img("me.png")]}).json()
    imgs = run["brief"]["images"]
    assert [i["note"] for i in imgs] == ["quán thật của tôi", None]
    assert all(i["file"].startswith(str(tmp_path)) for i in imgs)
    assert open(imgs[0]["file"], "rb").read() == b"\xff\xd8jpeg"


@pytest.mark.parametrize("img", [_img("x.gif"), {"base64": "%%%", "filename": "a.jpg"}])
async def test_bad_idea_images_are_rejected_before_any_run(api, img):
    assert api.post("/api/director/runs", json={"text": "idea", "images": [img]}).status_code == 400
    assert await store.list_runs() == []


async def test_at_most_six_images(api):
    assert api.post("/api/director/runs", json={"text": "idea", "images": [_img()] * 7}).status_code == 422


async def test_music_upload_type_is_checked(api):
    bad = api.post("/api/director/runs", json={"text": "love", "target_s": 30, "orientation": "HORIZONTAL",
                                                "music_base64": base64.b64encode(b"x").decode(),
                                                "music_filename": "evil.sh"})
    assert bad.status_code == 400


async def test_approve_wrong_gate_is_409(api):
    rid = api.post("/api/director/runs", json={"text": "love", "target_s": 30, "orientation": "HORIZONTAL"}).json()["id"]
    assert api.post(f"/api/director/runs/{rid}/approve", json={"gate": "ASSETS"}).status_code == 409


async def test_pause_resume_and_lessons(api):
    rid = api.post("/api/director/runs", json={"text": "love", "target_s": 30, "orientation": "HORIZONTAL"}).json()["id"]
    assert api.post(f"/api/director/runs/{rid}/pause").status_code == 409     # still an idea
    api.post(f"/api/director/runs/{rid}/approve", json={"gate": "IDEA"})
    assert api.post(f"/api/director/runs/{rid}/pause").json()["status"] == "PAUSED"
    assert api.post(f"/api/director/runs/{rid}/resume").json()["status"] == "RUNNING"
    lessons = api.get("/api/director/lessons").json()
    assert lessons == [] or all("rule" in l for l in lessons)


async def test_resume_all_kicks_running_runs(test_db, monkeypatch):
    kicked = []
    monkeypatch.setattr(runner, "kick", lambda rid: kicked.append(rid))
    a = await store.create_run({"text": "a", "target_s": 30}, {})
    b = await store.create_run({"text": "b", "target_s": 30}, {})
    await store.update_run(b["id"], status="WAITING_GATE")
    await runner.resume_all()
    assert kicked == [a["id"]]


async def test_patch_shot_requires_script_gate_and_404(api):
    rid = api.post("/api/director/runs", json={"text": "love", "target_s": 30, "orientation": "HORIZONTAL"}).json()["id"]
    assert api.patch(f"/api/director/runs/{rid}/shots/s1", json={"video_prompt": "x"}).status_code == 409
    assert api.patch("/api/director/runs/nope/shots/s1", json={"video_prompt": "x"}).status_code == 404
    assert api.patch(f"/api/director/runs/{rid}/shots/s1", json={"mode": "i2v"}).status_code == 422
    assert api.get("/api/director/runs/nope").status_code == 404


async def test_pause_stops_requests_still_queued_for_flow(api):
    from agent.db import crud
    rid = api.post("/api/director/runs", json={"text": "love", "target_s": 30, "orientation": "HORIZONTAL"}).json()["id"]
    api.post(f"/api/director/runs/{rid}/approve", json={"gate": "IDEA"})
    proj = await crud.create_project(name="p", story="s")
    await store.update_run(rid, status="RUNNING", plan={"ids": {"project_id": proj["id"]}})
    queued = await crud.create_request("GENERATE_CHARACTER_IMAGE", project_id=proj["id"])
    sent = await crud.create_request("GENERATE_CHARACTER_IMAGE", project_id=proj["id"])
    await crud.update_request(sent["id"], status="PROCESSING")
    assert api.post(f"/api/director/runs/{rid}/pause").json()["status"] == "PAUSED"
    assert (await crud.get_request(queued["id"]))["status"] == "FAILED"
    assert (await crud.get_request(sent["id"]))["status"] == "PROCESSING"   # already generating: kept
    assert api.post(f"/api/director/runs/{rid}/pause").status_code == 200   # pausing again is allowed


async def test_cancel_ends_the_run_and_its_queue_for_good(api, monkeypatch):
    from agent.db import crud
    stopped = []

    async def fake_cancel(rid):
        stopped.append(rid)
    monkeypatch.setattr(runner, "cancel", fake_cancel)
    rid = api.post("/api/director/runs", json={"text": "love", "target_s": 30, "orientation": "HORIZONTAL"}).json()["id"]
    proj = await crud.create_project(name="p", story="s")
    await store.update_run(rid, status="WAITING_GATE", gate="SCRIPT", plan={"ids": {"project_id": proj["id"]}})
    queued = await crud.create_request("GENERATE_CHARACTER_IMAGE", project_id=proj["id"])
    out = api.post(f"/api/director/runs/{rid}/cancel").json()
    assert out["status"] == "CANCELLED" and out["gate"] is None and stopped == [rid]
    assert (await crud.get_request(queued["id"]))["status"] == "FAILED"
    assert api.post(f"/api/director/runs/{rid}/cancel").status_code == 409
    assert api.post(f"/api/director/runs/{rid}/approve", json={"gate": "SCRIPT"}).status_code == 409
    assert api.post(f"/api/director/runs/{rid}/resume").status_code == 409


async def test_runner_cancel_stops_a_live_task(test_db):
    import asyncio
    started = asyncio.Event()

    async def forever():
        started.set()
        await asyncio.sleep(3600)
    runner._tasks["r1"] = asyncio.create_task(forever())
    await started.wait()
    await runner.cancel("r1")
    assert runner._tasks["r1"].cancelled()
    runner._tasks.pop("r1")


async def test_creativity_is_chosen_on_the_idea_and_editable_before_the_script(api):
    run = api.post("/api/director/runs", json={"text": "love"}).json()
    assert run["brief"]["creativity"] == "balanced"
    assert api.post("/api/director/runs", json={"text": "love", "creativity": "wild"}).status_code == 422
    got = api.patch(f"/api/director/runs/{run['id']}/idea", json={"creativity": "faithful"}).json()
    assert got["brief"]["creativity"] == "faithful"


async def test_film_mode_is_chosen_on_the_idea_and_editable_before_the_script(api):
    run = api.post("/api/director/runs", json={"text": "love"}).json()
    assert run["brief"]["film_mode"] == "continuous"   # directive B12, repeated 24/10: "Liền mạch là mặc định"
    assert "venue" not in run["brief"]
    assert api.post("/api/director/runs", json={"text": "love", "film_mode": "oner"}).status_code == 422
    got = api.patch(f"/api/director/runs/{run['id']}/idea", json={"film_mode": "cut"}).json()
    assert got["brief"]["film_mode"] == "cut"


async def test_an_ambient_idea_names_its_venue_and_reel(api):
    """Directive B14: ambient = one venue, a 1–2 minute reel; the venues come from one list (GET /venues)."""
    venues = api.get("/api/director/venues").json()
    assert {"worship-arena", "jazz-club"} <= {v["id"] for v in venues}
    assert all(v["name"] and len(v["explain"]) > 40 for v in venues)          # G2: explained in Vietnamese
    run = api.post("/api/director/runs", json={"text": "đêm nhạc", "film_mode": "ambient"}).json()
    assert (run["brief"]["venue"], run["brief"]["reel_s"], run["brief"]["loop_s"]) == ("worship-arena", 120, 1800)
    assert api.post("/api/director/runs", json={"text": "x", "film_mode": "ambient", "venue": "moon"}).status_code == 422
    assert api.post("/api/director/runs", json={"text": "x", "film_mode": "ambient", "reel_s": 300}).status_code == 422
    got = api.patch(f"/api/director/runs/{run['id']}/idea", json={"venue": "jazz-club", "reel_s": 60}).json()
    assert (got["brief"]["venue"], got["brief"]["reel_s"]) == ("jazz-club", 60)
    got = api.patch(f"/api/director/runs/{run['id']}/idea", json={"film_mode": "keyframe"}).json()
    assert "venue" not in got["brief"] and "reel_s" not in got["brief"]


async def test_optional_agents_default_on_and_can_be_switched_any_time(api):
    run = api.post("/api/director/runs", json={"text": "love", "agents": {"editor": False}}).json()
    assert run["brief"]["agents"] == {"producer": True, "editor": False, "qc": True, "coach": True}
    got = api.put(f"/api/director/runs/{run['id']}/agents", json={"qc": False, "coach": False}).json()
    assert got["brief"]["agents"] == {"producer": True, "editor": True, "qc": False, "coach": False}
    assert got["brief"]["text"] == "love"


async def test_script_package_is_served_once_the_script_exists(api):
    from tests.unit.director.fixtures import fmv_prompts, fmv_shotlist, fmv_story
    run = api.post("/api/director/runs", json={"text": "love"}).json()
    assert api.get(f"/api/director/runs/{run['id']}/package").status_code == 409
    await store.update_run(run["id"], plan={"brief": {"target_s": 30}, "story": fmv_story().model_dump(),
                                            "shotlist": fmv_shotlist().model_dump(), "prompts": fmv_prompts().model_dump()})
    got = api.get(f"/api/director/runs/{run['id']}/package").json()
    assert [f["name"] for f in got["files"]] == ["README.md", "kich-ban.md", "phan-canh-prompt.md"]
    assert got["folder"].endswith("kich-ban")


async def test_style_pack_is_picked_on_the_idea(api):
    packs = api.get("/api/director/styles").json()
    assert {p["id"] for p in packs} >= {"natural-youth", "warm-indie"}
    assert api.post("/api/director/runs", json={"text": "love", "style_pack": "nope"}).status_code == 422
    run = api.post("/api/director/runs", json={"text": "love", "style_pack": "warm-indie"}).json()
    assert run["brief"]["style_pack"] == "warm-indie"
    cleared = api.patch(f"/api/director/runs/{run['id']}/idea", json={"style_pack": ""}).json()
    assert cleared["brief"]["style_pack"] is None


async def test_a_keyframe_film_shows_image_to_video_from_the_start(api):
    """23/10: while the concert film was being split into shots, its script node still offered "🎬 Prompt + asset" —
    the project took "Ảnh → video" only at INGEST. It now follows the film mode from the start and when it changes."""
    from agent.db import crud
    r = api.post("/api/director/runs", json={"text": "a concert", "target_s": 30, "orientation": "HORIZONTAL",
                                              "film_mode": "keyframe"}).json()
    assert (await crud.get_project(r["project_id"]))["video_mode"] == "image"
    assert api.patch(f"/api/director/runs/{r['id']}/idea", json={"film_mode": "cut"}).status_code == 200
    assert (await crud.get_project(r["project_id"]))["video_mode"] == "refs"
    api.patch(f"/api/director/runs/{r['id']}/idea", json={"film_mode": "keyframe"})
    assert (await crud.get_project(r["project_id"]))["video_mode"] == "image"
