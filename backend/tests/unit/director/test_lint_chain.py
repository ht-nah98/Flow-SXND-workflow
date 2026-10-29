"""Directive B12 (21/10, playbook 09): continuous mode — each clip opens on the one before, the camera hands attention
on inside the clip, a time jump goes through light, and nobody appears from nowhere (the user's SIU Christmas film)."""
from agent.director.lint import errors, lint_shotlist
from agent.director.schemas import Action, Handoff, ShotList
from tests.unit.director.fixtures import BOY, GIRL, KITCHEN, _shot, fmv_story

FRAME = "Mai at the stove in medium shot, smiling toward the doorway on the left, steam rising, warm lamp light"


def _b(a, b, what, kind="action", who=""):
    return Action(start_s=a, end_s=b, what=what, kind=kind, who=who)


FIRST_BEATS = [_b(0, 2, "Mai at the stove, steam rising", "hold"), _b(2, 3, "Mai stirs the pot", who=GIRL),
               _b(3, 5, "camera pans left toward the kitchen doorway", "camera"),
               _b(5, 8, "Mai smiles toward the doorway", "reaction", GIRL)]
SECOND_BEATS = [_b(0, 1.5, "the inherited frame", "hold"), _b(1.5, 3, "Nam enters through the kitchen doorway", who=BOY),
                _b(3, 5, "Nam puts an arm around Mai", who=BOY), _b(5, 8, "Mai laughs", "reaction", GIRL)]


def _chain(**second) -> ShotList:
    first = _shot(id="c1", order=1, duration_s=8, cast=[GIRL, KITCHEN], final_frame=FRAME, actions=FIRST_BEATS,
                  handoff=Handoff(motive="voice", start_s=3, end_s=5, what="Nam calls from the hall; camera pans left",
                                  to="the kitchen doorway"))
    base = dict(id="c2", order=2, beat_id="b2", duration_s=8, continues=True, cast=[GIRL, BOY, KITCHEN],
                final_frame=FRAME, actions=SECOND_BEATS)
    base.update(second)
    return ShotList(shots=[first, _shot(**base)])


def _rules(sl, mode="continuous"):
    return {(i.rule, i.shot_id) for i in errors(lint_shotlist(sl, fmv_story(), 15, "en", mode))}


def test_a_well_built_chain_passes():
    assert _rules(_chain()) == set()


def test_the_shot_before_a_continuing_one_must_hand_off_and_promise_its_last_frame():
    sl = _chain()
    sl.shots[0] = sl.shots[0].model_copy(update={"handoff": None, "final_frame": ""})
    assert {("handoff_missing", "c1"), ("final_frame_missing", "c1")} <= _rules(sl)


def test_a_handoff_left_to_the_last_second_is_sent_back():
    sl = _chain()
    sl.shots[0] = sl.shots[0].model_copy(update={"handoff": sl.shots[0].handoff.model_copy(
        update={"start_s": 6, "end_s": 7.5})})
    assert ("handoff_timing", "c1") in _rules(sl)


def test_a_jump_to_the_past_inside_the_chain_goes_through_light():
    sl = _chain(period="childhood")
    assert ("time_jump_light", "c1") in _rules(sl)
    sl.shots[0] = sl.shots[0].model_copy(update={"handoff": sl.shots[0].handoff.model_copy(update={"motive": "light"})})
    assert ("time_jump_light", "c1") not in _rules(sl)


def test_a_new_person_is_seen_arriving():
    sl = _chain(actions=[SECOND_BEATS[0], _b(1.5, 3, "Nam stands beside her", who=BOY)] + SECOND_BEATS[2:])
    assert ("entrance", "c2") in _rules(sl)
    sl.shots[0] = sl.shots[0].model_copy(update={"handoff": sl.shots[0].handoff.model_copy(update={"to": "Nam in the hall"})})
    assert ("entrance", "c2") not in _rules(sl)


def test_the_first_shot_cannot_continue():
    sl = _chain()
    sl.shots[0] = sl.shots[0].model_copy(update={"continues": True})
    assert ("continues_first", "c1") in _rules(sl)


def test_a_continuing_clip_keeps_one_reference_for_the_last_frame():
    st = fmv_story()
    st.cast.append(st.cast[0].model_copy(update={"name": "Grandma"}))
    sl = _chain(cast=[GIRL, BOY, "Grandma", KITCHEN])
    assert ("too_many_refs", "c2") in {(i.rule, i.shot_id) for i in errors(lint_shotlist(sl, st, 15, "en", "continuous"))}


def test_cut_mode_rules_do_not_apply_to_a_continuous_film_and_still_apply_to_a_cut_one():
    sl = _chain()                      # 8s clips with 4 beats: wrong for cut mode, right for continuous
    assert _rules(sl) == set()
    cut = _rules(sl, "cut")
    assert ("clip_duration", "c1") in cut and ("actions_count", "c1") in cut


def test_roles_of_a_continuous_film_read_playbook_09():
    from agent.director import brain
    text = brain.continuous_playbook()
    assert "CONTINUOUS MODE" in text and "FINAL FRAME CONTRACT" in text


def test_the_omni_flash_limits_still_hold_inside_a_continuous_clip():
    """15–20/10 lessons kept (D3/D8): a stable open, ≤3 physical actions (≤2 per person), one gesture per action,
    the handoff 1–2.5s with ≥2s to settle, and nobody acts while the camera moves."""
    busy = [SECOND_BEATS[0], _b(1.5, 2.5, "Nam enters through the kitchen doorway", who=BOY),
            _b(2.5, 3.5, "Nam lifts the lid", who=BOY), _b(3.5, 5, "Nam tastes the soup", who=BOY),
            _b(5, 8, "Mai pours the tea", who=GIRL)]
    rules = _rules(_chain(actions=busy))
    assert ("actions_count", "c2") in rules
    rules = _rules(_chain(actions=[_b(0, 1.5, "Nam walks in, then hugs Mai and laughs", who=BOY)] + SECOND_BEATS[1:]))
    assert {("hold_open", "c2"), ("action_compound", "c2")} <= rules
    sl = _chain()
    sl.shots[0] = sl.shots[0].model_copy(update={
        "actions": [FIRST_BEATS[0], _b(2, 3, "Mai stirs the pot", who=GIRL), _b(3, 5, "Mai lifts the pot", who=GIRL),
                    FIRST_BEATS[3]],
        "handoff": sl.shots[0].handoff.model_copy(update={"start_s": 1, "end_s": 5})})
    assert {("handoff_timing", "c1"), ("action_during_handoff", "c1")} <= _rules(sl)


STYLE = ("Photorealistic 1920s period drama, 16:9, 35mm lens feel, warm amber practical light against cold blue-grey "
         "winter night, fine organic film grain, gentle highlight bloom.")
AVOID = "teleporting, people appearing from nowhere, costume changes, objects changing shape, camera shake, text, subtitles"


def _prompt(sid, continues, contract=True, sound="Sound\nSteam hissing, a spoon on the pot. No music."):
    head = ("Use the exact ending frame of the previous shot as the starting point.\nPreserve exact continuity: same "
            "Mai, same apron, same kitchen, same lamp light.\n" if continues else "")
    body = (head + "Create one continuous 8-second cinematic shot.\n"
            "SECOND 0 TO 2\nHold on Mai at the stove.\nSECOND 2 TO 3\nMai stirs the pot.\n"
            "SECOND 3 TO 5\nThe camera pans left toward the kitchen doorway.\nSECOND 5 TO 8\nMai smiles.\n")
    if contract:
        body += "FINAL FRAME CONTRACT\n" + FRAME + "\n"
    body += "Camera language\nhold → pan left → settle. One continuous movement. No hard cut.\n" + sound
    from agent.director.schemas import ShotPrompt
    return ShotPrompt(shot_id=sid, video_prompt=body, end_frame=FRAME)


def _prompts(**kw):
    from agent.director.schemas import ShotPrompts
    return ShotPrompts(prompts=[_prompt("c1", False), _prompt("c2", True, contract=False)],
                       style_block=STYLE, avoid_block=AVOID, **kw)


def _prules(sp, sl=None):
    from agent.director.lint import lint_prompts
    return {(i.rule, i.shot_id) for i in lint_prompts(sp, sl or _chain(), fmv_story(), None, "continuous")}


def test_continuous_prompts_follow_the_users_template():
    assert _prules(_prompts()) == set()
    sp = _prompts()
    sp.prompts[0] = _prompt("c1", False, contract=False, sound="Sound\nSteam hissing.")
    sp.prompts[1] = _prompt("c2", False, contract=False)
    rules = _prules(sp)
    assert {("final_frame_contract", "c1"), ("sound_block", "c1"), ("cont_open", "c2")} <= rules


def test_the_film_style_and_avoid_list_are_written_once_and_appended_to_every_prompt():
    from agent.director.lint import assemble
    assert {("style_block", None), ("avoid_block", None)} <= _prules(_prompts().model_copy(
        update={"style_block": "", "avoid_block": ""}))
    out = assemble(assemble(_prompts()))            # idempotent: a repair round never doubles the tail
    for p in out.prompts:
        assert p.video_prompt.count("Visual style") == 1 and p.video_prompt.endswith(AVOID + ".")
        assert STYLE in p.video_prompt


def test_the_cut_mode_length_cap_does_not_apply_but_the_d8_naming_rules_do():
    sp = _prompts()
    sp.prompts[0] = sp.prompts[0].model_copy(update={"video_prompt": sp.prompts[0].video_prompt.replace(
        "Mai stirs the pot.", "Mai stirs the pot. " + "The steam curls in the lamp light. " * 60)})
    assert ("too_long", "c1") not in _prules(sp)     # ~2,400 chars: fine in continuous mode
    sp.prompts[0] = sp.prompts[0].model_copy(update={"video_prompt": sp.prompts[0].video_prompt.replace(
        "Hold on Mai", "A camera on a tripod holds on Mai")})
    assert ("camera_object", "c1") in _prules(sp)


def test_a_photograph_never_shows_its_picture_to_the_lens():
    """22/10 Old Walt SH06: the print stood 'picture turned toward the lens', Flow drew soldiers' faces in it and its
    safety filter deleted the clip twice; SH02 (same refs, picture 'too soft to read') passed."""
    from agent.director.lint import _photo_faces
    props = {"Faded Squad Photograph", "Worn Leather Photo Album"}
    bad = "Old Walt stands the print upright against the base of the brass lamp, picture turned toward the lens."
    assert _photo_faces(bad, props) == bad
    fixed = ("Old Walt stands the print upright against the base of the brass lamp, angled away from the lens, so only "
             "its white deckled edge and its plain yellowed back show.")
    sh02 = "The picture is a small faded grey square, too soft to read; no faces are readable."
    assert _photo_faces(fixed, props) is None and _photo_faces(sh02, props) is None
    assert _photo_faces(bad, {"Brass Lamp"}) is None             # no photograph in the cast: nothing to check


def test_the_old_walt_review_lessons_are_enforced():
    """22/10 self-review: 6 clips, 14 rewrites. Each rule is a fault the video review found in a real clip."""
    sl = _chain()
    sl.shots[0] = sl.shots[0].model_copy(update={"final_frame": "The whole frame is a soft warm white-gold flare; no people, no objects readable."})
    assert ("abstract_final_frame", "c1") in _rules(sl)                     # SH02/SH04/SH05: Flow clears it, next clip cuts
    flip = [SECOND_BEATS[0], _b(1.5, 3, "Mai turns the photograph face-up on the table", who=GIRL)] + SECOND_BEATS[2:]
    assert ("flip_action", "c2") in _rules(_chain(actions=flip))             # SH02: lifted to the lens instead
    quick = FIRST_BEATS[:2] + [_b(3, 4, "camera pans left toward the kitchen doorway", "camera")] + FIRST_BEATS[3:]
    assert ("camera_beat_short", "c1") in _rules(_chain().model_copy(update={"shots": [
        _chain().shots[0].model_copy(update={"actions": quick}), _chain().shots[1]]}))
    gaze = SECOND_BEATS[:3] + [_b(5, 8, "Mai grins toward the unseen photographer", "reaction", GIRL)]
    assert ("lens_gaze", "c2") in _rules(_chain(actions=gaze))               # SH03/SH04: they stare into the lens
    assert _rules(_chain()) == set()                                         # the well-built chain still passes
