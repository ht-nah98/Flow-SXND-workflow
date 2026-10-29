from agent.director import cut


def test_voiced_clip_keeps_its_speech_and_is_never_shrunk():
    clips = [{"duration": 10, "trim_in": 2.5, "trim_out": 6, "voice": True},
             {"duration": 10, "trim_in": 0, "trim_out": 10}]
    (a1, b1), (a2, b2) = cut.plan_trims(clips, target_s=8)
    assert (a1, b1) == (1.0, 7.0)
    assert b2 - a2 < 10       # the silent clip absorbs the cut


def test_silent_clips_unchanged():
    assert cut.plan_trims([{"duration": 10, "trim_in": 2.5, "trim_out": 6}], target_s=30) == [(2.5, 6.0)]


def test_film_is_one_high_quality_pass():
    from agent.director import effects
    clips = [effects.ClipEdit("a.mp4", 1.0, 6.5), effects.ClipEdit("b.mp4", 2.0, 7.0)]
    cmd = effects.film_cmd("ffmpeg", clips, "out.mp4", cut.FILM_SIZE["VERTICAL"], crf=cut.FILM_CRF)
    assert cmd[cmd.index("-crf") + 1] == "16" and cmd[cmd.index("-r") + 1] == "24"
    assert "scale=1080:1920:flags=lanczos" in cmd[cmd.index("-filter_complex") + 1]
    assert cmd[cmd.index("-t") + 1] == "5.500"
    assert cmd.count("-c:v") == 1


def test_voiced_film_still_fits_its_length():
    """Every clip speaks (a narrated trailer): the tails after the spoken stretch are cut, never the words."""
    clips = [{"duration": 10, "trim_in": 1, "trim_out": 10, "voice": True}] * 11
    trims = cut.plan_trims(clips, target_s=60)
    assert all(a == 1.0 and b >= cut.VOICE_WINDOW[1] for a, b in trims)
    assert sum(b - a for a, b in trims) <= 60 * 1.4 + 1   # was 99s before: voiced clips were never shortened
