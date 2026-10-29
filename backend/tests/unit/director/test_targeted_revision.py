"""Targeted revision (19/10): an editor fix rewrites only what it names, not the whole film."""
import pytest

from agent.director import brain, pipeline, store, targeted
from agent.director.schemas import EditorFix, ShotPrompts
from tests.unit.director.fake_plans import fake_responses
from tests.unit.director.fixtures import fmv_prompts, fmv_shotlist, fmv_story


def test_plan_revision_splits_named_shots_from_film_wide_fixes():
    fixes = [EditorFix(target_stage="PROMPTS", shot_id="s1", issue="a"),
             EditorFix(target_stage="PROMPTS", shot_id="s1", issue="b"),
             EditorFix(target_stage="SHOTLIST", issue="pacing"),
             EditorFix(target_stage="STORY", issue="ages")]
    assert targeted.plan_revision(fixes) == {"shots": {"PROMPTS": ["s1"]}, "film_wide": ["SHOTLIST"]}


def test_story_changes_finds_edited_beats_and_cast_only():
    old = fmv_story()
    new = old.model_copy(deep=True)
    new.beats[1].summary = "He leaves at dawn instead."
    new.cast[0].description = "older, grey at the temples"
    assert targeted.story_changes(old, new) == ({"b2"}, {old.cast[0].name})
    fewer = old.model_copy(update={"beats": old.beats[:1]})
    assert targeted.story_changes(old, fewer) is None            # beat list changed: re-plan everything


def test_merge_shots_keeps_other_beats_renumbers_and_avoids_id_clashes():
    old, story = fmv_shotlist(), fmv_story()
    s3 = old.shots[2]
    new = [s3.model_copy(update={"id": "s1", "order": 1, "idea": "new A"}),     # clashes with a kept shot id
           s3.model_copy(update={"id": "s9", "order": 2, "idea": "new B"}),
           old.shots[0].model_copy(update={"idea": "not asked"})]               # beat b1 was not asked about
    merged, touched = targeted.merge_shots(old, new, {"b2"}, story)
    assert [(s.id, s.order, s.idea) for s in merged.shots] == [
        ("s1", 1, old.shots[0].idea), ("s2", 2, old.shots[1].idea), ("s1-r1", 3, "new A"), ("s9", 4, "new B")]
    assert touched == {"s1-r1", "s9"}


def test_merge_prompts_replaces_only_the_rewritten_and_drops_removed_shots():
    old, shots = fmv_prompts(), fmv_shotlist()
    new = ShotPrompts(prompts=[p.model_copy(update={"video_prompt": "NEW " + p.video_prompt}) for p in old.prompts])
    fewer = shots.model_copy(update={"shots": shots.shots[:2]})
    out = targeted.merge_prompts(old, new, fewer, {"s2"})
    assert [p.video_prompt.startswith("NEW") for p in out.prompts] == [False, True]


@pytest.fixture
def fake(test_db, monkeypatch):
    monkeypatch.setitem(pipeline.HANDLERS, "INGEST", pipeline._stop_here)
    yield lambda r: brain.set_brain(fb := brain.FakeBrain(r)) or fb
    brain.reset_brain()


async def test_a_story_fix_replans_only_the_changed_beat(fake):
    resp = fake_responses()
    story2 = fmv_story().model_dump()
    story2["beats"][1]["summary"] = "Nam leaves at dawn, the cake untouched."
    resp["writer"] = [fmv_story().model_dump(), story2]
    resp["editor"] = [{"score": 50, "checklist": {}, "fixes": [{"target_stage": "STORY", "issue": "ending is flat"}]},
                      {"score": 90, "checklist": {}, "fixes": []}]
    fb = fake(resp)
    r = await pipeline.run_until_blocked((await store.create_run({"text": "love story", "target_s": 15}, {}))["id"])
    assert r["stage"] == "INGEST" and "revise" not in r["plan"]
    writer = [p for role, p in fb.calls if role == "writer"]
    assert "previous_story" not in writer[0] and writer[1]["previous_story"]["beats"][1]["id"] == "b2"
    director = [p for role, p in fb.calls if role == "director"]
    assert [s["id"] for s in director[1]["previous_shots"]] == ["s3"] and "b2" in director[1]["task"]
    dp = [p for role, p in fb.calls if role == "dp"]
    assert [s["id"] for s in dp[1]["shotlist"]["shots"]] == ["s3"]               # only the re-planned shot
    assert [s["id"] for s in r["plan"]["shotlist"]["shots"]] == ["s1", "s2", "s3"]
    assert len(r["plan"]["prompts"]["prompts"]) == 3


async def test_a_prompt_fix_rewrites_only_that_prompt(fake):
    resp = fake_responses()
    resp["editor"] = [{"score": 50, "checklist": {}, "fixes": [{"target_stage": "PROMPTS", "shot_id": "s2",
                                                              "issue": "two actions"}]},
                      {"score": 90, "checklist": {}, "fixes": []}]
    fb = fake(resp)
    r = await pipeline.run_until_blocked((await store.create_run({"text": "love story", "target_s": 15}, {}))["id"])
    roles = [role for role, _ in fb.calls]
    assert roles.count("writer") == 1 and roles.count("director") == 1
    dp = [p for role, p in fb.calls if role == "dp"]
    assert [s["id"] for s in dp[1]["shotlist"]["shots"]] == ["s2"]
    assert r["stage"] == "INGEST"


async def test_a_film_wide_shotlist_fix_still_replans_everything(fake):
    resp = fake_responses()
    resp["editor"] = [{"score": 50, "checklist": {}, "fixes": [{"target_stage": "SHOTLIST", "issue": "pacing"}]},
                      {"score": 90, "checklist": {}, "fixes": []}]
    fb = fake(resp)
    await pipeline.run_until_blocked((await store.create_run({"text": "love story", "target_s": 15}, {}))["id"])
    director = [p for role, p in fb.calls if role == "director"]
    dp = [p for role, p in fb.calls if role == "dp"]
    assert "task" not in director[1] and len(dp[1]["shotlist"]["shots"]) == 3
