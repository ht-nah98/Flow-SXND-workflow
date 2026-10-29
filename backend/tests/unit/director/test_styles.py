"""Style packs (gonghaosnail skill library, 19/10): one look — core rules, variables, deviation fixes — per film."""
from agent.director import effects, styles
from agent.director.lint import lint_prompts
from tests.unit.director.fixtures import fmv_prompts, fmv_shotlist, fmv_story


def test_every_pack_is_complete_and_grades_with_a_real_look():
    for p in styles.PACKS.values():
        assert p.core and p.variables and p.deviations and p.marker, p.id
        assert p.film_look in effects.LOOKS, p.id


def test_the_marker_must_be_in_every_lighting_line():
    pack = styles.get("warm-indie")
    bad = [i for i in lint_prompts(fmv_prompts(), fmv_shotlist(), fmv_story(), pack.marker) if i.rule == "style_pack"]
    assert len(bad) == 3                      # the fixture's lighting says "tông ấm", not the pack marker
    prompts = fmv_prompts()
    for p in prompts.prompts:
        p.video_prompt = p.video_prompt.replace("Ánh sáng & màu sắc: tông ấm", "Ánh sáng & màu sắc: warm golden light, tông ấm")
    assert not [i for i in lint_prompts(prompts, fmv_shotlist(), fmv_story(), pack.marker) if i.rule == "style_pack"]
    assert not [i for i in lint_prompts(fmv_prompts(), fmv_shotlist(), fmv_story()) if i.rule == "style_pack"]


async def test_the_pack_reaches_every_role_and_sets_the_grade(test_db):
    from agent.director import brain, pipeline, store
    from tests.unit.director.fake_plans import fake_responses
    resp = fake_responses()
    for p in resp["dp"][0]["prompts"]:
        p["video_prompt"] = p["video_prompt"].replace("Ánh sáng & màu sắc: tông ấm", "Ánh sáng & màu sắc: warm golden, tông ấm")
    fb = brain.FakeBrain(resp)
    brain.set_brain(fb)
    try:
        r = await store.create_run({"text": "love", "target_s": 15, "style_pack": "warm-indie"}, {})
        for stage in ("h_brief", "h_story", "h_shotlist", "h_prompts"):
            await getattr(pipeline, stage)(r)
    finally:
        brain.reset_brain()
    seen = {role: payload for role, payload in fb.calls}
    assert all(seen[r]["style_pack"]["id"] == "warm-indie" for r in ("writer", "director", "dp"))
    assert r["plan"]["shotlist"]["film_look"] == "mv-co-dien"


def test_the_roles_know_how_to_use_a_pack():
    from agent.director.brain import _system_prompt
    assert "Style pack" in _system_prompt("writer", "") and "marker" in _system_prompt("dp", "")
