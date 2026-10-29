import pytest

from agent.db import crud
from agent.director import brain, cut, pipeline, production, stages_film, store
from tests.unit.director.fake_plans import fake_responses, finish


@pytest.fixture
def world(test_db, monkeypatch, tmp_path):
    async def done(ids, poll_s=None, **kw):
        out = {}
        for i in ids:
            await finish(i, "COMPLETED")
            out[i] = row = await crud.get_request(i)
            if row["type"].startswith("GENERATE_VIDEO") and row.get("scene_id"):   # like the real worker
                await crud.update_scene(row["scene_id"], horizontal_video_status="COMPLETED")
        return out
    production.set_waiter(done)

    async def fake_local(scene, ori, dest):
        p = tmp_path / f"{scene['id']}.mp4"
        p.write_bytes(b"x")
        return p
    monkeypatch.setattr(cut, "local_clip", fake_local)
    monkeypatch.setattr(stages_film, "_contact_sheets", lambda path, out_dir: [str(path)])
    rendered = {}

    async def fake_render(paths, trims, out_path, size, music_path=None, edit=None):
        rendered.update(paths=paths, trims=trims, out=out_path)
        return out_path
    monkeypatch.setattr(cut, "render_cut", fake_render)
    monkeypatch.setitem(pipeline.HANDLERS, "RETRO", pipeline._stop_here)
    yield rendered
    brain.reset_brain()
    production.reset_waiter()


async def to_qc(responses, agents=None):
    fb = brain.FakeBrain(responses)
    brain.set_brain(fb)
    to_qc.brain = fb
    r = await store.create_run({"text": "love", "target_s": 15} | ({"agents": agents} if agents else {}), {})
    r = await pipeline.run_until_blocked(r["id"])
    await pipeline.approve(r["id"], "SCRIPT")
    r = await pipeline.run_until_blocked(r["id"])
    await pipeline.approve(r["id"], "ASSETS")
    return await pipeline.run_until_blocked(r["id"])


async def test_all_pass_goes_to_cut_with_qc_trims(world):
    r = await to_qc(fake_responses())
    assert r["stage"] == "RETRO" and r["final_path"].endswith("final.mp4")
    assert world["trims"][0][0] >= 0.5                                      # inside the QC window (may sit on the action)
    total = sum(b - a for a, b in world["trims"])
    assert 15 <= total <= 15 * 1.4 + 0.1        # ~15s asked: the film follows the material, never past 1.4× (E1b)


async def test_fail_triggers_one_regen_within_budget(world):
    resp = fake_responses()
    fail = {"items": [{"shot_id": "s1", "verdict": "FAIL", "issues": ["face warped"], "trim_in_s": 0,
                       "trim_out_s": 10}]}
    ok = resp["qc"][0]
    resp["qc"] = [fail, ok, ok, ok]
    r = await to_qc(resp)
    regens = [q for q in await crud.list_requests(project_id=r["plan"]["ids"]["project_id"])
              if q["id"] == r["plan"]["requests"].get("regen:s1")]
    assert len(regens) == 1 and r["spent"]["regens"] == 1


async def test_failed_shot_stops_at_gate_then_drop_continues(world):
    async def first_video_fails(ids, poll_s=None, **kw):
        out = {}
        for n, i in enumerate(ids):
            video = (await crud.get_request(i))["type"].startswith("GENERATE_VIDEO")
            out[i] = await finish(i, "FAILED" if video and n == 0 else "COMPLETED")
        return out
    production.set_waiter(first_video_fails)
    r = await to_qc(fake_responses())
    assert (r["gate"], r["stage"]) == ("SHOT_FAILED", "CUT")
    await pipeline.resolve_shot_failure(r["id"], "drop")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["stage"] == "RETRO" and len(world["paths"]) == 2


def _fail_s1(resp):
    fail = {"items": [{"shot_id": "s1", "verdict": "FAIL", "issues": ["face warped"], "trim_in_s": 0,
                       "trim_out_s": 10}]}
    ok = resp["qc"][0]
    resp["qc"] = [fail, ok, ok, ok]
    return resp


async def test_regen_resets_scene_status_and_is_a_new_request(world, monkeypatch):
    from agent.worker.processor import _is_already_completed
    seen = {}
    orig = production.request_for

    async def spy(run, key, kind, **kw):
        if key == "regen:s1":
            seen["status"] = (await crud.get_scene(kw["scene_id"]))["horizontal_video_status"]
        rid = await orig(run, key, kind, **kw)
        if key == "regen:s1":     # the worker would pick the request up now
            seen["skipped"] = await _is_already_completed(await crud.get_request(rid), "HORIZONTAL")
        return rid
    monkeypatch.setattr(production, "request_for", spy)
    r = await to_qc(_fail_s1(fake_responses()))
    reqs = r["plan"]["requests"]
    assert seen["status"] == "PENDING" and reqs["regen:s1"] != reqs["vid:s1"]
    assert seen["skipped"] is False


async def test_reqc_after_regen_sees_fresh_clip(world, monkeypatch):
    calls = []

    async def fresh_local(scene, ori, dest):
        dest.mkdir(parents=True, exist_ok=True)
        p = dest / f"{scene['id']}.mp4"
        if not p.exists():
            p.write_bytes(f"v{len(calls)}".encode())
            calls.append(scene["id"])
        return p
    monkeypatch.setattr(cut, "local_clip", fresh_local)
    seen = []
    monkeypatch.setattr(stages_film, "_contact_sheets", lambda path, out_dir: seen.append((out_dir.name, path.read_bytes())) or [])
    await to_qc(_fail_s1(fake_responses()))
    s1 = [b for name, b in seen if name == "s1"]
    assert len(s1) == 2 and s1[0] != s1[1]      # s1 first pass vs post-regen pass


async def test_no_regen_budget_keeps_clip_with_note(world):
    brain.set_brain(brain.FakeBrain(_fail_s1(fake_responses())))
    r = await store.create_run({"text": "love", "target_s": 15}, {})
    r = await pipeline.run_until_blocked(r["id"])
    await pipeline.approve(r["id"], "SCRIPT")
    r = await pipeline.run_until_blocked(r["id"])
    await pipeline.approve(r["id"], "ASSETS", {"videos": 3})
    r = await pipeline.run_until_blocked(r["id"])
    q = r["plan"]["qc"]["s1"]
    assert q["verdict"] == "FAIL" and "no regen budget left" in q["issues"] and r["stage"] == "RETRO"


async def test_stop_resolution_fails_run(world):
    async def first_video_fails(ids, poll_s=None, **kw):
        out = {}
        for n, i in enumerate(ids):
            video = (await crud.get_request(i))["type"].startswith("GENERATE_VIDEO")
            out[i] = await finish(i, "FAILED" if video and n == 0 else "COMPLETED")
        return out
    production.set_waiter(first_video_fails)
    r = await to_qc(fake_responses())
    r = await pipeline.resolve_shot_failure(r["id"], "stop")
    assert r["status"] == "FAILED" and r["error"] == "stopped by user"


async def test_dropping_every_shot_is_a_clear_failure(world):
    async def all_fail(ids, poll_s=None, **kw):     # every clip fails; the reference images are fine
        out = {}
        for i in ids:
            video = (await crud.get_request(i))["type"].startswith("GENERATE_VIDEO")
            out[i] = await finish(i, "FAILED" if video else "COMPLETED")
        return out
    production.set_waiter(all_fail)
    r = await to_qc(fake_responses())
    assert r["gate"] == "SHOT_FAILED"
    await pipeline.resolve_shot_failure(r["id"], "drop")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["status"] == "FAILED" and "no shots left to cut" in r["error"]


async def test_recut_uses_current_takes_and_resets_trims_of_swapped_ones(world):
    r = await to_qc(fake_responses())
    assert world["trims"][0][0] >= 0.5                                   # QC window of the reviewed take
    plan = r["plan"]
    plan["qc"]["s1"]["media_id"] = "reviewed-take"
    await store.update_run(r["id"], plan=plan)
    await crud.update_scene(plan["ids"]["scenes"]["s1"], horizontal_video_media_id="picked-take")
    r = await pipeline.recut(r["id"])
    a, b = world["trims"][0]
    assert r["status"] == "DONE" and a >= pipeline.UNREVIEWED_TRIM[0] and b <= pipeline.UNREVIEWED_TRIM[1]


async def test_qc_off_keeps_every_clip_without_watching_it(world):
    """Directive A5: no QC role → no AI call per clip, each clip keeps its default middle window."""
    r = await to_qc(fake_responses(), agents={"qc": False})
    assert r["stage"] == "RETRO" and "qc" not in [c[0] for c in to_qc.brain.calls]
    assert all(q.get("skipped") and q["verdict"] == "PASS" for q in r["plan"]["qc"].values())
    assert world["trims"][0] == (pipeline.UNREVIEWED_TRIM[0], pipeline.UNREVIEWED_TRIM[1])


async def test_qc_reviews_clips_in_batches(world, monkeypatch):
    """Bước 7 (19/10): 19 QC calls cost $2.08 on Daniel, each re-reading the role prompt; up to 4 clips per call."""
    monkeypatch.setattr(stages_film, "QC_BATCH", 2)
    r = await to_qc(fake_responses())
    qc_calls = [p for role, p in to_qc.brain.calls if role == "qc"]
    assert [len(p["clips"]) for p in qc_calls] == [2, 1]           # 3 clips → 2 calls
    assert all(q["trim_in_s"] == 0.5 for q in r["plan"]["qc"].values())


async def test_a_clip_left_out_of_the_answer_passes_unreviewed(world):
    resp = fake_responses()
    resp["qc"] = [{"items": [resp["qc"][0]["items"][0]]}]          # only s1 answered for the batch of 3
    r = await to_qc(resp)
    assert r["plan"]["qc"]["s2"]["issues"] == ["QC did not return this clip"]
    assert r["plan"]["qc"]["s2"]["trim_in_s"] == pipeline.UNREVIEWED_TRIM[0]


async def test_a_failed_clip_regenerated_by_hand_joins_the_cut(world):
    """20/10: clip 4 failed, the user re-made it on the canvas — 🎬 Ghép phim must use it, not ask to drop it."""
    async def first_video_fails(ids, poll_s=None, **kw):
        out = {}
        for n, i in enumerate(ids):
            video = (await crud.get_request(i))["type"].startswith("GENERATE_VIDEO")
            out[i] = await finish(i, "FAILED" if video and n == 0 else "COMPLETED")
        return out
    production.set_waiter(first_video_fails)
    r = await to_qc(fake_responses())
    assert r["gate"] == "SHOT_FAILED" and r["plan"]["gate_payload"]["scenes"] == [1]
    await crud.update_scene(r["plan"]["ids"]["scenes"]["s1"], horizontal_video_status="COMPLETED")
    await pipeline.resolve_shot_failure(r["id"], "retry")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["stage"] == "RETRO" and len(world["paths"]) == 3
    a, b = world["trims"][0]
    assert pipeline.UNREVIEWED_TRIM[0] <= a and b <= pipeline.UNREVIEWED_TRIM[1] and "s1" not in r["plan"]["failed"]


async def test_retry_while_the_clip_is_still_missing_asks_again(world):
    async def first_video_fails(ids, poll_s=None, **kw):
        out = {}
        for n, i in enumerate(ids):
            video = (await crud.get_request(i))["type"].startswith("GENERATE_VIDEO")
            out[i] = await finish(i, "FAILED" if video and n == 0 else "COMPLETED")
        return out
    production.set_waiter(first_video_fails)
    r = await to_qc(fake_responses())
    await pipeline.resolve_shot_failure(r["id"], "retry")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["gate"] == "SHOT_FAILED"


async def test_a_cancelled_film_whose_clips_were_all_made_by_hand_can_be_cut(world):
    """22/10 Old Walt: cancelled at REFS, the user then made all 6 clips on the canvas; the film node had no button."""
    r = await to_qc(fake_responses())
    plan = r["plan"]
    plan.pop("qc")                                                    # never reached QC
    await store.update_run(r["id"], plan=plan, status="CANCELLED", stage="REFS")
    r = await pipeline.recut(r["id"])
    assert r["status"] == "DONE" and r["final_path"]
    await crud.update_scene(plan["ids"]["scenes"]["s1"], horizontal_video_status="FAILED")
    run = await store.get_run(r["id"])
    assert await pipeline.clips_missing(run) == [1]
