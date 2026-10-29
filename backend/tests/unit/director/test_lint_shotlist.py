from agent.director.lint import errors, lint_shotlist
from agent.director.schemas import Action, InShotTransition, ShotList
from tests.unit.director.fixtures import fmv_shotlist, fmv_story, overloaded_fmv_shots

TARGET = 15  # fixture source = 3 × 10s; allowed [1.5, 2.4] × target


def rules(shots, target=TARGET, story=None):
    return {i.rule for i in errors(lint_shotlist(shots, story or fmv_story(), target))}


def with_shot(i, **upd):
    sl = fmv_shotlist()
    sl.shots[i] = sl.shots[i].model_copy(update=upd)
    return sl


def test_fmv_reference_shots_are_clean():
    assert rules(fmv_shotlist()) == set()


def test_length_is_approximate_only_far_off_is_an_error():
    """Directive E1b: 3 clips ≈ 16.5s of film. Near the asked length is fine, a drift is a note, far off is sent back."""
    from agent.director.lint import errors
    by_target = lambda t: [i for i in lint_shotlist(fmv_shotlist(), fmv_story(), t) if i.rule == "total_duration"]  # noqa: E731
    assert by_target(16) == [] and by_target(13) == []
    assert by_target(25) and not errors(by_target(25))           # 0.66× → warning only
    assert errors(by_target(40)) and errors(by_target(8))        # 0.41× and 2.06× → too far


def test_cast_names_must_match_story_exactly():
    r = lint_shotlist(with_shot(0, cast=["mai", "Nam"]), fmv_story(), TARGET)
    bad = [i for i in r if i.rule == "cast_unknown"]
    assert bad and "mai" in bad[0].message


def test_more_than_seven_refs_is_an_error():
    assert "too_many_refs" in rules(with_shot(0, cast=["Mai"] * 5))
    assert "too_many_refs" not in rules(with_shot(0, cast=["Mai"] * 4))


def test_unknown_command():
    assert "unknown_command" in rules(with_shot(0, commands=["/medium-shot", "/flyover"]))


def test_one_command_per_group_and_one_primary_movement():
    assert "group_duplicate" in rules(with_shot(0, commands=["/medium-shot", "/closeup"]))
    assert "movement_count" in rules(with_shot(0, commands=["/dolly-in", "/pan-left", "/tilt-up"]))


def test_conflicting_pairs():
    assert "conflict" in rules(with_shot(0, commands=["/static", "/dolly-in"]))
    assert "conflict" in rules(with_shot(0, commands=["/handheld", "/gimbal"]))


def test_one_macro_and_no_atomic_movement_with_it():
    assert "macro" in rules(with_shot(0, commands=["/macrozoom", "/earth-zoom-in"]))
    assert "macro" in rules(with_shot(0, commands=["/macrozoom", "/pan-left"]))


def test_fmv_2_and_6_overloaded_with_actions_fail():
    sl = ShotList(shots=overloaded_fmv_shots())
    assert "actions_count" in rules(sl, target=10)


def test_every_clip_is_r2v_and_10s():
    assert "mode_r2v" in rules(with_shot(1, mode="i2v"))
    acts = [Action(start_s=0, end_s=6, what="a")]
    assert "clip_duration" in rules(with_shot(1, duration_s=6, actions=acts))


def test_action_outside_clip():
    acts = [Action(start_s=0, end_s=12, what="a")]
    assert "action_range" in rules(with_shot(0, actions=acts))


def test_transition_needs_two_seconds_stable_open_and_time_to_finish():
    t = InShotTransition(start_s=1, technique="/pull-back", from_frame="coffee cup", to_frame="whole room")
    assert "transition_timing" in rules(with_shot(0, transition=t, stable_open_s=1,
                                                  commands=["/closeup", "/handheld"]))
    late = t.model_copy(update={"start_s": 9})
    assert "transition_timing" in rules(with_shot(0, transition=late, stable_open_s=2,
                                                  commands=["/closeup", "/handheld"]))
    ok = t.model_copy(update={"start_s": 3})
    assert rules(with_shot(0, transition=ok, stable_open_s=3, commands=["/closeup", "/handheld"])) == set()


def test_transition_forbids_an_extra_primary_movement():
    t = InShotTransition(start_s=3, technique="/occlusion-reveal", from_frame="old man at railing",
                         to_frame="child at railing")
    assert "transition_plus_movement" in rules(with_shot(0, transition=t, stable_open_s=3,
                                                         commands=["/medium-shot", "/dolly-in"]))


def test_r2v_needs_a_ref():
    assert "r2v_no_refs" in rules(with_shot(0, cast=[]))


def test_order_must_be_contiguous():
    assert "order" in rules(with_shot(2, order=7))


def test_sequence_without_shots():
    story = fmv_story()
    story.sequences.append(story.sequences[0].model_copy(update={"id": "sq9"}))
    assert "empty_sequence" in rules(fmv_shotlist(), story=story)



def test_voice_line_too_long_for_one_clip():
    from agent.director.lint import errors, lint_shotlist
    from tests.unit.director.fixtures import fmv_shotlist, fmv_story
    s = fmv_shotlist()
    s.shots[0] = s.shots[0].model_copy(update={"voice_line": " ".join(["chữ"] * 19)})
    assert "voice_too_long" in {i.rule for i in errors(lint_shotlist(s, fmv_story(), 30))}


def test_english_voice_lines_are_shorter():
    from agent.director.lint import errors, lint_shotlist
    from tests.unit.director.fixtures import fmv_shotlist, fmv_story
    s = fmv_shotlist()
    s.shots[0] = s.shots[0].model_copy(update={"voice_line": " ".join(["word"] * 14)})
    assert "voice_too_long" not in {i.rule for i in errors(lint_shotlist(s, fmv_story(), 30, "vi"))}
    assert "voice_too_long" in {i.rule for i in errors(lint_shotlist(s, fmv_story(), 30))}   # English is the default


def test_a_story_needs_its_spine():
    from agent.director.lint import errors, lint_story
    from tests.unit.director.fixtures import fmv_story
    assert errors(lint_story(fmv_story())) == []
    bare = fmv_story().model_copy(update={"message": "", "viewer_value": " "})
    assert {i.message.split()[0] for i in errors(lint_story(bare))} == {"Story.message", "Story.viewer_value"}


def test_a_written_story_must_be_adapted_part_by_part():
    from agent.director.lint import errors, lint_story
    from agent.director.schemas import SourcePart
    idea = "Cảnh 1 — Ngày cuộc đời sụp đổ. " * 40          # a user-written story, not a one-liner
    story = fmv_story()
    beat = story.beats[0].id
    assert "source_map" in {i.rule for i in errors(lint_story(story, idea))}          # no map at all
    assert errors(lint_story(story, "Hai bạn trẻ làm bánh")) == []                      # short idea: no map needed
    parts = [SourcePart(part=f"Hồi {n}", beats=[beat]) for n in range(1, 5)]
    assert errors(lint_story(story.model_copy(update={"source_map": parts}), idea)) == []
    bad = parts[:3] + [SourcePart(part="Lời kết", kept="dropped")]                       # dropped without a reason
    assert "source_map" in {i.rule for i in errors(lint_story(story.model_copy(update={"source_map": bad}), idea))}
    lost = parts[:2] + [SourcePart(part=f"Hồi {n}", kept="dropped", note="không đủ thời lượng") for n in (3, 4)]
    msgs = [i.message for i in errors(lint_story(story.model_copy(update={"source_map": lost}), idea))]
    assert any("compress them instead" in m for m in msgs)                                # half the story dropped
    ghost = [SourcePart(part=f"Hồi {n}", beats=["B99"]) for n in range(1, 4)]
    assert "source_map" in {i.rule for i in errors(lint_story(story.model_copy(update={"source_map": ghost}), idea))}


def test_story_carries_the_directors_intent_and_retention_hooks():
    """SciCloud sample (19/10): the script says WHY (director_notes) and keeps the viewer every 25–30s (hooks)."""
    from agent.director.lint import lint_story
    from agent.director.schemas import Hook
    st = fmv_story()
    assert lint_story(st, target_s=15) == []
    rules_of = lambda s, t: {i.rule for i in lint_story(s, target_s=t)}  # noqa: E731
    assert "director_notes" in rules_of(st.model_copy(update={"director_notes": []}), 15)
    assert "hooks" in rules_of(st, 180)                                    # 3 min needs ≥5 hooks
    many = [Hook(at_s=25 * i, beat_id="b1", moment="m") for i in range(1, 6)]
    assert "hooks" not in rules_of(st.model_copy(update={"hooks": many}), 180)
    assert "hooks" in rules_of(st.model_copy(update={"hooks": [Hook(at_s=5, beat_id="nope", moment="m")]}), 15)


def test_every_clip_keeps_its_location_picture():
    """20/10 Cảnh 1: with two props the kitchen picture was dropped, so the room would be redrawn."""
    assert "location_ref" in rules(with_shot(0, cast=["Mai", "Nam"]))
    assert "location_ref" not in rules(with_shot(0, cast=["Mai", "Nam", "Rustic Kitchen"]))
