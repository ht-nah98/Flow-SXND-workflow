"""Ambient mode (directive B14, playbook 11): no story — one venue, one look, a 1–2 minute reel of 8s clips that loops
under the music. These checks replace the story, chain and cut-mode rules for a film with film_mode = "ambient"."""
import re

from agent.director.schemas import ShotList, ShotPrompts, Story
from agent.director.lint.common import LintIssue, NEWS_LOOK_MSG, _CAMERA_OBJECT, _LENS_GAZE, _news_look
from agent.director.lint.continuous import STYLE_TAIL, assemble

AMB_CLIP_S = 8                 # the sample cuts exactly every 8.0s: one 8s clip per shot, used whole
AMB_REEL_S = (60, 120)         # "Họ làm video có 1p-2p rồi lặp" (24/10); sample loop 124.75s
AMB_SHOT_SLACK = 2             # shots = reel_s / 8, give or take this many
AMB_KINDS = ("wide", "people", "detail", "stage")
AMB_MIN_KINDS = 3
AMB_MAX_WIDE = 0.5             # sample: about a third of the shots are wide
AMB_MAX_REFS = 3               # the venue picture + up to 2 detail pictures (stage, instrument)
AMB_MAX_DETAILS = 2
AMB_MAX_STATES = 2             # people only show states (eyes closed, a slow raised hand), never actions
AMB_PROMPT_WORDS = (50, 150)   # the clip's own words; the film's Visual style and Avoid are appended after
AMB_STYLE_MIN = 60
AMB_AVOID_MIN = 30

# 24/10 trial: an empty-venue picture (directive C3's empty backdrop) made the wide shot copy the empty stands; in
# this mode the crowd is the backdrop, so the venue picture shows the performance with its audience.
_CROWD = re.compile(r"\b(?:crowd|audience|people|spectators|worshippers|listeners|fans|full of|packed|filled)\b", re.I)
_EMPTY = re.compile(r"\bempty\b|\bno (?:people|audience|crowd|one)\b|\bunoccupied\b|\bdeserted\b|\bvacant\b"
                    r"|\bbefore the (?:show|concert|crowd)\b|\bready for (?:the|a) (?:crowd|audience)\b", re.I)
_FAST_CAMERA = re.compile(r"\bwhip|\bfast\b|\bquick(?:ly)?\b|\brapid|\bsnap|\bhandheld|\bshak(?:e|y|ing)|crash zoom"
                          r"|\bswish|\bjerk", re.I)
_PERFORMER = re.compile(r"\b(?:singer|vocalist|performer|worship leader|pastor|preacher|band|musician|pianist|"
                        r"guitarist|drummer|violinist|cellist|conductor|choir|saxophonist|trumpeter|rapper|dj)s?\b", re.I)
_FACE_SHOWN = re.compile(r"\b(?:face|faces|close-?up|facing (?:the )?(?:camera|lens|us|viewer)|front view|portrait)\b",
                         re.I)
_FACE_SAFE = re.compile(r"\bfrom behind\b|\bback(?:s)? (?:to|of)\b|\bsilhouett|\bbacklit\b|\bfar away\b|\bdistant\b"
                        r"|\btiny\b|\bseen from the back\b|\bover (?:his|her|their) shoulder", re.I)
_READABLE = re.compile(r"\blogos?\b|\bsigns? (?:that )?reads?\b|\breading [\"']|\bbanner (?:saying|that says|reads)"
                       r"|\bcaption|\bsubtitle|\blyrics on|\bwords? [\"'][^\"']+[\"'] (?:on|across)", re.I)


def _performer_face(text: str) -> str | None:
    """The words around a performer that show their face, unless the same clause keeps them from behind / far away.
    Only the clause around the performer counts: "…the singer's face, then a wide view toward the distant stage"
    still shows the singer's face."""
    for m in _PERFORMER.finditer(text):
        start = max(0, text.rfind(",", 0, m.start()) + 1, text.rfind(".", 0, m.start()) + 1, m.start() - 40)
        end = min((i for i in (text.find(c, m.end()) for c in ",.;\n") if i != -1), default=len(text))
        clause = text[start:end]
        if _FACE_SHOWN.search(clause) and not _FACE_SAFE.search(clause):
            return clause.strip()[:80]
    return None


def reel_shots(reel_s: int) -> int:
    return max(1, round(reel_s / AMB_CLIP_S))


def lint_story_ambient(story: Story) -> list[LintIssue]:
    """The venue sheet that stands in for a story: one place, a few detail props, nobody to keep a face for."""
    out: list[LintIssue] = []
    add = lambda rule, msg: out.append(LintIssue(rule, None, msg))  # noqa: E731
    places = [c for c in story.cast if c.entity_type == "location"]
    if len(places) != 1:
        add("amb_one_venue", f"an ambient film has exactly one venue (location), got {len(places)}: one place, one "
                             "night, one performance (directive B14)")
    for p in places:
        if _EMPTY.search(p.image_prompt) or not _CROWD.search(p.image_prompt):
            add("amb_venue_crowd", f"the venue picture {p.name!r} shows the live performance with its seats full of an "
                                   "anonymous audience (phone lights, raised hands): an empty venue makes the wide "
                                   "shots copy the empty stands (24/10 trial)")
    if any(c.entity_type == "character" for c in story.cast):
        add("amb_no_characters", "no characters: the people on screen are a different anonymous audience member in "
                                 "each shot, so there is no face to keep and no character sheet (playbook 11 §3)")
    if sum(c.entity_type == "visual_asset" for c in story.cast) > AMB_MAX_DETAILS:
        add("amb_details", f"at most {AMB_MAX_DETAILS} detail pictures (stage, instrument); the venue carries the rest")
    if len(story.sequences) != 1:
        add("amb_one_sequence", "one sequence: the reel has no acts")
    return out


def lint_shotlist_ambient(shots: ShotList, story: Story, reel_s: int) -> list[LintIssue]:
    out: list[LintIssue] = []
    add = lambda rule, sid, msg, sev="error": out.append(LintIssue(rule, sid, msg, sev))  # noqa: E731
    seq = sorted(shots.shots, key=lambda s: s.order)
    want = reel_shots(reel_s)
    if abs(len(seq) - want) > AMB_SHOT_SLACK:
        add("amb_reel_length", None, f"a ~{reel_s}s reel of {AMB_CLIP_S}s clips is about {want} shots "
                                     f"({want - AMB_SHOT_SLACK}–{want + AMB_SHOT_SLACK}), got {len(seq)}")
    if [s.order for s in seq] != list(range(1, len(seq) + 1)):
        add("order", None, f"shot order must be 1..N, got {[s.order for s in seq]}")
    names = {c.name for c in story.cast}
    places = {c.name for c in story.cast if c.entity_type == "location"}
    beats = {b.id for b in story.beats}
    for s in seq:
        for n in s.cast:
            if n not in names:
                add("cast_unknown", s.id, f"cast name {n!r} not in story cast {sorted(names)}")
        if not set(s.cast) & places:
            add("location_ref", s.id, "every clip carries the venue picture: it is what keeps one place and one look")
        if len(s.cast) > AMB_MAX_REFS:
            add("too_many_refs", s.id, f"{len(s.cast)} refs > {AMB_MAX_REFS}: the venue + at most 2 details")
        if s.beat_id not in beats:
            add("beat_unknown", s.id, f"beat {s.beat_id!r} not in story")
        if s.mode != "r2v":
            add("mode_r2v", s.id, "every shot is reference-to-video (r2v)")
        if s.duration_s != AMB_CLIP_S:
            add("clip_duration", s.id, f"an ambient clip is {AMB_CLIP_S}s, used whole (the sample cuts every 8.0s)")
        if s.kind not in AMB_KINDS:
            add("amb_kind", s.id, f"kind must be one of {list(AMB_KINDS)} (playbook 11 §3), got {s.kind!r}")
        if s.voice_line:
            add("amb_no_voice", s.id, "no spoken words: the sound is one music track over the whole reel")
        if s.bridge or s.transition or s.continues or s.handoff or s.keyframe:
            add("amb_plain_cut", s.id, "shots join by a plain cut: no bridge, in-clip transition, chain or keyframe")
        if any(a.kind == "action" for a in s.actions):
            add("amb_no_action", s.id, "people show states, not actions: write them as kind 'reaction' (eyes closed, "
                                       "a slow raised hand, a slow clap) — nothing happens, the music carries it")
        if sum(a.kind == "reaction" for a in s.actions) > AMB_MAX_STATES:
            add("amb_states", s.id, f"at most {AMB_MAX_STATES} states per clip; the crowd behind stays still background")
        camera = [a for a in s.actions if a.kind == "camera"]
        if len(camera) != 1:
            add("amb_one_camera", s.id, f"exactly one slow camera move for the whole clip (or 'static, shallow focus' "
                                        f"as that move), got {len(camera)}")
        for a in camera:
            if (m := _FAST_CAMERA.search(a.what)):
                add("amb_slow_camera", s.id, f"\"{m.group(0)}\": the camera only drifts, glides, pushes or cranes slowly")
    kinds = [s.kind for s in seq if s.kind in AMB_KINDS]
    if kinds and kinds[0] != "wide":
        add("amb_open_wide", seq[0].id, "the reel opens on a wide shot: the viewer first sees where they are")
    if len(kinds) > 1 and kinds[-1] == "wide":
        add("amb_loop_seam", seq[-1].id, "the last shot is not wide: the loop cuts from it back to the opening wide shot")
    for a, b in zip(seq, seq[1:]):
        if a.kind == b.kind and a.kind in AMB_KINDS:
            add("amb_rotate", b.id, f"two {a.kind} shots in a row: rotate wide → people → detail/stage (playbook 11 §3)")
    if len(seq) >= 4 and len(set(kinds)) < AMB_MIN_KINDS:
        add("amb_variety", None, f"use at least {AMB_MIN_KINDS} of the shot kinds {list(AMB_KINDS)}")
    if kinds and kinds.count("wide") / len(kinds) > AMB_MAX_WIDE:
        add("amb_variety", None, "more than half the shots are wide: give the audience and the details their share")
    return out


def lint_prompts_ambient(prompts: ShotPrompts, shots: ShotList, story: Story,
                         style_marker: str | None = None) -> list[LintIssue]:
    out: list[LintIssue] = []
    add = lambda rule, sid, msg: out.append(LintIssue(rule, sid, msg))  # noqa: E731
    prompts = assemble(prompts)
    if len(prompts.style_block.strip()) < AMB_STYLE_MIN:
        add("style_block", None, "write style_block once for the reel (palette, light sources, haze, depth of field): "
                                 "it is appended word for word to every prompt, so the look never changes")
    if len(prompts.avoid_block.strip()) < AMB_AVOID_MIN:
        add("avoid_block", None, "write avoid_block once (readable text, logos, performers' faces, fast camera moves, "
                                 "sudden actions…)")
    if style_marker and style_marker.lower() not in prompts.style_block.lower():
        add("style_pack", None, f"the film's style pack: write \"{style_marker}\" in style_block")
    places = [c.name for c in story.cast if c.entity_type == "location"]
    by_id = {p.shot_id: p for p in prompts.prompts}
    for s in shots.shots:
        p = by_id.get(s.id)
        if not p:
            add("missing_prompt", s.id, "no prompt for shot")
            continue
        body = p.video_prompt.split(STYLE_TAIL, 1)[0]
        n = len(body.split())
        if not AMB_PROMPT_WORDS[0] <= n <= AMB_PROMPT_WORDS[1]:
            add("amb_prompt_words", s.id, f"{n} words; an ambient clip prompt is {AMB_PROMPT_WORDS[0]}–"
                                          f"{AMB_PROMPT_WORDS[1]} words (playbook 11 §5), the look is appended")
        if not re.search(r"^\s*References:", body, re.M):
            add("amb_references", s.id, "start with a 'References:' line naming the attached pictures")
        for place in places:
            if place in s.cast and place not in body:
                add("asset_named", s.id, f"name the venue exactly as its picture is named: {place!r}")
        if (m := _CAMERA_OBJECT.search(body)):
            add("camera_object", s.id, f"\"{m.group(0)}\" makes the model draw a camera/crew in the shot")
        if (cue := _news_look(body)):
            add("news_look", s.id, f"\"{cue}\" {NEWS_LOOK_MSG}")
        if (m := _LENS_GAZE.search(body)):
            add("lens_gaze", s.id, f"\"{m.group(0)}\": nobody looks into the lens; give the eyes a place (the stage)")
        if (m := _READABLE.search(body)):
            add("amb_no_text", s.id, f"\"{m.group(0)}\": no readable text or logos; screens and signs are only light")
        if (near := _performer_face(body)):
            add("amb_performer_face", s.id, f"{near!r}: performers are only seen from behind, backlit or far away "
                                            "(a recognisable face is refused by Flow, playbook 05)")
    return out

