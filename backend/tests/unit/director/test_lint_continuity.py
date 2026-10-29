"""Directive B7/B11 (15/10, 16/10, 19/10): a cut to another story time needs a bridge; props keep count and colour."""
from agent.director.lint import errors, lint_prompts, lint_shotlist
from agent.director.schemas import Bridge
from tests.unit.director.fixtures import fmv_prompts, fmv_shotlist, fmv_story

PHONE = Bridge(element="the ringing wall phone", outgoing="young Daniel lifts the ringing wall phone",
               incoming="present Daniel lifts the same ringing wall phone")


def _shots(**s2):
    sl = fmv_shotlist()
    sl.shots[1] = sl.shots[1].model_copy(update=s2)
    return sl


def _rules(sl):
    return {i.rule for i in errors(lint_shotlist(sl, fmv_story(), 15))}


def test_a_cut_to_another_time_without_a_bridge_is_sent_back():
    assert "time_bridge" in _rules(_shots(period="past"))
    sl = _shots(period="past", bridge=PHONE)
    sl.shots[2] = sl.shots[2].model_copy(update={"period": "past"})
    assert "time_bridge" not in _rules(sl)


def test_the_bridge_is_written_in_both_prompts():
    sl = _shots(period="past", bridge=PHONE)
    sl.shots[2] = sl.shots[2].model_copy(update={"period": "past"})
    pr = fmv_prompts()
    bad = {(i.rule, i.shot_id) for i in lint_prompts(pr, sl, fmv_story())}
    assert ("bridge_prompt", "s1") in bad and ("bridge_prompt", "s2") in bad
    for i in (0, 1):
        pr.prompts[i] = pr.prompts[i].model_copy(
            update={"video_prompt": pr.prompts[i].video_prompt + "\nVật lý: the ringing wall phone rings on the wall."})
    assert not [i for i in lint_prompts(pr, sl, fmv_story()) if i.rule == "bridge_prompt"]


def test_cain_1_failures_are_caught_before_any_credit():
    """20/10 Cảnh 1 clip: a tripod camera in the kitchen, a third mug, a mug turning into a pot — from a 2,450-char
    prompt with a chain of actions and a 'two mugs' prop picture."""
    from agent.director.lint import lint_story
    from agent.director.schemas import Action
    pr = fmv_prompts()
    pr.prompts[0] = pr.prompts[0].model_copy(update={"video_prompt": pr.prompts[0].video_prompt.replace(
        "Góc quay: Trung cảnh", "Góc quay: camera placed at the chair side, locked-off camera on a tripod. Trung cảnh")
        + "\n" + "Vật lý: x " * 200})
    rules = {(i.rule, i.shot_id) for i in lint_prompts(pr, fmv_shotlist(), fmv_story())}
    assert ("camera_object", "s1") in rules and ("too_long", "s1") in rules
    chain = Action(what="Daniel sets the two mugs down, then picks up the pot and pours", start_s=0, end_s=5)
    assert "action_compound" in _rules(_shots(actions=[chain]))
    st = fmv_story()
    st.cast.append(st.cast[0].model_copy(update={"name": "Twin Coffee Mugs", "entity_type": "visual_asset",
                                                 "description": "Two identical cream mugs"}))
    assert "prop_single" in {i.rule for i in lint_story(st)}


def test_the_dp_is_told_what_the_shot_before_a_bridge_ends_on():
    from agent.director.pipeline import _dp_shots
    sl = _shots(period="past", bridge=PHONE)
    out = _dp_shots(sl)["shots"]
    assert out[0]["ends_on"] == {"element": PHONE.element, "how": PHONE.outgoing}
    assert "ends_on" not in out[1] and "ends_on" not in out[2]
    sub = sl.model_copy(update={"shots": [sl.shots[0]]})
    assert _dp_shots(sl, sub)["shots"][0]["ends_on"]["element"] == PHONE.element   # also in a targeted repair


def test_a_bridge_is_found_by_its_words_not_only_verbatim():
    from agent.director.lint import mentions
    assert mentions("swinging slowly back and forth on its hanging line", "the porch swing swings back and forth on its line, hanging")
    assert not mentions("Daniel's gold wedding ring", "Daniel lifts the phone")


def test_cain_1_clip_2_failures_are_caught():
    """20/10 clip 2: 'the steel pot' drew a saucepan (clip 1 said 'steel coffee pot', no reference); 'a matching empty
    mug' next to his mug, from a one-mug reference, collapsed into a single mug."""
    st = fmv_story()
    st.cast.append(st.cast[0].model_copy(update={"name": "Cream Coffee Mug", "entity_type": "visual_asset",
                                                 "description": "one cream mug"}))
    sl = fmv_shotlist()
    for i in (0, 1):
        sl.shots[i] = sl.shots[i].model_copy(update={"cast": sl.shots[i].cast + ["Cream Coffee Mug"],
                                                     "props": ["1 steel coffee pot: on the table"]})
    assert "recurring_prop" in _rules(sl)
    pr = fmv_prompts()
    pr.prompts[1] = pr.prompts[1].model_copy(update={"video_prompt": pr.prompts[1].video_prompt.replace(
        "Hành động:", "Bối cảnh: his mug and a matching empty mug on the table.\nHành động:", 1)})
    rules = {(i.rule, i.shot_id) for i in lint_prompts(pr, sl, st)}
    assert ("asset_named", "s1") in rules and ("twin_objects", "s2") in rules
    pr.prompts[0] = pr.prompts[0].model_copy(update={"video_prompt": pr.prompts[0].video_prompt
                                                     + "\nBối cảnh: the Cream Coffee Mug on the table."})
    assert ("asset_named", "s1") not in {(i.rule, i.shot_id) for i in lint_prompts(pr, sl, st)}
