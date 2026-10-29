import pytest

from agent.db import crud
from agent.director import brain, pipeline, production, store
from tests.unit.director.fake_plans import fake_responses, finish


async def _complete(ids):
    out = {}
    for i in ids:
        await finish(i, "COMPLETED")
        out[i] = await crud.get_request(i)
    return out


@pytest.fixture
def world(test_db, monkeypatch):
    brain.set_brain(brain.FakeBrain(fake_responses()))
    monkeypatch.setitem(pipeline.HANDLERS, "QC", pipeline._stop_here)

    async def waiter(ids, poll_s=None, **kw):
        return await _complete(ids)
    production.set_waiter(waiter)
    yield
    brain.reset_brain()
    production.reset_waiter()


async def to_credit_gate():
    r = await store.create_run({"text": "love", "target_s": 15}, {})
    r = await pipeline.run_until_blocked(r["id"])
    await pipeline.approve(r["id"], "SCRIPT")
    return await pipeline.run_until_blocked(r["id"])


async def _video_reqs(r):
    return [q for q in await crud.list_requests(project_id=r["plan"]["ids"]["project_id"])
            if q["type"].startswith("GENERATE_VIDEO")]


async def test_every_clip_is_reference_to_video(world):
    r = await to_credit_gate()
    await pipeline.approve(r["id"], "ASSETS")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["stage"] == "QC"
    reqs = await crud.list_requests(project_id=r["plan"]["ids"]["project_id"])
    types = sorted(q["type"] for q in reqs if q["type"] != "GENERATE_CHARACTER_IMAGE")
    assert types == ["GENERATE_VIDEO_REFS"] * 3
    assert r["spent"] == {"refs": 3, "videos": 3}


async def test_budget_too_small_stops_at_gate_without_extra_requests(world):
    r = await to_credit_gate()
    await pipeline.approve(r["id"], "ASSETS", {"videos": 2})
    r = await pipeline.run_until_blocked(r["id"])
    assert (r["status"], r["gate"]) == ("WAITING_GATE", "BUDGET_EXCEEDED")
    assert len(await _video_reqs(r)) == 2


async def test_restart_mid_videos_does_not_duplicate_requests(world):
    r = await to_credit_gate()
    await pipeline.approve(r["id"], "ASSETS")
    calls = {"n": 0}

    async def crash_on_videos(ids, poll_s=None, **kw):
        calls["n"] += 1
        if calls["n"] == 1:            # the videos wait
            raise RuntimeError("backend killed")
        return await _complete(ids)
    production.set_waiter(crash_on_videos)
    r = await pipeline.run_until_blocked(r["id"])
    assert r["status"] == "FAILED"
    assert len(await _video_reqs(r)) == 3

    async def completing(ids, poll_s=None, **kw):
        return await _complete(ids)
    production.set_waiter(completing)
    await store.update_run(r["id"], status="RUNNING", error=None)     # what /retry does
    r = await pipeline.run_until_blocked(r["id"])
    assert r["stage"] == "QC"
    assert len(await _video_reqs(r)) == 3


async def test_failed_clip_is_recorded_and_others_continue(world):
    r = await to_credit_gate()
    await pipeline.approve(r["id"], "ASSETS")

    async def one_fails(ids, poll_s=None, **kw):
        out = {}
        for n, i in enumerate(ids):
            await crud.update_request(i, status="FAILED" if n == 0 and len(ids) == 3 else "COMPLETED")
            out[i] = await crud.get_request(i)
        return out
    production.set_waiter(one_fails)
    r = await pipeline.run_until_blocked(r["id"])
    assert r["stage"] == "QC" and list(r["plan"]["failed"].values()) == ["video"]


async def test_out_of_credit_account_stops_the_film_at_a_gate_and_resumes_after(world):
    """Account rotation step 3: the worker holds the film's requests; the director asks the user instead of waiting."""
    from agent.db import account_crud
    r = await to_credit_gate()
    pid = r["plan"]["ids"]["project_id"]
    await crud.update_project(pid, flow_account="a@gmail.com")
    await account_crud.mark_exhausted("a@gmail.com", "PUBLIC_ERROR_USER_QUOTA_REACHED")
    production.reset_waiter()                      # the real poll: requests stay PENDING
    await pipeline.approve(r["id"], "ASSETS")
    r = await pipeline.run_until_blocked(r["id"])
    assert (r["status"], r["gate"]) == ("WAITING_GATE", "ACCOUNT_EXHAUSTED")
    assert r["plan"]["gate_payload"] == {"account": "a@gmail.com", "waiting": 3, "stage": "VIDEOS"}
    n = len(await _video_reqs(r))

    async def waiter(ids, poll_s=None, **kw):
        return await _complete(ids)
    production.set_waiter(waiter)
    await pipeline.approve(r["id"], "ACCOUNT_EXHAUSTED")   # "the account has credit again"
    assert (await account_crud.get("a@gmail.com"))["status"] == "ACTIVE"
    r = await pipeline.run_until_blocked(r["id"])
    assert r["stage"] == "QC" and len(await _video_reqs(r)) == n   # same requests, none duplicated


async def test_resume_after_pause_sends_the_stopped_clips_again(world):
    """23/10 Blue Morning: pause failed the queued clips ("never sent"), and resume adopted those rows as failed — the
    film fell to the failed-shots gate with nothing re-sent. Stopped clips go again on the budget they already hold; a
    clip Flow refused stays failed for the user to decide."""
    r = await to_credit_gate()
    await pipeline.approve(r["id"], "ASSETS")
    calls = {"n": 0}

    async def pause_on_videos(ids, poll_s=None, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            for n, i in enumerate(ids):
                await crud.update_request(i, status="FAILED",
                                          error_message="NO_MEDIA_CREATED: refused" if n == 0 else production.STOPPED)
            await store.update_run(r["id"], status="PAUSED")
            raise production.Paused(r["id"])                          # what the real poller does
        done = [i for i in ids if (await crud.get_request(i))["status"] != "FAILED"]
        return await _complete(done) | {i: await crud.get_request(i) for i in ids if i not in done}
    production.set_waiter(pause_on_videos)
    r = await pipeline.run_until_blocked(r["id"])
    await store.update_run(r["id"], status="RUNNING")                  # what /resume does
    r = await pipeline.run_until_blocked(r["id"])
    vids = await _video_reqs(r)
    assert len(vids) == 5 and sorted(q["status"] for q in vids).count("COMPLETED") == 2
    assert list(r["plan"]["failed"].values()) == ["video"] and r["spent"]["videos"] == 3
