"""Keyframe-mode lint (directive B13, playbook 10): stills, joins, prompts that land on the next still. Split from lint.py on 23/10 (code moved, not changed)."""
import re

from agent.director.schemas import ShotList, ShotPrompts, Story
from agent.director.lint.common import LintIssue, NEWS_LOOK_MSG, _CAMERA_OBJECT, _FLIP, _LENS_GAZE, _news_look, _norm_period, _photo_faces

# Keyframe mode (playbook 10, directive B13; sample: Artlist "New Kling 4.0", 15 shots in 47.5s, 0.9–4.9s each, every
# join inside a movement). A shot does ONE thing between two pinned stills.
KF_CLIP_S = (4, 6, 8)        # Omni first+last durations used here
KF_USE_S = (0.8, 5.0)        # seconds of a shot kept in the film
KF_KEY_WORDS = (12, 90)
_KF_JOIN_LOOK = {            # what the keyframe of a joined shot must show for its join to work
    "occlusion": (re.compile(r"\b(?:fill(?:s|ing)?|cover(?:s|ing)?|block(?:s|ing)?)\b[^.]{0,30}\b(?:frame|lens)\b"
                             r"|\bclose to the lens\b|\bagainst the lens\b|\bforeground\b", re.I),
                  "something right at the lens covering most of the frame (a coat, a shoulder, a pillar, a door)"),
    "screen": (re.compile(r"\b(?:screen|tv|television|monitor|display|shop window|window display)\b", re.I),
               "the screen (or shop window) filling the frame, showing the next place"),
    "whip": (re.compile(r"\bmotion blur|\bblurr?(?:ed|ing|s)?\b|\bwhip|\bstreak", re.I),
             "the frame smeared by motion blur in the direction of the move"),
}


def _lint_kf_shot(s, story, add):
    if s.duration_s not in KF_CLIP_S:
        add("clip_duration", s.id, f"a keyframe-mode clip is generated at 4, 6 or 8s, got {s.duration_s}s")
    words = len(s.keyframe.split())
    if not KF_KEY_WORDS[0] <= words <= KF_KEY_WORDS[1]:
        add("kf_keyframe", s.id, f"keyframe has {words} words; write the opening still in {KF_KEY_WORDS[0]}–"
            f"{KF_KEY_WORDS[1]} words: who (exact asset name), where, pose or action in progress, shot size, angle, light")
    elif not any(re.search(rf"\b{re.escape(n)}\b", s.keyframe) for n in s.cast):
        add("kf_cast", s.id, "the keyframe names none of the shot's cast: the still is generated from those pictures, "
            "write their exact names in it")
    people = [c.name for c in story.cast if c.entity_type == "character"]
    for n in people:
        if n not in s.cast and re.search(rf"\b{re.escape(n)}\b", s.keyframe):
            add("kf_cast_missing", s.id, f"the keyframe shows {n} but the shot's cast lacks {n}: the still is drawn from "
                "the cast pictures only, so the face would be invented — add them (drop a minor prop to stay ≤4)")
    if s.use_s is None or not KF_USE_S[0] <= s.use_s <= min(KF_USE_S[1], s.duration_s):
        add("kf_use", s.id, f"use_s = seconds kept in the film, {KF_USE_S[0]:g}–{KF_USE_S[1]:g}s (the sample's shots run "
            "0.9–4.9s)")
    acts = [a for a in s.actions if a.kind == "action"]
    cams = [a for a in s.actions if a.kind == "camera"]
    if len(acts) > 1 or len(cams) > 1:
        add("kf_one_thing", s.id, f"{len(acts)} actions and {len(cams)} camera moves: a keyframe shot does ONE thing "
            "(one action or one camera move, plus at most one of the other) — split it into more shots")
    for a in s.actions:
        if a.kind == "action" and _FLIP.search(a.what):
            add("flip_action", s.id, f"{a.what!r}: Flow cannot flip a flat object or slide it out of a pocket; pin "
                "the state you need in the keyframe")
        if a.kind != "camera" and _LENS_GAZE.search(a.what) and not re.search(r"\bnever\b|\bpast\b", a.what, re.I):
            add("lens_gaze", s.id, f"{a.what!r}: looking at the camera/photographer makes the actor stare into the lens")
    look = _KF_JOIN_LOOK.get(s.join_in)
    if look and s.keyframe and not look[0].search(s.keyframe):
        add("kf_join", s.id, f"join_in={s.join_in}: this shot's keyframe must show {look[1]} — it is also the last "
            "frame of the shot before, so the cut happens inside that movement")


def _lint_kf_chain(shots: ShotList, story: Story, add):
    seq = sorted(shots.shots, key=lambda x: x.order)
    if seq and seq[0].join_in != "cut":
        add("kf_first_join", seq[0].id, "the first shot has no shot before it: join_in = cut")
    places = {c.name for c in story.cast if c.entity_type == "location"}
    for prev, cur in zip(seq, seq[1:]):
        if cur.join_in == "cut":
            continue
        moved = (set(prev.cast) & places) != (set(cur.cast) & places) or _norm_period(prev.period) != _norm_period(cur.period)
        if moved and cur.join_in == "action":
            add("kf_place_change", cur.id, "a cut on action keeps the place and time; to change place or time join "
                "through a screen, an occlusion or a whip (the sample: TV on the wall → the news)")
    for i, s in enumerate(seq):
        joined_in = s.join_in != "cut" and i > 0
        joins_out = i + 1 < len(seq) and seq[i + 1].join_in != "cut"
        if joined_in and joins_out and s.use_s is not None and s.use_s < s.duration_s - 0.01:
            add("kf_both_ends", s.id, f"joined at both ends, the clip is used whole ({s.duration_s}s pinned to both "
                f"keyframes): set duration_s 4 and use_s 4, or make one side a cut")


KF_PROMPT_WORDS = (25, 200)


def _lint_prompts_kf(prompts: ShotPrompts, shots: ShotList, story: Story, style_marker: str | None) -> list[LintIssue]:
    """Keyframe mode (playbook 10 §4): the stills carry the picture; the video prompt only says what moves between them."""
    out: list[LintIssue] = []
    add = lambda rule, sid, msg: out.append(LintIssue(rule, sid, msg))  # noqa: E731
    if len(prompts.style_block.strip()) < 80:
        add("style_block", None, "write style_block once for the film (look, palette, grain, lens): it is added to every "
                                 "keyframe image so the stills match")
    if style_marker and style_marker.lower() not in prompts.style_block.lower():
        add("style_pack", None, f"the film's style pack: write \"{style_marker}\" in style_block")
    by_id = {p.shot_id: p for p in prompts.prompts}
    seq = sorted(shots.shots, key=lambda x: x.order)
    props = {c.name for c in story.cast if c.entity_type == "visual_asset"}
    for i, s in enumerate(seq):
        p = by_id.get(s.id)
        if not p:
            add("missing_prompt", s.id, "no prompt for shot")
            continue
        vp = p.video_prompt
        n = len(vp.split())
        if not KF_PROMPT_WORDS[0] <= n <= KF_PROMPT_WORDS[1]:
            add("kf_prompt_len", s.id, f"{n} words; a keyframe-mode prompt says only what moves between the two stills "
                f"({KF_PROMPT_WORDS[0]}–{KF_PROMPT_WORDS[1]} words): one action or one camera move, direction, speed")
        if "exact ending frame of the previous shot" in vp.lower():
            add("kf_template", s.id, "that opening is the continuous-mode template; in keyframe mode the first frame is "
                "the pinned still — start with the movement")
        joins_out = i + 1 < len(seq) and seq[i + 1].join_in != "cut"
        if joins_out and "final frame" not in vp.lower():
            add("kf_end", s.id, f"the next shot joins ({seq[i + 1].join_in}): end the prompt with \"…ending exactly on "
                "the final frame: <the next keyframe, short>\" so the movement lands on it")
        if (m := _CAMERA_OBJECT.search(vp)):
            add("camera_object", s.id, f"\"{m.group(0)}\" makes the model draw a camera/crew in the shot; describe only "
                                       "the view, never the equipment")
        if (shown := _photo_faces(vp, props)) or (shown := _photo_faces(s.keyframe, props)):
            add("photo_faces", s.id, f"\"{shown[:120]}\" shows a photograph's picture to the lens: Flow invents sharp "
                                     "faces in it and its safety filter deletes the clip")
        if (cue := _news_look(vp)) or (cue := _news_look(s.keyframe)):
            add("news_look", s.id, f"\"{cue}\" {NEWS_LOOK_MSG}")
    return out
