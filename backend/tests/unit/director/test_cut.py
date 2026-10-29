from agent.director.cut import plan_trims


def test_uses_qc_trims_when_total_fits():
    clips = [{"duration": 6, "trim_in": 0.5, "trim_out": 5.7}, {"duration": 4, "trim_in": 0, "trim_out": 4}]
    assert plan_trims(clips, target_s=9) == [(0.5, 5.7), (0, 4)]


def test_clamps_bad_qc_values():
    assert plan_trims([{"duration": 4, "trim_in": -1, "trim_out": 9}], target_s=4) == [(0, 4)]


def test_length_follows_the_material_not_the_target():
    """Directive E1b: 3 good 6s windows make an 18s film even when ~15s was asked."""
    clips = [{"duration": 10, "trim_in": 1, "trim_out": 7}] * 3
    assert plan_trims(clips, target_s=15) == [(1, 7)] * 3


def test_a_silent_clip_never_holds_past_8s():
    """Directive E1: cut every 5–8s."""
    assert plan_trims([{"duration": 10, "trim_in": 0, "trim_out": 10}], target_s=60) == [(0, 8.0)]


def test_only_a_film_far_past_the_target_is_shortened():
    clips = [{"duration": 10, "trim_in": 0, "trim_out": 8}] * 3        # 24s
    trims = plan_trims(clips, target_s=10)                             # cap 1.4 × 10 = 14s
    total = sum(b - a for a, b in trims)
    assert 13.5 <= total <= 14.5
    assert all(a == 0 for a, _ in trims)


def test_never_shrinks_a_clip_below_min():
    clips = [{"duration": 4, "trim_in": 0, "trim_out": 2.2}, {"duration": 10, "trim_in": 0, "trim_out": 10}]
    trims = plan_trims(clips, target_s=6)
    assert trims[0][1] - trims[0][0] >= 2.0


def test_a_long_clip_keeps_its_action_not_its_first_seconds():
    """Agent Review F3 (21/10): the hug at 5–8.5s was cut because the window was the first 8s, then its tail went."""
    clip = {"duration": 10, "trim_in": 0, "trim_out": 9.5, "focus": (5.0, 8.5)}
    (a, b), = plan_trims([clip], target_s=60)
    assert a <= 5.0 and b >= 8.5 and b - a <= 8.0


def test_shortening_cuts_around_the_action_and_spares_the_payoff():
    clips = [{"duration": 10, "trim_in": 0.5, "trim_out": 9.5, "focus": (2.0, 8.5)}] * 12
    trims = plan_trims(clips, target_s=40)                             # cap 56s → ~4.7s each
    assert all(abs(b - 8.5) < 0.05 for _, b in trims)                  # every clip still ends on its payoff
    assert 55 <= sum(b - a for a, b in trims) <= 56.1
