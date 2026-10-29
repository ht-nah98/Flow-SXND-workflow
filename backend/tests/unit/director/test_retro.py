from agent.director import brain, lessons, pipeline, store


async def test_retro_records_lessons_and_finishes(test_db):
    await lessons.ensure_seed()
    fb = brain.FakeBrain({"coach": [{"lessons": [{"scope": "omni_flash", "rule": "avoid fast orbit with r2v",
                                                   "evidence": [{"shot_id": "s1", "issue": "warp"}]}]}]})
    brain.set_brain(fb)
    try:
        r = await store.create_run({"text": "t", "target_s": 15}, {})
        await store.update_run(r["id"], stage="RETRO", plan={
            "qc": {"s1": {"verdict": "FAIL", "issues": ["warp"]}, "s2": {"verdict": "PASS", "issues": []}},
            "prompts": {"prompts": [{"shot_id": "s1", "video_prompt": "p1", "end_frame": "e"}]},
            "shotlist": {"shots": []}})
        r = await pipeline.run_until_blocked(r["id"])
    finally:
        brain.reset_brain()
    assert r["status"] == "DONE"
    payload = fb.calls[0][1]
    assert [i["shot_id"] for i in payload["flagged"]] == ["s1"]
    assert any(l["rule"] == "avoid fast orbit with r2v" for l in await store.list_lessons(status="PROPOSED"))


async def test_retro_failure_never_blocks_done(test_db):
    brain.set_brain(brain.FakeBrain({}))   # coach has no answer -> BrainError
    try:
        r = await store.create_run({"text": "t", "target_s": 15}, {})
        await store.update_run(r["id"], stage="RETRO", plan={"qc": {}, "prompts": {"prompts": []},
                                                              "shotlist": {"shots": []}})
        r = await pipeline.run_until_blocked(r["id"])
    finally:
        brain.reset_brain()
    assert r["status"] == "DONE"


async def test_coach_off_finishes_without_learning(test_db):
    fb = brain.FakeBrain({})
    brain.set_brain(fb)
    try:
        r = await store.create_run({"text": "t", "target_s": 15, "agents": {"coach": False}}, {})
        await store.update_run(r["id"], stage="RETRO", plan={"qc": {}, "prompts": {"prompts": []},
                                                              "shotlist": {"shots": []}})
        r = await pipeline.run_until_blocked(r["id"])
    finally:
        brain.reset_brain()
    assert r["status"] == "DONE" and fb.calls == []
