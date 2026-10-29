import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api.director import router
from agent.db import crud
from agent.director import brain, pipeline, production, runner, store
from tests.unit.director.fake_plans import fake_responses, finish


@pytest.fixture
def world(test_db):
    fb = brain.FakeBrain(fake_responses())
    brain.set_brain(fb)

    async def done(ids, poll_s=None, **kw):
        rows = {}
        for rid in ids:
            await finish(rid, "COMPLETED")
            rows[rid] = await crud.get_request(rid)
        return rows
    production.set_waiter(done)
    yield fb
    brain.reset_brain(); production.reset_waiter()


async def new_run():
    return await store.create_run({"text": "love", "target_s": 15}, {})


async def test_double_kick_runs_pipeline_once(world):
    r = await new_run()
    runner.kick(r["id"]); runner.kick(r["id"])
    await runner._tasks[r["id"]]
    assert [c for c, _ in world.calls].count("producer") == 1
    assert (await store.get_run(r["id"]))["gate"] == "SCRIPT" and r["id"] not in runner._tasks


async def test_kick_while_task_live_is_honoured(world, monkeypatch):
    r = await new_run()
    real, calls = pipeline.run_until_blocked, []

    async def wrapper(rid):
        calls.append(rid)
        out = await real(rid)
        if len(calls) == 1:           # approve + kick arrive while the task is still live
            await pipeline.approve(rid, "SCRIPT")
            runner.kick(rid)
        return out
    monkeypatch.setattr(pipeline, "run_until_blocked", wrapper)
    runner.kick(r["id"])
    await runner._tasks[r["id"]]
    assert len(calls) == 2 and r["id"] not in runner._tasks
    assert (await store.get_run(r["id"]))["gate"] == "ASSETS"


async def test_crash_marks_failed_and_cleans_up(test_db, monkeypatch):
    r = await new_run()

    async def boom(rid):
        raise RuntimeError("kaput")
    monkeypatch.setattr(pipeline, "run_until_blocked", boom)
    runner.kick(r["id"])
    await runner._tasks[r["id"]]
    got = await store.get_run(r["id"])
    assert got["status"] == "FAILED" and "kaput" in got["error"] and r["id"] not in runner._tasks


@pytest.fixture
def api(world, monkeypatch):
    monkeypatch.setattr(runner, "kick", lambda rid: None)
    app = FastAPI(); app.include_router(router, prefix="/api")
    return TestClient(app)


async def at_script_gate():
    r = await new_run()
    r = await pipeline.run_until_blocked(r["id"])
    assert r["gate"] == "SCRIPT"
    return r


async def test_patch_shot_invalid_is_422_and_plan_unchanged(api):
    r = await at_script_gate()
    res = api.patch(f"/api/director/runs/{r['id']}/shots/s1", json={"commands": ["/static", "/dolly-in"]})
    assert res.status_code == 422 and res.json()["detail"]
    assert (await store.get_run(r["id"]))["plan"] == r["plan"]


async def test_patch_shot_valid_updates_plan_and_scene(api):
    r = await at_script_gate()
    vp = r["plan"]["prompts"]["prompts"][0]["video_prompt"].replace("tiếng cười khẽ", "tiếng cười nhẹ")
    assert vp != r["plan"]["prompts"]["prompts"][0]["video_prompt"]
    res = api.patch(f"/api/director/runs/{r['id']}/shots/s1", json={"video_prompt": vp})
    assert res.status_code == 200, res.text
    got = await store.get_run(r["id"])
    assert got["plan"]["prompts"]["prompts"][0]["video_prompt"] == vp
    scenes = await crud.list_scenes(r["plan"]["ids"]["video_id"])
    assert any("tiếng cười nhẹ" in (s.get("video_prompt") or "") for s in scenes)


def test_approve_budget_keys_validated():
    app = FastAPI(); app.include_router(router, prefix="/api")
    c = TestClient(app)
    for bad in ({"bogus": 1}, {"refs": -1}):
        assert c.post("/api/director/runs/x/approve", json={"gate": "CREDIT", "budget": bad}).status_code == 422


async def test_timeline_lists_steps_and_typical_durations(api):
    r = await at_script_gate()
    body = api.get(f"/api/director/runs/{r['id']}/timeline").json()
    assert [s["stage"] for s in body["steps"]][:3] == ["BRIEF", "STORY", "SHOTLIST"]
    assert body["gate"] == "SCRIPT" and "input" not in body["steps"][0]
    assert set(body["typical_ms"]) <= {"BRIEF", "STORY", "SHOTLIST", "PROMPTS", "EDIT_REVIEW"}


async def test_rewrite_proposes_a_new_prompt_and_apply_updates_plan_and_scene(api, world):
    r = await at_script_gate()
    old = r["plan"]["prompts"]["prompts"][0]
    new_vp = old["video_prompt"].replace("tiếng cười khẽ", "tiếng cười giòn")
    world.responses["reshoot"] = [{"shot_id": "s1", "video_prompt": new_vp, "keyframe_prompt": None,
                                   "end_frame": old["end_frame"]}]
    res = api.post(f"/api/director/runs/{r['id']}/shots/s1/rewrite", json={"feedback": "cười tươi hơn"})
    assert res.status_code == 200, res.text
    assert res.json()["new"] == new_vp and res.json()["old"] == old["video_prompt"]
    assert (await store.get_run(r["id"]))["plan"]["prompts"]["prompts"][0]["video_prompt"] == old["video_prompt"]
    assert api.post(f"/api/director/runs/{r['id']}/shots/s1/apply-rewrite").status_code == 200
    got = await store.get_run(r["id"])
    assert got["plan"]["prompts"]["prompts"][0]["video_prompt"] == new_vp and "s1" not in got["plan"]["proposals"]
    scenes = await crud.list_scenes(got["plan"]["ids"]["video_id"])
    assert any(s["video_prompt"] == new_vp for s in scenes)


async def test_rewrite_that_breaks_the_format_is_rejected(api, world):
    r = await at_script_gate()
    world.responses["reshoot"] = [{"shot_id": "s1", "video_prompt": "just walk", "keyframe_prompt": None,
                                   "end_frame": "x"}] * 3
    assert api.post(f"/api/director/runs/{r['id']}/shots/s1/rewrite", json={"feedback": "nhanh hơn"}).status_code == 422


async def test_claude_rewrites_the_prompt_from_the_video_review(api, world):
    """22/10: after "Claude đánh giá" (6.8/10, 5 errors) the user asked whether Claude rewrites the prompt itself."""
    r = await at_script_gate()
    old = r["plan"]["prompts"]["prompts"][0]
    world.responses["reshoot"] = [{"shot_id": "s1", "video_prompt": old["video_prompt"], "keyframe_prompt": None,
                                   "end_frame": old["end_frame"]}]
    review = {"score": 6.8, "errors": [{"severity": "HIGH", "time_range": "3s-5s", "description": "hand morphs"}]}
    res = api.post(f"/api/director/runs/{r['id']}/shots/s1/rewrite", json={"review": review})
    assert res.status_code == 200, res.text
    role, payload = world.calls[-1]
    assert role == "reshoot" and payload["review"] == review and payload["feedback"] == ""
    assert api.post(f"/api/director/runs/{r['id']}/shots/s1/rewrite", json={"review": {"errors": []}}).status_code == 422


async def test_effects_catalog_and_edit_round_trip(api):
    cat = api.get("/api/director/effects").json()
    assert {"looks", "transitions", "fx"} <= cat.keys()
    assert any(t["id"] == "nhay-trang" and t["label"] == "Nháy trắng" for t in cat["transitions"])
    r = await at_script_gate()
    e = api.get(f"/api/director/runs/{r['id']}/edit").json()
    shot_ids = [s["id"] for s in sorted(r["plan"]["shotlist"]["shots"], key=lambda s: s["order"])]
    assert [c["shot_id"] for c in e["clips"]] == shot_ids
    res = api.put(f"/api/director/runs/{r['id']}/edit", json={
        "look": "Phim cổ điển",
        "clips": [{"shot_id": shot_ids[0], "fx": ["glow", "không có", "hat", "vien-toi-nhat"],
                   "transition_out": "light leak"}]})
    assert res.status_code == 200, res.text
    got = res.json()
    assert got["look"] == "phim-co-dien"
    assert got["clips"][0] == {"shot_id": shot_ids[0], "fx": ["nhoe-sang", "hat"], "transition_out": "bung-sang-vang"}
    assert api.put(f"/api/director/runs/{r['id']}/edit", json={"clips": [{"shot_id": "nope"}]}).status_code == 422
