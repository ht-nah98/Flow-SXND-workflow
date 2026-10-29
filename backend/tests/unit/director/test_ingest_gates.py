import pytest

from agent.db import crud
from agent.director import brain, budget, pipeline, production, store
from agent.director import ingest as ingest_mod
from tests.unit.director.fake_plans import fake_responses, finish


@pytest.fixture
def world(test_db, monkeypatch):
    brain.set_brain(brain.FakeBrain(fake_responses()))

    async def done(ids, poll_s=None, **kw):
        rows = {}
        for rid in ids:
            await finish(rid, "COMPLETED")
            rows[rid] = await crud.get_request(rid)
        return rows
    production.set_waiter(done)
    yield
    brain.reset_brain(); production.reset_waiter()


async def start():
    r = await store.create_run({"text": "love", "target_s": 15}, {})
    return await pipeline.run_until_blocked(r["id"])


async def at_assets():
    r = await start()
    await pipeline.approve(r["id"], "SCRIPT")
    return await pipeline.run_until_blocked(r["id"])


async def test_script_gate_comes_before_any_credit(world):
    r = await start()
    assert (r["status"], r["gate"], r["stage"]) == ("WAITING_GATE", "SCRIPT", "INGEST")
    ids = r["plan"]["ids"]
    p = await crud.get_project(ids["project_id"])
    assert p["video_model_family"] == "omni_flash" and p["story"] == r["plan"]["story"]["synopsis"]
    scenes = await crud.list_scenes(ids["video_id"])
    assert [s["duration"] for s in scenes] == [10, 10, 10]
    assert all(s["video_mode"] == "r2v" and not s["image_prompt"] for s in scenes)
    assert [s["prompt"] for s in scenes] == [sh["idea"] for sh in r["plan"]["shotlist"]["shots"]]
    assert await crud.list_requests(project_id=ids["project_id"]) == []
    assert r["plan"]["gate_budget"]["SCRIPT"] == {"refs": 3}
    assert r["plan"]["gate_payload"] == {"shots": 3, "refs": 3, "provided": 0, "credits_est": 3,
                                         "videos": 3, "regens": 1, "video_credits_est": 60,
                                         "total_credits_est": 63}


async def test_auto_mode_grants_everything_and_skips_the_assets_gate(world, monkeypatch):
    monkeypatch.setitem(pipeline.HANDLERS, "VIDEOS", pipeline._stop_here)
    r = await start()
    r = await pipeline.approve(r["id"], "SCRIPT", mode="auto")
    assert r["budget"] == {"refs": 3, "videos": 3, "regens": 1} and r["plan"]["mode"] == "auto"
    r = await pipeline.run_until_blocked(r["id"])
    assert (r["status"], r["gate"], r["stage"]) == ("RUNNING", None, "VIDEOS")


async def test_auto_mode_still_stops_when_a_reference_fails(world, monkeypatch):
    async def fail_one(ids, poll_s=None, **kw):
        out = {}
        for n, i in enumerate(ids):
            await finish(i, "FAILED" if n == 0 else "COMPLETED")
            out[i] = await crud.get_request(i)
        return out
    production.set_waiter(fail_one)
    r = await start()
    await pipeline.approve(r["id"], "SCRIPT", mode="auto")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["gate"] == "ASSETS" and len(r["plan"]["gate_payload"]["failed_refs"]) == 1


async def test_approving_the_script_generates_refs_then_asks_for_video_credit(world):
    r = await at_assets()
    assert (r["gate"], r["stage"]) == ("ASSETS", "REFS")
    reqs = await crud.list_requests(project_id=r["plan"]["ids"]["project_id"])
    assert len(reqs) == 3 and {q["type"] for q in reqs} == {"GENERATE_CHARACTER_IMAGE"}
    assert {q["orientation"] for q in reqs} == {"HORIZONTAL"}
    assert r["budget"]["refs"] == 3 and r["spent"]["refs"] == 3
    assert r["plan"]["estimate"] == {"videos": 3, "regens": 1, "credits_est": 60}
    assert r["plan"]["gate_budget"]["ASSETS"] == {"videos": 3, "regens": 1}


async def test_entities_with_a_reference_are_not_generated(world):
    r = await start()
    ids = r["plan"]["ids"]
    first = next(iter(ids["entities"].values()))
    await crud.update_character(first, media_id="11111111-1111-1111-1111-111111111111")
    r = await store.get_run(r["id"])
    await pipeline.approve(r["id"], "SCRIPT", {"refs": 2})
    r = await pipeline.run_until_blocked(r["id"])
    reqs = await crud.list_requests(project_id=ids["project_id"])
    assert len(reqs) == 2 and first not in {q["character_id"] for q in reqs}


async def test_ingest_is_idempotent(world):
    r = await start()
    again = await ingest_mod.ingest(r)
    assert again == r["plan"]["ids"]
    assert len(await crud.list_scenes(r["plan"]["ids"]["video_id"])) == 3


async def test_budget_exceeded_never_creates_a_request(world, monkeypatch):
    r = await store.create_run({"text": "t", "target_s": 15}, {"videos": 0})
    called = []
    monkeypatch.setattr(crud, "create_request", lambda *a, **k: called.append(1))
    with pytest.raises(budget.BudgetExceeded):
        await budget.guarded_request(r["id"], "videos", req_type="GENERATE_VIDEO")
    assert called == []


async def test_revise_routes_back_and_records_user_lesson(world):
    r = await start()
    fb = brain.FakeBrain(fake_responses() | {
        "editor": [{"score": 50, "checklist": {}, "fixes": [{"target_stage": "SHOTLIST", "issue": "more beach"}]}],
        "coach": [{"lessons": [{"scope": "story", "rule": "User wants seaside scenes", "evidence": []}]}]})
    brain.set_brain(fb)
    r = await pipeline.revise(r["id"], "thêm cảnh biển")
    assert (r["stage"], r["status"]) == ("SHOTLIST", "RUNNING")
    assert "thêm cảnh biển" in " ".join(r["plan"]["revision_notes"])
    assert [l["rule"] for l in await store.list_lessons(status="ACTIVE", scopes=["story"])] == [
        "User wants seaside scenes"]


async def test_revision_resyncs_scenes(world):
    r = await start()
    run = await store.get_run(r["id"])
    run["plan"]["shotlist"]["shots"] = run["plan"]["shotlist"]["shots"][:2]
    run["plan"]["prompts"]["prompts"] = run["plan"]["prompts"]["prompts"][:2]
    from agent.director.ingest import sync_scenes
    await sync_scenes(run)
    assert len(await crud.list_scenes(run["plan"]["ids"]["video_id"])) == 2


async def test_approve_assets_grants_the_asked_video_budget_and_advances(world):
    r = await at_assets()
    r = await pipeline.approve(r["id"], "ASSETS")
    assert (r["stage"], r["status"], r["gate"]) == ("VIDEOS", "RUNNING", None)
    assert r["budget"]["videos"] == 3 and r["budget"]["regens"] == 1 and r["spent"]["refs"] == 3
    with pytest.raises(ValueError):
        await pipeline.approve(r["id"], "ASSETS")


async def test_ingest_uses_flow_project_id_when_connected(world, monkeypatch):
    from agent.director import ingest

    class FakeClient:
        connected = True
        last_account = "hot@gmail.com"     # the profile that answered

        created_in = []

        async def create_project(self, name, tool):
            self.created_in.append(ingest.CURRENT_ACCOUNT.get())
            return {"data": {"projectId": "flow-proj-123"}}

    client = FakeClient()
    monkeypatch.setattr(ingest, "get_flow_client", lambda: client)
    r = await start()
    # 23/10 Blue Morning: with three profiles connected the Flow project was made in another account than the one the
    # film was bound to, so every clip went to a project that account does not have (NO_MEDIA_CREATED ×6)
    assert client.created_in == ["hot@gmail.com"]
    assert r["plan"]["ids"]["project_id"] == "flow-proj-123"
    assert r["project_id"] == "flow-proj-123"
    assert (await crud.get_project("flow-proj-123"))["id"] == "flow-proj-123"
    assert (await crud.get_project("flow-proj-123"))["flow_account"] == "hot@gmail.com"   # bound to its account


async def _reopen_refs(rid):
    return await store.update_run(rid, status="RUNNING", gate=None, stage="REFS")


async def test_request_for_adopts_existing_row_without_reserving(world):
    r = await at_assets()
    run = await store.get_run(r["id"])
    ids = run["plan"]["ids"]
    name, cid = next(iter(ids["entities"].items()))
    run["plan"]["requests"].pop(f"ref:{name}")
    before = run["spent"]["refs"]
    existing = next(q for q in await crud.list_requests(project_id=ids["project_id"])
                    if q["character_id"] == cid)
    rid = await production.request_for(run, f"ref:{name}", "refs", req_type="GENERATE_CHARACTER_IMAGE",
                                       character_id=cid, project_id=ids["project_id"])
    assert rid == existing["id"]
    assert len(await crud.list_requests(project_id=ids["project_id"])) == 3
    assert (await store.get_run(r["id"]))["spent"]["refs"] == before
    assert (await store.get_run(r["id"]))["plan"]["requests"][f"ref:{name}"] == rid


async def test_pause_during_wait_returns_run_unchanged(world, monkeypatch):
    # Single-task on purpose: a concurrent poller contending for agent.db.schema._db_lock would
    # bind that asyncio.Lock to this test's loop and break later tests on other loops.
    production.reset_waiter()
    run = await store.create_run({"text": "love", "target_s": 15}, {})
    await pipeline.run_until_blocked(run["id"])
    await pipeline.approve(run["id"], "SCRIPT")

    async def pause_instead_of_sleeping(_):
        await store.update_run(run["id"], status="PAUSED")
    monkeypatch.setattr(production.asyncio, "sleep", pause_instead_of_sleeping)
    r = await pipeline.run_until_blocked(run["id"])
    assert (r["stage"], r["status"]) == ("REFS", "PAUSED")
    assert r["plan"]["requests"]


async def test_missing_request_row_counts_as_failed(world):
    production.reset_waiter()
    rows = await production.wait_requests(["no-such-request"], poll_s=0.01)
    assert rows["no-such-request"]["status"] == "FAILED"


async def test_ingest_resumes_after_crash(world, monkeypatch):
    run = await store.create_run({"text": "love", "target_s": 15}, {})
    brain.set_brain(brain.FakeBrain(fake_responses()))
    monkeypatch.setitem(pipeline.HANDLERS, "INGEST", pipeline._stop_here)
    await pipeline.run_until_blocked(run["id"])
    monkeypatch.undo()
    run = await store.get_run(run["id"])
    assert "ids" not in run["plan"]
    real, calls = crud.create_character, []

    async def flaky(*a, **k):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("boom")
        return await real(*a, **k)
    monkeypatch.setattr(crud, "create_character", flaky)
    with pytest.raises(RuntimeError):
        await ingest_mod.ingest(run)
    monkeypatch.setattr(crud, "create_character", real)
    run = await store.get_run(run["id"])
    assert len(run["plan"]["ids"]["entities"]) == 1 and run["plan"]["ids"]["video_id"] is None
    ids = await ingest_mod.ingest(run)
    n_cast = len(run["plan"]["story"]["cast"])
    assert len(ids["entities"]) == n_cast and len(ids["scenes"]) == 3 and ids["video_id"]
    assert len(await crud.list_scenes(ids["video_id"])) == 3
    assert len(await crud.list_projects()) == 1
    assert len(await crud.list_characters()) == n_cast


async def test_failed_ref_is_rerequested_on_next_pass(world):
    r = await at_assets()
    ids = r["plan"]["ids"]
    name = next(iter(ids["entities"]))
    old = r["plan"]["requests"][f"ref:{name}"]
    await crud.update_request(old, status="FAILED")
    await crud.update_character(ids["entities"][name], media_id=None)
    await store.add_budget(r["id"], {"refs": 1})
    await _reopen_refs(r["id"])
    r = await pipeline.run_until_blocked(r["id"])
    assert r["gate"] == "ASSETS" and r["plan"]["requests"][f"ref:{name}"] != old
    assert r["spent"]["refs"] == 4


async def test_refs_budget_too_small_raises_budget_gate(test_db):
    brain.set_brain(brain.FakeBrain(fake_responses()))
    production.set_waiter(lambda ids, poll_s=None, **kw: None)
    try:
        run = await store.create_run({"text": "love", "target_s": 15}, {})
        await pipeline.run_until_blocked(run["id"])
        await pipeline.approve(run["id"], "SCRIPT", {"refs": 1})
        r = await pipeline.run_until_blocked(run["id"])
    finally:
        brain.reset_brain(); production.reset_waiter()
    assert (r["status"], r["gate"]) == ("WAITING_GATE", "BUDGET_EXCEEDED")


async def test_revise_rejects_when_gate_no_longer_open(world, monkeypatch):
    r = await start()
    real = brain.think

    async def racing(role, payload, schema, **kw):
        out = await real(role, payload, schema, **kw)
        if role == "coach":
            await pipeline.approve(r["id"], "SCRIPT")
        return out
    monkeypatch.setattr(brain, "think", racing)
    with pytest.raises(ValueError):
        await pipeline.revise(r["id"], "x")
    assert (await store.get_run(r["id"]))["stage"] == "REFS"   # revise did not clobber the approval


async def test_story_revision_receives_locked_cast_names(world):
    """A rewrite must reuse cast names that already have reference images (no renames → no extra refs)."""
    r = await start()
    fb = brain.FakeBrain(fake_responses() | {
        "editor": [{"score": 50, "checklist": {}, "fixes": [{"target_stage": "STORY", "issue": "show the bump"}]}],
        "coach": [{"lessons": []}]})
    brain.set_brain(fb)
    await pipeline.revise(r["id"], "cho thấy cú va chạm")
    await pipeline.run_until_blocked(r["id"])
    writer = [p for role, p in fb.calls if role == "writer"]
    assert sorted(writer[0]["locked_cast"]) == sorted(r["plan"]["ids"]["entities"])


async def test_first_story_has_no_locked_cast(world):
    fb = brain.FakeBrain(fake_responses())
    brain.set_brain(fb)
    await start()
    writer = [p for role, p in fb.calls if role == "writer"]
    assert writer[0].get("locked_cast", []) == []


async def test_videos_never_start_while_an_asset_image_is_missing(world):
    async def fail_one(ids, poll_s=None, **kw):
        out = {}
        for n, i in enumerate(ids):
            await finish(i, "FAILED" if n == 0 else "COMPLETED")
            out[i] = await crud.get_request(i)
        return out
    production.set_waiter(fail_one)
    r = await start()
    await pipeline.approve(r["id"], "SCRIPT")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["gate"] == "ASSETS"
    with pytest.raises(ValueError, match="asset images still missing"):
        await pipeline.approve(r["id"], "ASSETS")
    # forcing the stage anyway (e.g. an old run resumed) stops before any video request
    await store.update_run(r["id"], status="RUNNING", gate=None, stage="VIDEOS")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["gate"] == "ASSETS" and "missing" in r["plan"]["gate_payload"]
    reqs = await crud.list_requests(project_id=r["plan"]["ids"]["project_id"])
    assert not [q for q in reqs if q["type"].startswith("GENERATE_VIDEO")]


async def test_auto_mode_assets_gate_grants_nothing_twice(world):
    async def fail_one(ids, poll_s=None, **kw):
        out = {}
        for n, i in enumerate(ids):
            await finish(i, "FAILED" if n == 0 else "COMPLETED")
            out[i] = await crud.get_request(i)
        return out
    production.set_waiter(fail_one)
    r = await start()
    await pipeline.approve(r["id"], "SCRIPT", mode="auto")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["plan"]["gate_budget"]["ASSETS"] == {} and r["plan"]["gate_payload"]["credits_est"] == 0


async def test_missing_images_are_made_from_the_assets_gate(world):
    calls = {"n": 0}

    async def first_round_fails_one(ids, poll_s=None, **kw):
        calls["n"] += 1
        out = {}
        for n, i in enumerate(ids):
            out[i] = await finish(i, "FAILED" if calls["n"] == 1 and n == 0 else "COMPLETED")
        return out
    production.set_waiter(first_round_fails_one)
    r = await start()
    await pipeline.approve(r["id"], "SCRIPT")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["gate"] == "ASSETS"
    r = await pipeline.make_missing_refs(r["id"])
    assert r["budget"]["refs"] == 4 and r["stage"] == "REFS"
    r = await pipeline.run_until_blocked(r["id"])
    assert r["gate"] == "ASSETS" and r["spent"]["refs"] == 4
    assert not await pipeline._refs_needed(r["plan"]["ids"])
    with pytest.raises(ValueError, match="no asset image is missing"):
        await pipeline.make_missing_refs(r["id"])
