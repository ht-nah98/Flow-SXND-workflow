from agent.director import lessons, store
from agent.director.schemas import LessonDraft, Retro


async def test_seed_is_active_and_idempotent(test_db):
    await lessons.ensure_seed(); await lessons.ensure_seed()
    active = await store.list_lessons(status="ACTIVE")
    assert len(active) == len(lessons.SEED_LESSONS)
    assert any("2 actions" in l["rule"] for l in active)


async def test_retro_lesson_activates_after_two_failures(test_db):
    ev = {"shot_id": "s1", "issue": "face warped during orbit"}
    [l] = await lessons.apply_retro(Retro(lessons=[LessonDraft(scope="omni_flash", rule="avoid /orbit-360 in r2v",
                                                                evidence=[ev])]), "run1")
    assert l["status"] == "PROPOSED"
    [l] = await lessons.apply_retro(Retro(lessons=[LessonDraft(scope="omni_flash", rule="", existing_id=l["id"],
                                                                evidence=[ev | {"shot_id": "s9"}])]), "run2")
    assert l["status"] == "ACTIVE" and len(l["evidence"]) == 2


async def test_user_lessons_are_active_immediately_and_retired_stay_retired(test_db):
    [l] = await lessons.apply_retro(Retro(lessons=[LessonDraft(scope="prompt", rule="no slow motion")]),
                                    "run1", source="user")
    assert l["status"] == "ACTIVE"
    await store.update_lesson(l["id"], status="RETIRED")
    [l] = await lessons.apply_retro(Retro(lessons=[LessonDraft(scope="prompt", rule="", existing_id=l["id"],
                                                                evidence=[{"shot_id": "a", "issue": "b"}] * 3)]), "r")
    assert l["status"] == "RETIRED"


async def test_context_only_includes_active_lessons_in_role_scopes(test_db):
    await lessons.ensure_seed()
    await store.add_lesson("story", "STORY-ONLY RULE", "user", "ACTIVE")
    await store.add_lesson("prompt", "OFF RULE", "user", "RETIRED")
    dp = await lessons.context_for("dp")
    assert "2 actions" in dp and "STORY-ONLY RULE" not in dp and "OFF RULE" not in dp
    assert "STORY-ONLY RULE" in await lessons.context_for("writer")


def test_stats_count_pass_rates():
    run = {"plan": {
        "shotlist": {"shots": [
            {"id": "a", "mode": "r2v", "duration_s": 6, "commands": ["/orbit-360"], "transition": None},
            {"id": "b", "mode": "r2v", "duration_s": 6, "commands": ["/orbit-360"],
             "transition": {"technique": "/pull-back"}}]},
        "qc": {"a": {"verdict": "FAIL"}, "b": {"verdict": "PASS"}}}}
    st = lessons.compute_stats([run, run])
    assert st["mode"]["r2v"] == [2, 4]
    assert st["command"]["orbit-360"] == [2, 4]
    assert st["transition"]["pull-back"] == [2, 2]


async def test_unknown_existing_id_creates_nothing(test_db):
    out = await lessons.apply_retro(Retro(lessons=[LessonDraft(scope="prompt", rule="some rule", existing_id="nope",
                                                                evidence=[{"shot_id": "a", "issue": "b"}])]), "r1")
    assert out == [] and await store.list_lessons() == []


async def test_blank_rule_creates_nothing(test_db):
    out = await lessons.apply_retro(Retro(lessons=[LessonDraft(scope="prompt", rule="   ")]), "r1", source="user")
    assert out == [] and await store.list_lessons() == []


async def test_user_endorsement_activates_proposed_lesson(test_db):
    [l] = await lessons.apply_retro(Retro(lessons=[LessonDraft(scope="prompt", rule="keep hands visible",
                                                                evidence=[{"shot_id": "a", "issue": "x"}])]), "run1")
    assert l["status"] == "PROPOSED"
    [l] = await lessons.apply_retro(Retro(lessons=[LessonDraft(scope="prompt", rule="", existing_id=l["id"])]),
                                    "run2", source="user")
    assert l["status"] == "ACTIVE"


async def test_same_evidence_applied_twice_counts_once(test_db):
    ev = {"shot_id": "s1", "issue": "warp"}
    [l] = await lessons.apply_retro(Retro(lessons=[LessonDraft(scope="omni_flash", rule="avoid orbit",
                                                                evidence=[ev])]), "run1")
    [l] = await lessons.apply_retro(Retro(lessons=[LessonDraft(scope="omni_flash", rule="", existing_id=l["id"],
                                                                evidence=[ev])]), "run1")
    assert len(l["evidence"]) == 1 and l["status"] == "PROPOSED"


def test_compute_stats_ignores_malformed_shot():
    run = {"plan": {
        "shotlist": {"shots": [
            {"id": "a", "duration_s": 6, "commands": ["/orbit-360"], "transition": {"technique": "/pull-back"}},
            {"id": "b", "mode": "r2v", "duration_s": 6, "commands": [], "transition": {}}]},
        "qc": {"a": {"verdict": "PASS"}, "b": {"verdict": "PASS"}}}}
    st = lessons.compute_stats([run])
    assert st["mode"] == {"r2v": [1, 1]}
    assert st["command"] == {"orbit-360": [1, 1]}
    assert st["transition"] == {"pull-back": [1, 1]}


async def test_context_renders_stats_line_only_from_two_samples(test_db):
    def run(shots, verdict):
        return {"brief": {}, "budget": {}, "spent": {}, "plan": {
            "shotlist": {"shots": [{"id": f"s{i}", "mode": "r2v", "duration_s": 6, "commands": ["/orbit-360"]}
                                   for i in range(shots)]},
            "qc": {f"s{i}": {"verdict": verdict} for i in range(shots)}}}
    r1 = await store.create_run({"text": "t", "target_s": 30}, {})
    await store.update_run(r1["id"], plan=run(1, "PASS")["plan"])
    assert "command orbit-360: PASS 1/1" not in await lessons.context_for("dp")
    assert "PASS 1/1" not in await lessons.context_for("dp")
    r2 = await store.create_run({"text": "t", "target_s": 30}, {})
    await store.update_run(r2["id"], plan=run(1, "FAIL")["plan"])
    ctx = await lessons.context_for("dp")
    assert "- command orbit-360: PASS 1/2" in ctx and "- mode r2v: PASS 1/2" in ctx
