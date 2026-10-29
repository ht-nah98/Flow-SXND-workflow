"""Directive B13 (22/10, playbook 10): keyframe mode — short shots of one thing between pinned stills; every join sits
inside a movement (the user's second sample, Artlist "New Kling 4.0": 15 shots in 47.5s)."""
from agent.director.lint import errors, lint_prompts, lint_shotlist
from agent.director.schemas import Action, ShotList, ShotPrompt, ShotPrompts
from tests.unit.director.fixtures import BOY, GIRL, KITCHEN, _shot, fmv_story

K1 = f"Overhead close-up in the {KITCHEN}: {GIRL} kneads dough on the floured table, warm window light, flour on her cheek."
K2 = (f"{BOY}'s shoulder in a dark sweater fills the frame in the foreground, close to the lens, as he crosses in "
      f"front of {GIRL} in the {KITCHEN}.")
K3 = f"Medium shot in the {KITCHEN}: {BOY} hands {GIRL} a wooden spoon, both smiling, flour on her cheek, warm light."


def _kf(i, key, join="cut", use=3.0, dur=4, what="She presses the dough", kind="action"):
    return _shot(id=f"k{i}", order=i, beat_id="b1" if i == 1 else "b2", duration_s=dur, mode="i2v", keyframe=key,
                 join_in=join, use_s=use,
                 actions=[Action(start_s=0, end_s=dur, what=what, kind=kind)])


def _film(**third) -> ShotList:
    s3 = dict(i=3, key=K3, join="action", use=2.0, what="He hands her the spoon")
    s3.update(third)
    return ShotList(shots=[_kf(1, K1), _kf(2, K2, "occlusion", 4.0, what="camera tracks right with him", kind="camera"),
                           _kf(**s3)])


def _rules(sl):
    return {(i.rule, i.shot_id) for i in errors(lint_shotlist(sl, fmv_story(), 9, "en", "keyframe"))}


def test_a_well_built_keyframe_film_passes():
    assert _rules(_film()) == set()


def test_a_join_needs_a_keyframe_that_shows_it():
    sl = _film()
    sl.shots[1] = sl.shots[1].model_copy(update={"keyframe": K3})          # occlusion join, but nothing covers the lens
    assert ("kf_join", "k2") in _rules(sl)


def test_one_thing_per_shot_and_a_length_kept_in_the_film():
    busy = [Action(start_s=0, end_s=2, what="He lifts the bowl", kind="action"),
            Action(start_s=2, end_s=4, what="He pours the milk", kind="action")]
    sl = _film()
    sl.shots[2] = sl.shots[2].model_copy(update={"actions": busy, "use_s": None})
    assert {("kf_one_thing", "k3"), ("kf_use", "k3")} <= _rules(sl)


def test_the_first_shot_is_not_joined_and_a_place_change_does_not_cut_on_action():
    sl = _film()
    sl.shots[0] = sl.shots[0].model_copy(update={"join_in": "whip"})
    assert ("kf_first_join", "k1") in _rules(sl)
    sl = _film()
    sl.shots[2] = sl.shots[2].model_copy(update={"period": "childhood"})
    assert ("kf_place_change", "k3") in _rules(sl)


def test_a_shot_joined_at_both_ends_is_used_whole():
    sl = _film(join="screen", key=f"The TV screen fills the frame showing {GIRL} in the {KITCHEN}, {BOY} beside her.")
    sl.shots.append(_kf(4, K3, "action", 2.0))
    sl.shots[1] = sl.shots[1].model_copy(update={"use_s": 2.0})
    assert ("kf_both_ends", "k2") in _rules(sl)


def test_cut_mode_rules_do_not_apply_to_a_keyframe_film():
    rules = {r for r, _ in _rules(_film())}
    assert not rules & {"mode_r2v", "clip_duration", "actions_count", "commands"}


def _prompts(**over):
    vp = {"k1": ("She presses the heel of her hand into the dough, slow and steady, as he steps in from the left and "
                 "crosses close in front of the lens, ending exactly on the final frame: his dark shoulder fills the frame."),
          "k2": ("The camera tracks right as he crosses close in front of her, his shoulder sweeping across the lens, "
                 "ending exactly on the final frame: he hands her a wooden spoon, both smiling."),
          "k3": ("He offers the wooden spoon; she takes it from his hand and laughs softly, flour on her cheek. The camera "
                 "holds, then a gentle slow push-in toward their hands.")}
    vp.update(over)
    return ShotPrompts(prompts=[ShotPrompt(shot_id=k, video_prompt=v, end_frame="") for k, v in vp.items()],
                       style_block="Warm naturalistic film look, 35mm lens feel, soft window light, fine grain, gentle "
                                   "contrast, muted earthy palette.")


def test_keyframe_prompts_say_only_what_moves_and_land_on_the_next_still():
    assert {(i.rule, i.shot_id) for i in lint_prompts(_prompts(), _film(), fmv_story(), None, "keyframe")} == set()
    bad = _prompts(k2="The camera tracks right as he crosses close in front of her, his shoulder sweeping the lens.")
    assert ("kf_end", "k2") in {(i.rule, i.shot_id) for i in lint_prompts(bad, _film(), fmv_story(), None, "keyframe")}
    cont = _prompts(k1="Use the exact ending frame of the previous shot as the starting point. She presses the dough "
                       "slowly with the heel of her hand while the camera holds still.")
    assert ("kf_template", "k1") in {(i.rule, i.shot_id) for i in lint_prompts(cont, _film(), fmv_story(), None, "keyframe")}


def test_roles_of_a_keyframe_film_read_playbook_10():
    from agent.director import brain
    text = brain.keyframe_playbook()
    assert "KEYFRAME MODE" in text and "join_in" in text and "occlusion" in text


def test_a_person_in_a_keyframe_is_in_the_cast_and_the_length_is_held():
    """22/10 'Weatherman' test: shot 14 showed Leo on a TV without his picture; 14 shots made 51.5s for 30s asked."""
    sl = _film()
    sl.shots[0] = sl.shots[0].model_copy(update={"keyframe": K1 + f" {BOY} watches from the doorway.",
                                                 "cast": [GIRL, KITCHEN]})
    assert ("kf_cast_missing", "k1") in _rules(sl)
    long = ShotList(shots=_film().shots + [_kf(i, K1, use=4.0) for i in range(4, 8)])
    assert ("total_duration", None) in {(i.rule, i.shot_id) for i in errors(lint_shotlist(long, fmv_story(), 9, "en", "keyframe"))}


def test_a_clip_that_looks_like_a_real_news_broadcast_is_flagged():
    """22/10 Leo Marsh: Flow refused every clip with a news desk / ON AIR / a TV airing a person ('could misrepresent
    current events'); a plain studio with a cartoon sun passed."""
    from agent.director.lint import _news_look
    assert _news_look("Leo sits at the anchor desk, the ON AIR lamp turns red")
    assert _news_look("a banner reading WEATHER — LIVE IN 30 SECONDS")
    assert _news_look("A plain white studio; the wall screen shows a cartoon sun over green hills.") is None
    sl = _film()
    sl.shots[2] = sl.shots[2].model_copy(update={"keyframe": K3 + " A red ON AIR sign glows behind them."})
    assert ("news_look", "k3") in {(i.rule, i.shot_id) for i in lint_prompts(_prompts(), sl, fmv_story(), None, "keyframe")}


def test_a_rewritten_keyframe_clip_is_linted_as_a_keyframe_clip():
    """23/10 Blue Morning: "Claude viết lại prompt" on a keyframe film failed 3 times on the cut-mode blocks."""
    from agent.director.pipeline import rewrite_issues
    sp = _prompts()
    p, blocks = sp.prompts[1], {"style_block": sp.style_block, "avoid_block": sp.avoid_block}
    assert rewrite_issues(p, "k2", _film(), fmv_story(), blocks, "keyframe") == []
    bad = p.model_copy(update={"video_prompt": "The camera tracks right as he crosses close in front of her."})
    assert ("kf_end", "k2") in {(i.rule, i.shot_id) for i in rewrite_issues(bad, "k2", _film(), fmv_story(), blocks, "keyframe")}


def test_a_keyframe_still_may_hold_a_family_of_four_and_their_room():
    """23/10 "Home for Christmas": the family photo needs 4 people + the living room; at 4 refs the director failed 3
    times (too_many_refs vs location_ref). The pictures only draw the still in keyframe mode."""
    from agent.director.lint import KF_MAX_REFS, MAX_REFS
    sl = _film()
    sl.shots[2] = sl.shots[2].model_copy(update={"cast": [GIRL, BOY, KITCHEN, "Ann", "Bob"][:5]})
    rules = {(i.rule, i.shot_id) for i in errors(lint_shotlist(sl, fmv_story(), 9, "en", "keyframe"))}
    assert ("too_many_refs", "k3") not in rules and KF_MAX_REFS == 6 > MAX_REFS
