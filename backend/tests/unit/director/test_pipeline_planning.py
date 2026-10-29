import pytest

from agent.director import brain, pipeline, store
from tests.unit.director.fake_plans import fake_responses


@pytest.fixture
def fake(test_db, monkeypatch):
    def install(responses):
        fb = brain.FakeBrain(responses)
        brain.set_brain(fb)
        return fb
    # planning tests stop before INGEST
    monkeypatch.setitem(pipeline.HANDLERS, "INGEST", pipeline._stop_here)
    yield install
    brain.reset_brain()


async def new_run():
    return await store.create_run({"text": "love story", "target_s": 15}, {})


async def test_runs_brief_to_edit_review(fake):
    fb = fake(fake_responses())
    r = await new_run()
    r = await pipeline.run_until_blocked(r["id"])
    assert r["stage"] == "INGEST"
    assert [c[0] for c in fb.calls] == ["producer", "writer", "director", "dp", "editor"]
    assert len(r["plan"]["shotlist"]["shots"]) == 3
    steps = await store.list_steps(r["id"])
    assert [s["stage"] for s in steps] == ["BRIEF", "STORY", "SHOTLIST", "PROMPTS", "EDIT_REVIEW"]


async def test_lint_errors_are_fed_back_then_fixed(fake):
    import copy
    resp = fake_responses()
    good = resp["director"][0]
    bad = copy.deepcopy(good)
    bad["shots"][0]["actions"] = bad["shots"][0]["actions"] * 2      # 4 actions → actions_count
    resp["director"] = [bad, good]
    fb = fake(resp)
    r = await pipeline.run_until_blocked((await new_run())["id"])
    assert r["stage"] == "INGEST"
    director_calls = [p for role, p in fb.calls if role == "director"]
    assert len(director_calls) == 2 and any("actions_count" in e for e in director_calls[1]["lint_errors"])


async def test_lint_failing_three_times_fails_the_run(fake):
    resp = fake_responses()
    bad = dict(resp["director"][0]); bad["shots"] = [dict(bad["shots"][0], cast=["Nobody"])] + bad["shots"][1:]
    resp["director"] = [bad]
    fake(resp)
    r = await pipeline.run_until_blocked((await new_run())["id"])
    assert r["status"] == "FAILED" and r["stage"] == "SHOTLIST" and "cast_unknown" in r["error"]


async def test_low_editor_score_loops_back_at_most_twice(fake):
    resp = fake_responses(editor_score=40)
    resp["editor"] = [{"score": 40, "checklist": {}, "fixes": [
        {"target_stage": "PROMPTS", "shot_id": "s1", "issue": "camera does two jobs"}]}]
    fb = fake(resp)
    r = await pipeline.run_until_blocked((await new_run())["id"])
    assert r["stage"] == "INGEST"
    assert [c[0] for c in fb.calls].count("dp") == 3            # first + 2 loops
    assert any("camera does two jobs" in n for n in r["plan"]["revision_notes"])
    assert r["plan"]["warnings"]                                 # still below score → warning


async def test_pause_stops_between_stages(fake):
    fake(fake_responses())
    r = await new_run()
    await store.update_run(r["id"], status="PAUSED")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["stage"] == "BRIEF" and r["status"] == "PAUSED"


async def test_unknown_stage_fails_run(fake):
    r = await new_run()
    await store.update_run(r["id"], stage="NOPE")
    r = await pipeline.run_until_blocked(r["id"])
    assert r["status"] == "FAILED" and "no handler" in r["error"]


async def test_unexpected_exception_fails_run(fake, monkeypatch):
    async def boom(run):
        raise RuntimeError("kaboom")
    monkeypatch.setitem(pipeline.HANDLERS, "BRIEF", boom)
    r = await pipeline.run_until_blocked((await new_run())["id"])
    assert r["status"] == "FAILED" and "RuntimeError" in r["error"] and "kaboom" in r["error"]


async def test_gate_waits_and_keeps_stage(fake, monkeypatch):
    async def gate(run):
        raise pipeline.Gate("X", {"a": 1})
    monkeypatch.setitem(pipeline.HANDLERS, "BRIEF", gate)
    r = await pipeline.run_until_blocked((await new_run())["id"])
    assert r["status"] == "WAITING_GATE" and r["gate"] == "X" and r["stage"] == "BRIEF"


async def test_idea_asking_for_voice_keeps_voiceover_even_if_producer_misses_it(fake):
    fake(fake_responses())
    r = await store.create_run({"text": "Quảng cáo viên nén xơ dừa. Có lồng tiếng giới thiệu sản phẩm", "target_s": 15}, {})
    await pipeline.h_brief(r)
    assert r["plan"]["brief"]["voice"] == "voiceover" and r["plan"]["brief"]["voice_style"]


async def test_a_narrated_written_story_gets_a_voice_on_auto(fake):
    """19/10 Daniel: the pasted story said "Giọng kể trầm" — not one of the old trigger words."""
    for text in ("Cảnh 1. Giọng kể trầm, chậm rãi: Tên ông là Daniel.", "Narrator: his name was Daniel."):
        fake(fake_responses())
        r = await store.create_run({"text": text, "target_s": 15}, {})
        await pipeline.h_brief(r)
        assert r["plan"]["brief"]["voice"] == "voiceover"


async def test_users_voice_choice_overrides_the_idea(fake):
    fake(fake_responses())
    r = await store.create_run({"text": "Có lồng tiếng giới thiệu", "target_s": 15, "voice": "none"}, {})
    await pipeline.h_brief(r)
    assert r["plan"]["brief"]["voice"] == "none"
    fake(fake_responses())
    r = await store.create_run({"text": "love story", "target_s": 15, "voice": "dialogue"}, {})
    await pipeline.h_brief(r)
    assert r["plan"]["brief"]["voice"] == "dialogue" and r["plan"]["brief"]["voice_style"]


async def test_users_language_choice_is_the_films_language(fake):
    fake(fake_responses())
    r = await store.create_run({"text": "Truyện cổ tích", "target_s": 15, "language": "en", "voice": "voiceover"}, {})
    await pipeline.h_brief(r)
    assert r["plan"]["brief"]["language"] == "en"
    fake(fake_responses())
    r = await store.create_run({"text": "no choice made", "target_s": 15}, {})
    await pipeline.h_brief(r)
    assert r["plan"]["brief"]["language"] == "en"     # directive B4 (19/10): English unless asked


async def test_users_creativity_choice_reaches_the_brief(fake):
    """Directive B9: the creativity level chosen on the idea is in the brief every role reads."""
    fake(fake_responses())
    r = await store.create_run({"text": "ông già mất vợ", "target_s": 60, "creativity": "bold"}, {})
    await pipeline.h_brief(r)
    assert r["plan"]["brief"]["creativity"] == "bold"
    fake(fake_responses())
    r = await store.create_run({"text": "old run, no choice", "target_s": 15}, {})
    await pipeline.h_brief(r)
    assert r["plan"]["brief"]["creativity"] == "balanced"


async def test_film_mode_reaches_the_brief_and_brings_playbook_09_to_the_roles(fake):
    """Directive B12: the film mode chosen on the idea is in the brief; a continuous film's roles read playbook 09."""
    fb = fake(fake_responses())
    r = await store.create_run({"text": "a woman remembers Christmas", "target_s": 60, "film_mode": "continuous"}, {})
    await pipeline.h_brief(r)
    assert r["plan"]["brief"]["film_mode"] == "continuous"
    await pipeline.h_story(r)
    role, payload = fb.calls[-1]
    assert role == "writer" and "CONTINUOUS MODE" in payload["_context"]
    fake(fake_responses())
    r = await store.create_run({"text": "old run, no choice", "target_s": 15}, {})
    await pipeline.h_brief(r)
    assert r["plan"]["brief"]["film_mode"] == "cut"


async def test_writer_gets_the_projects_existing_assets_and_ingest_reuses_them(fake):
    from agent.db import crud
    fb = fake(fake_responses())
    p = await crud.create_project(name="p")
    ch = await crud.create_character(name="Minh Khoa", entity_type="character", description="tall man")
    await crud.update_character(ch["id"], media_id="m-1")
    await crud.link_character_to_project(p["id"], ch["id"])
    r = await store.create_run({"text": "love story", "target_s": 15}, {})
    r["plan"]["ids"] = {"project_id": p["id"], "video_id": None, "entities": {}, "scenes": {}}
    await pipeline.h_brief(r)
    await pipeline.h_story(r)
    payload = [c for c in fb.calls if c[0] == "writer"][-1][1]
    assert payload["existing_assets"][0]["name"] == "Minh Khoa"
    assert r["plan"]["ids"]["entities"]["Minh Khoa"] == ch["id"]


async def test_turned_off_roles_are_never_called(fake):
    """Directive A5: producer and editor off → the brief comes from the idea node, the script goes unreviewed."""
    fb = fake(fake_responses())
    r = await store.create_run({"text": "Có lồng tiếng: quảng cáo cà phê", "target_s": 30, "language": "en",
                                "agents": {"producer": False, "editor": False, "qc": True, "coach": True}}, {})
    r = await pipeline.run_until_blocked(r["id"])
    assert [c[0] for c in fb.calls] == ["writer", "director", "dp"]
    assert r["stage"] == "INGEST" and r["plan"]["editor"] == {"skipped": True}
    b = r["plan"]["brief"]
    assert (b["target_s"], b["language"], b["voice"]) == (30, "en", "voiceover") and b["voice_style"]


async def test_the_producer_still_reads_pictures(fake):
    fb = fake(fake_responses())
    r = await store.create_run({"text": "love story", "target_s": 15, "agents": {"producer": False},
                                "images": [{"file": "/x/1.jpg", "note": None}]}, {})
    await pipeline.h_brief(r)
    assert [c[0] for c in fb.calls] == ["producer"]


async def test_a_lint_retry_rewrites_only_the_broken_prompts(fake):
    """Bước 7 (19/10): one bad prompt must not send all of them back (Daniel: 44 rewritten on Opus)."""
    resp = fake_responses()
    good = resp["dp"][0]
    bad = {"prompts": [dict(p) for p in good["prompts"]]}
    bad["prompts"][0]["video_prompt"] = bad["prompts"][0]["video_prompt"].replace(
        "0-6s: hai người cùng trộn bột. 6-10s:", "0-3s: trộn bột. 3-6s: rắc bột. 6-10s:")
    fixed_s1 = {"prompts": [dict(good["prompts"][0], end_frame="sửa xong")]}
    seen = []
    fb = brain.FakeBrain(dict(resp, dp=[bad, fixed_s1]))

    async def recorder(role, payload, schema, **kw):
        seen.append((role, payload, kw))
        return await fb(role, payload, schema, **kw)
    brain.set_brain(recorder)
    r = await store.create_run({"text": "love story", "target_s": 15}, {})
    r = await pipeline.run_until_blocked(r["id"])
    dp = [(p, kw) for role, p, kw in seen if role == "dp"]
    assert len(dp) == 2
    retry, kw = dp[1]
    assert [s["id"] for s in retry["shotlist"]["shots"]] == ["s1"] and kw["escalate"] is False
    assert any("[s1]" in e for e in retry["lint_errors"])
    prompts = r["plan"]["prompts"]["prompts"]
    assert prompts[0]["end_frame"] == "sửa xong" and prompts[1] == good["prompts"][1]
