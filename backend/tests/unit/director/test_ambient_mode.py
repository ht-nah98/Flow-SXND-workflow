"""Directive B14 (24/10, playbook 11): ambient mode — no story, one venue, a reel of 8s clips that rotate wide → people
→ detail/stage, one slow camera move each, no performers' faces, no text; the script stops before any credit."""
import shutil
import subprocess

import pytest

from tests.unit.director.test_ingest_gates import world  # noqa: F401 — the fixture

from agent.director import brain, lint, pipeline, store
from agent.director.actions import rewrite_issues
from agent.director.schemas import ShotList, ShotPrompt, ShotPrompts, Story

VENUE = "Grand Arena"
KINDS = ["wide", "people", "stage", "people", "wide", "detail", "people", "stage"]   # 8 shots = a 60s reel
CAMERA = {"wide": "slow drift across the stands", "people": "slow glide along the row",
          "stage": "slow pull back from behind the band", "detail": "static, shallow focus"}


def story() -> Story:
    return Story.model_validate({
        "synopsis": "Một đêm worship trong sân vận động, tím hồng, đèn điện thoại.",
        "sequences": [{"id": "Q1", "title": "Reel", "act": 1, "purpose": "không khí"}],
        "beats": [{"id": "B1", "sequence_id": "Q1", "summary": "đêm nhạc", "emotion": "bình an"}],
        "cast": [{"name": VENUE, "entity_type": "location", "description": "a vast indoor arena",
                  "continuity_lock": "same tiers and LED screens", "image_prompt": "a vast indoor arena during the concert, stands full of an anonymous crowd with phone lights"}]})


def shot(i: int, kind: str, **kw) -> dict:
    d = {"id": f"S{i}", "beat_id": "B1", "order": i, "duration_s": 8, "idea": kind, "story_beat": "B1",
         "cast": [VENUE], "mode": "r2v", "mode_reason": "venue reference", "commands": [], "stable_open_s": 0,
         "kind": kind, "actions": [{"start_s": 0, "end_s": 8, "kind": "camera", "what": CAMERA[kind]}]}
    if kind == "people":
        d["actions"].append({"start_s": 0, "end_s": 8, "kind": "reaction", "what": "a woman keeps her eyes closed"})
    return d | kw


def shotlist(kinds=KINDS, over: dict | None = None) -> ShotList:
    shots = [shot(i, k) for i, k in enumerate(kinds, 1)]
    for i, kw in (over or {}).items():
        shots[i - 1] |= kw
    return ShotList.model_validate({"shots": shots})


BODY = (f"References: {VENUE}.\nLocation: the same {VENUE} as the reference, during a live worship night.\n"
        "Shot: a wide view from the upper stands over thousands of people toward the distant stage.\n"
        "People: ordinary unfamous faces in the nearest rows sway gently with open palms; the crowd behind stays a "
        "soft background of phone lights.\nCamera: one slow continuous drift to the right for the whole clip.\n"
        "Sound: no dialogue, no music.")


def prompts(body=BODY, n=len(KINDS)) -> ShotPrompts:
    return ShotPrompts(prompts=[ShotPrompt(shot_id=f"S{i}", video_prompt=body, end_frame="") for i in range(1, n + 1)],
                       style_block="deep purple and magenta stage wash, cool white spotlight beams, phone lights, light haze",
                       avoid_block="readable text, logos, performers' faces, fast camera moves")


def rules(issues) -> set[str]:
    return {i.rule for i in lint.errors(issues)}


def test_a_clean_ambient_script_passes_its_own_lints_only():
    st, sl, sp = story(), shotlist(), prompts()
    assert rules(lint.lint_story_ambient(st)) == set()
    assert rules(lint.lint_shotlist(sl, st, 60, "en", "ambient")) == set()
    assert rules(lint.lint_prompts(sp, sl, st, None, "ambient")) == set()
    assert "story_spine" in rules(lint.lint_story(st))          # the story rules would reject it: they are not used


@pytest.mark.parametrize("picture", [
    "Photorealistic wide-angle photograph of a vast empty indoor arena at night, show lights on",   # the 24/10 trial
    "a vast indoor arena at night, show lights on and ready for the crowd",
    "a vast indoor arena at night, stage lit",
])
def test_the_venue_picture_shows_the_audience_not_empty_seats(picture):
    """24/10 trial: with the empty-venue picture the wide shot copied the empty stands; the close shot drew a crowd."""
    st = story()
    st.cast[0] = st.cast[0].model_copy(update={"image_prompt": picture})
    assert "amb_venue_crowd" in rules(lint.lint_story_ambient(st))


def test_the_venue_sheet_has_one_place_and_nobody_to_keep():
    st = story()
    st.cast.append(st.cast[0].model_copy(update={"name": "Lobby"}))
    st.cast.append(st.cast[0].model_copy(update={"name": "Singer", "entity_type": "character"}))
    assert {"amb_one_venue", "amb_no_characters"} <= rules(lint.lint_story_ambient(st))


@pytest.mark.parametrize("kinds, rule", [
    (["people", "wide", "stage", "people", "wide", "detail", "people", "stage"], "amb_open_wide"),
    (["wide", "people", "people", "stage", "wide", "detail", "people", "stage"], "amb_rotate"),
    (["wide", "people", "stage", "people", "wide", "detail", "people", "wide"], "amb_loop_seam"),
    (["wide", "people", "wide", "people", "wide", "people", "wide", "people"], "amb_variety"),
    (["wide", "people", "stage"], "amb_reel_length"),
])
def test_the_reel_rotates_its_shot_kinds(kinds, rule):
    assert rule in rules(lint.lint_shotlist(shotlist(kinds), story(), 60, "en", "ambient"))


def test_a_clip_is_one_slow_camera_move_and_states_only():
    act = [{"start_s": 0, "end_s": 8, "kind": "camera", "what": "fast whip pan"},
           {"start_s": 2, "end_s": 4, "kind": "action", "what": "a man waves a flag"}]
    sl = shotlist(over={2: {"actions": act, "duration_s": 10, "voice_line": "Hello"}})
    assert {"amb_slow_camera", "amb_no_action", "clip_duration", "amb_no_voice"} <= \
        rules(lint.lint_shotlist(sl, story(), 60, "en", "ambient"))
    sl = shotlist(over={2: {"actions": []}})
    assert "amb_one_camera" in rules(lint.lint_shotlist(sl, story(), 60, "en", "ambient"))


def test_prompts_hide_performers_faces_and_text():
    face = BODY.replace("Shot: a wide view", "Shot: a close-up of the worship leader's face, then a wide view")
    assert "amb_performer_face" in rules(lint.lint_prompts(prompts(face), shotlist(), story(), None, "ambient"))
    back = BODY.replace("Shot: a wide view", "Shot: the worship leader seen from behind, backlit, then a wide view")
    assert "amb_performer_face" not in rules(lint.lint_prompts(prompts(back), shotlist(), story(), None, "ambient"))
    logo = BODY.replace("distant stage", "distant stage under a giant logo")
    assert "amb_no_text" in rules(lint.lint_prompts(prompts(logo), shotlist(), story(), None, "ambient"))
    assert "amb_prompt_words" in rules(lint.lint_prompts(prompts(f"References: {VENUE}."), shotlist(), story(),
                                                         None, "ambient"))


def test_a_rewritten_ambient_clip_is_linted_by_the_ambient_rules():
    sp = prompts()
    blocks = {"style_block": sp.style_block, "avoid_block": sp.avoid_block}
    assert rules(rewrite_issues(sp.prompts[0], "S1", shotlist(), story(), blocks, "ambient")) == set()
    bad = sp.prompts[0].model_copy(update={"video_prompt": "A close-up of the singer's face."})
    assert "amb_performer_face" in rules(rewrite_issues(bad, "S1", shotlist(), story(), blocks, "ambient"))


@pytest.fixture
def fake(test_db, monkeypatch):
    def install(responses):
        fb = brain.FakeBrain(responses)
        brain.set_brain(fb)
        return fb
    monkeypatch.setitem(pipeline.HANDLERS, "INGEST", pipeline._stop_here)
    yield install
    brain.reset_brain()


def ambient_responses() -> dict:
    return {"producer": [{"logline": "a worship night", "genre": "music", "tone": "calm", "target_s": 60,
                          "orientation": "HORIZONTAL", "voice": "voiceover"}],
            "writer": [story().model_dump()], "director": [shotlist().model_dump()],
            "dp": [prompts().model_dump()], "editor": [{"score": 90, "checklist": {}, "fixes": []}]}


async def test_an_ambient_run_writes_a_venue_sheet_not_a_story(fake):
    fb = fake(ambient_responses())
    r = await store.create_run({"text": "đêm worship", "target_s": 60, "film_mode": "ambient",
                                "venue": "worship-arena", "reel_s": 60}, {})
    r = await pipeline.run_until_blocked(r["id"])
    assert r["stage"] == "INGEST"
    b = r["plan"]["brief"]
    assert (b["film_mode"], b["venue"], b["reel_s"], b["target_s"], b["voice"]) == ("ambient", "worship-arena", 60, 60, "none")
    writer = next(p for role, p in fb.calls if role == "writer")
    assert "NO story" in writer["task"] and writer["venue"]["id"] == "worship-arena"
    assert all("AMBIENT MODE" in p["_context"] for role, p in fb.calls if role in ("writer", "director", "dp", "editor"))
    assert all("Visual style" in p["video_prompt"] and "Avoid" in p["video_prompt"]
               for p in r["plan"]["prompts"]["prompts"])          # the one look, appended to every clip


async def test_an_ambient_film_is_cut_as_a_looping_reel_never_by_the_cut_mode_edit(world, monkeypatch):  # noqa: F811
    """Step 4 (playbook 11 §7): reel.mp4 = every clip whole, plain cuts, muted; final.mp4 = the reel looped to loop_s
    or the music. The cut-mode trims and effects never touch an ambient film."""
    from agent.director import cut as cut_mod
    from tests.unit.director.test_ingest_gates import at_assets
    calls = {}

    async def local_clip(scene, ori, dest):
        return f"/clips/{scene['id']}.mp4"

    async def render_reel(paths, out, size):
        calls["reel"] = (paths, out, size)
        return out

    async def loop_reel(reel, out, loop_s, music):
        calls["loop"] = (reel, out, loop_s, music)
        return out
    monkeypatch.setattr(cut_mod, "local_clip", local_clip)
    monkeypatch.setattr(cut_mod, "render_reel", render_reel)
    monkeypatch.setattr(cut_mod, "loop_reel", loop_reel)
    monkeypatch.setitem(pipeline.HANDLERS, "PUBLISH", pipeline._stop_here)
    r = await at_assets()
    plan = r["plan"]
    plan["brief"] |= {"film_mode": "ambient", "loop_s": 1800}
    r = await store.update_run(r["id"], plan=plan, stage="CUT", status="RUNNING", gate=None)
    r = await pipeline.run_until_blocked(r["id"])
    assert r["stage"] == "PUBLISH" and "trims" not in r["plan"] and "edit" not in r["plan"]
    paths, out, size = calls["reel"]
    assert len(paths) == len(plan["shotlist"]["shots"]) and out.endswith("/reel.mp4") and size == "1920x1080"
    assert calls["loop"][1].endswith("/final.mp4") and calls["loop"][2] == 1800
    assert r["final_path"].endswith("/final.mp4") and r["plan"]["reel_path"].endswith("/reel.mp4")


def test_the_loop_copies_the_reel_video_and_fades_the_music():
    from agent.director import cut as cut_mod
    cmd = cut_mod.loop_cmd("ffmpeg", "reel.mp4", "final.mp4", 600.0, "song.mp3")
    assert cmd[cmd.index("-stream_loop") + 1] == "-1" and cmd[cmd.index("-c:v") + 1] == "copy"   # no second encode
    assert "afade=t=in:d=3.0,afade=t=out:st=596.000:d=4.0" in cmd and cmd[cmd.index("-t") + 1] == "600.000"
    assert "-an" in cut_mod.loop_cmd("ffmpeg", "reel.mp4", "final.mp4", 600.0, None)


def _tiny_clips(folder, n: int = 2) -> list[str]:
    """n real 2s clips with sound, like Flow's (which the reel must mute)."""
    srcs = []
    for i in range(n):
        src = folder / f"c{i}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=2",
                        "-f", "lavfi", "-i", "sine=d=2", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                        "-c:a", "aac", str(src)], check=True)
        srcs.append(str(src))
    return srcs


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")
async def test_a_real_reel_renders_whole_clips_and_loops_to_length(tmp_path):
    from agent.director import cut as cut_mod
    srcs = _tiny_clips(tmp_path)
    reel = await cut_mod.render_reel(srcs, str(tmp_path / "reel.mp4"), "320x180")
    assert abs(cut_mod.probe_duration(reel) - 4.0) < 0.2                     # both clips whole
    final = await cut_mod.loop_reel(reel, str(tmp_path / "final.mp4"), 10, None)
    assert abs(cut_mod.probe_duration(final) - 10.0) < 0.5
    assert not cut_mod._has_audio(final)                                     # muted: the user adds the music
