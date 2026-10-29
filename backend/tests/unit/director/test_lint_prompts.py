import pytest

from agent.director.lint import BLOCK_LABELS, REQUIRED_BLOCKS, errors, lint_prompts
from agent.director.schemas import InShotTransition
from tests.unit.director.fixtures import fmv_prompts, fmv_shotlist, fmv_story


def rules(prompts=None, shots=None):
    return {i.rule for i in errors(lint_prompts(prompts or fmv_prompts(), shots or fmv_shotlist(), fmv_story()))}


def edit(i, **upd):
    p = fmv_prompts()
    p.prompts[i] = p.prompts[i].model_copy(update=upd)
    return p


def vp(i=0):
    return fmv_prompts().prompts[i].video_prompt


def test_reference_prompts_pass():
    assert rules() == set()


def test_every_shot_needs_a_prompt():
    p = fmv_prompts(); p.prompts.pop()
    assert "missing_prompt" in rules(p)


def test_block_labels_are_the_fmv_template():
    assert list(BLOCK_LABELS) == ["Ảnh tham chiếu", "Nhân vật & trang phục", "Bối cảnh", "Góc quay", "Hành động",
                                  "Chuyển động camera", "Ánh sáng & màu sắc", "Âm thanh", "Physics", "Props", "Thời lượng"]
    assert set(REQUIRED_BLOCKS) <= set(BLOCK_LABELS)


_EN = {"Ảnh tham chiếu:": "References:", "Nhân vật & trang phục:": "Characters & wardrobe:", "Bối cảnh:": "Setting:",
       "Góc quay:": "Shot:", "Hành động:": "Action:", "Chuyển động camera:": "Camera movement:",
       "Ánh sáng & màu sắc:": "Lighting & color:", "Âm thanh:": "Audio:",
       "Giữ nguyên đúng như ảnh tham chiếu đính kèm": "Keep them exactly as in the reference images",
       "Thời lượng: 10 giây, nhịp chậm rãi, không cắt cảnh.": "Duration: 10 seconds, slow pace, one continuous shot, no cuts."}


def english(text):
    for vi, en in _EN.items():
        text = text.replace(vi, en)
    return text


def test_english_template_passes():
    p = fmv_prompts()
    p.prompts = [x.model_copy(update={"video_prompt": english(x.video_prompt)}) for x in p.prompts]
    assert rules(p) == set()


def test_english_template_still_checks_the_blocks():
    assert "duration_block" in rules(edit(0, video_prompt=english(vp()).replace("no cuts", "fast")
                                          .replace("one continuous shot, ", "")))
    assert "constraints" in rules(edit(0, video_prompt=english(vp()).replace(
        "Keep them exactly as in the reference images", "Two young people")))


def test_required_blocks():
    assert "missing_block" in rules(edit(0, video_prompt=vp().replace("Góc quay:", "Khung hình:")))


@pytest.mark.parametrize("line", ["Thời lượng: 8 giây, không cắt cảnh.", "Thời lượng: 10 giây, nhịp chậm.",
                                  "Thời lượng: 110 giây, không cắt cảnh."])
def test_duration_block_must_say_10s_and_no_cuts(line):
    assert "duration_block" in rules(edit(0, video_prompt=vp().replace(
        "Thời lượng: 10 giây, nhịp chậm rãi, không cắt cảnh.", line)))


@pytest.mark.parametrize("form", ["10 giây", "10s", "10 Giây"])
def test_duration_forms_accepted(form):
    text = vp().replace("10 giây, nhịp chậm rãi", f"{form}, nhịp chậm rãi")
    assert rules(edit(0, video_prompt=text)) == set()


def test_people_must_be_locked_to_the_references():
    text = vp().replace("Giữ nguyên đúng như ảnh tham chiếu đính kèm", "Hai bạn trẻ")
    assert "constraints" in rules(edit(0, video_prompt=text))


def test_timestamps_within_clip_and_increasing():
    assert "timestamps" in rules(edit(0, video_prompt=vp().replace("6-10s", "6-12s")))
    assert "timestamps" in rules(edit(0, video_prompt=vp().replace("0-6s", "7-9s")))


def test_three_timed_beats_fail():
    text = vp().replace("6-10s: nhìn nhau bật cười.", "6-8s: nhìn nhau. 8-10s: bật cười.")
    assert "timestamps" in rules(edit(0, video_prompt=text))


def test_markdown_labels_and_bullets_parse():
    text = "\n".join(f"**{ln.split(':', 1)[0]}:** {ln.split(':', 1)[1]}" for ln in vp().splitlines())
    assert rules(edit(0, video_prompt=text)) == set()


def test_no_extra_people():
    assert "extra_person" in rules(edit(2, video_prompt=vp(2) + "\nMai bước vào."))


def test_keyframe_prompt_is_forbidden():
    assert "keyframe" in rules(edit(0, keyframe_prompt="x"))


def test_length_cap():
    assert "too_long" in rules(edit(0, video_prompt=vp() + "x" * 3600))


def test_two_movements_need_explicit_sequence():
    sl = fmv_shotlist()
    sl.shots[0] = sl.shots[0].model_copy(update={"commands": ["/medium-shot", "/handheld", "/pan-left", "/push-in"]})
    assert "movement_sequence" in rules(shots=sl)
    ok = vp().replace("cầm tay rung nhẹ tự nhiên.", "lia trái rồi đẩy vào gần.")
    assert "movement_sequence" not in rules(edit(0, video_prompt=ok), sl)


def _transition(camera):
    sl = fmv_shotlist()
    t = InShotTransition(start_s=3, technique="/pull-back", from_frame="tách cà phê", to_frame="cả căn phòng")
    sl.shots[0] = sl.shots[0].model_copy(update={"transition": t, "stable_open_s": 3,
                                                  "commands": ["/closeup", "/handheld"]})
    text = vp().replace("Chuyển động camera: Oneshot liền mạch, cầm tay rung nhẹ tự nhiên.", f"Chuyển động camera: {camera}")
    return rules(edit(0, video_prompt=text), sl)


def test_transition_holds_first_then_moves():
    assert _transition("Giữ khung ổn định vào tách cà phê 3 giây đầu, rồi lùi ra thấy cả căn phòng.") == set()
    assert _transition("Giữ khung cận tách cà phê → lùi ra toàn cảnh căn phòng.") == set()


def test_transition_without_hold_or_sequence_fails():
    assert "transition_prompt" in _transition("Lùi ra thấy cả căn phòng.")
    assert "transition_prompt" in _transition("Lùi ra thấy cả căn phòng rồi giữ ổn định.")


def _voiced(line="Viên nén xơ dừa, nở gấp năm lần chỉ với nước"):
    s = fmv_shotlist()
    s.shots[0] = s.shots[0].model_copy(update={"voice_line": line})
    return s


def test_voice_line_must_be_in_the_sound_block():
    assert "voice_line" in rules(shots=_voiced())
    p = edit(0, video_prompt=vp().replace("Âm thanh:", 'Âm thanh: Lồng tiếng nói: "Viên nén xơ dừa — nở gấp năm lần, chỉ với nước!".', 1))
    assert "voice_line" not in rules(p, _voiced())
