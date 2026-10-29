"""Continuous-mode lint (directive B12, playbook 09): beats, the chain, assembled prompts. Split from lint.py on 23/10 (code moved, not changed)."""
import re

from agent.director.schemas import ShotList, ShotPrompts, Story
from agent.director.lint.common import LintIssue, MAX_ACTION_WORDS, NEWS_LOOK_MSG, _CAMERA_OBJECT, _COMPOUND, _FLIP, _LENS_GAZE, _news_look, _norm_period, _photo_faces, _words, mentions

CONT_BEATS = (3, 7)        # the timed beats of one camera journey (the user's prompts have 5–7)
MAX_BEAT_WORDS = 30
# Omni Flash limits, packaged from the cut-mode lessons (D3, D8, 15–20/10) and the user's own prompts (21/10). A
# continuous clip is one camera journey of several beats, but the people in it still do few physical things.
CONT_MAX_ACTIONS = 3       # physical "action" beats per clip (holds, reactions and camera beats are not counted)
CONT_MAX_PER_PERSON = 2    # D3: ≤2 actions for one subject in one clip
HOLD_CONT_S = 1.0          # a continuing clip holds the inherited frame ≥1s ("Hold this only very briefly")
HOLD_FIRST_S = 2.0         # D3: the clip that starts a chain holds a stable frame 2s before any special move
HANDOFF_MIN_S = 1.0        # the handoff move takes 1–2.5s (the user's: 1.5–2s; a light bloom fills < 1s of it)
HANDOFF_MAX_S = 2.5
HANDOFF_SETTLE_S = 2.0     # the new person/place settles ≥2s into the final frame (the user's: 2.5–3s)
MAX_PROMPT_CHARS_CONT = 7500   # the user's prompts: 550–1,050 words (~3,500–6,500 chars) + the film's style block
MIN_FINAL_FRAME = 40       # characters: a contract the next clip can open from
# A new person in a continuing clip arrives where the camera can see it (the user had to re-prompt the father who
# "appeared from nowhere").
_ENTRY = re.compile(r"\b(enter|enters|entering|walks? in|steps? (?:in|into|through|out)|comes? (?:in|into|down|through|out)"
                    r"|runs? (?:in|into|down|up)|arriv|leans? out|peeks? out|appears? (?:at|in|through) the (?:door|arch|hall)"
                    r"|through the (?:door|doorway|archway|gate))", re.I)


# 22/10 self-review of "Old Walt" (6 clips, 14 rewrites, review scores 5.2–7.9). Each rule below is a fault the video
# review found in a real clip; see playbook 09 §8.
# (1) A clip that ends on an abstract texture (flare, macro raindrops, canvas filling the frame) does not hold it — Flow
#     clears it (SH02, SH04, SH05) — and the next clip must pull back from it to a new wide place, where Flow hard-cuts
#     (SH03 at 2s, SH05 at 1.25s). The transition goes in AND out inside one clip; the clip ends on a readable image.
_ABSTRACT_END = re.compile(r"\b(?:fills?|filling|filled) (?:the )?(?:whole )?frame|\bwhole frame\b|\bflare\b|\bhaze\b"
                           r"|\bmacro\b|out of focus|\bno people(?:,| or) no objects|nothing (?:is )?readable", re.I)
MIN_CAMERA_BEAT_S = 1.5     # SH03 "flare softens into sunbeams" in 1s and a reframe in 0.5s read as cuts


def _lint_beats(s, add):
    """Continuous mode: the clip's actions are the 3–7 timed beats of one camera journey, in order, inside the clip —
    with the Omni Flash limits kept: a stable opening, few physical actions, one handoff with time to settle."""
    if not CONT_BEATS[0] <= len(s.actions) <= CONT_BEATS[1]:
        add("beats_count", s.id, f"{len(s.actions)} beats; a continuous {s.duration_s}s clip is told in "
            f"{CONT_BEATS[0]}–{CONT_BEATS[1]} timed beats (SECOND a TO b)")
    beats = sorted(s.actions, key=lambda a: a.start_s)
    for a in beats:
        if a.end_s > s.duration_s or a.start_s >= a.end_s:
            add("action_range", s.id, f"beat {a.what!r} {a.start_s}-{a.end_s}s outside 0-{s.duration_s}s")
        if a.kind == "action" and (len(a.what.split()) > MAX_ACTION_WORDS or _COMPOUND.search(a.what)):
            add("action_compound", s.id, f"action {a.what!r} is a chain; one action = ONE gesture of ≤{MAX_ACTION_WORDS} "
                "words (a pour, a reach, a turn) — the rest goes in another beat or clip")
        elif len(a.what.split()) > MAX_BEAT_WORDS:
            add("beat_too_long", s.id, f"beat {a.what[:40]!r}… has {len(a.what.split())} words; one beat ≤ "
                f"{MAX_BEAT_WORDS} words — the prompt gives the detail")
    acts = [a for a in beats if a.kind == "action"]
    if len(acts) > CONT_MAX_ACTIONS:
        add("actions_count", s.id, f"{len(acts)} physical actions; a continuous clip carries at most {CONT_MAX_ACTIONS} "
            "(holds, reactions and camera beats are free) — Omni Flash breaks objects when more happens")
    per: dict[str, int] = {}
    for a in acts:
        if a.who:
            per[a.who] = per.get(a.who, 0) + 1
    for who, n in per.items():
        if n > CONT_MAX_PER_PERSON:
            add("actions_count", s.id, f"{who} does {n} actions; one person does at most {CONT_MAX_PER_PERSON} per clip (D3)")
    need = HOLD_CONT_S if s.continues else HOLD_FIRST_S
    first = beats[0] if beats else None
    if not first or first.kind != "hold" or first.start_s > 0 or first.end_s - first.start_s < need:
        add("hold_open", s.id, f"open on a 'hold' beat from 0s lasting ≥{need:g}s "
            + ("(the inherited frame, held briefly)" if s.continues else "(D3: a stable frame before anything moves)"))
    for a in beats:
        if a.kind == "action" and _FLIP.search(a.what):
            add("flip_action", s.id, f"{a.what!r}: Flow cannot flip a flat object or slide it out of a pocket (Old Walt "
                "SH01, SH02, SH06 — it lifts it to the lens, swaps it or makes it appear); start the object already in "
                "the state the shot needs and use one plain contact (touch, lift, set down)")
        if a.kind == "camera" and a.end_s - a.start_s < MIN_CAMERA_BEAT_S:
            add("camera_beat_short", s.id, f"camera beat {a.what[:50]!r} lasts {a.end_s - a.start_s:g}s; a camera move "
                f"needs ≥{MIN_CAMERA_BEAT_S:g}s or Flow cuts instead of moving (Old Walt SH03)")
        if a.kind != "camera" and _LENS_GAZE.search(a.what) and not re.search(r"\bnever\b|\bpast\b", a.what, re.I):
            add("lens_gaze", s.id, f"{a.what!r}: 'photographer' / looking at the camera makes the actors stare into the "
                "lens (Old Walt SH03, SH04); give the look a place in the room (\"toward the doorway at frame left\")")
    if s.final_frame and _ABSTRACT_END.search(s.final_frame):
        add("abstract_final_frame", s.id, "the final frame is an abstract texture (flare, haze, macro, something filling "
            "the frame): Flow does not hold it and the next clip hard-cuts pulling back from it (Old Walt SH02→03, "
            "SH04→05). Let the light/occlusion go in AND out inside this clip and end on a readable image: who is "
            "where, doing what, in which light")
    h = s.handoff
    if not h:
        return
    if (h.start_s < need or h.start_s >= h.end_s or not HANDOFF_MIN_S <= h.end_s - h.start_s <= HANDOFF_MAX_S
            or h.end_s > s.duration_s - HANDOFF_SETTLE_S):
        add("handoff_timing", s.id, f"handoff {h.start_s}–{h.end_s}s: start after the {need:g}s hold, last "
            f"{HANDOFF_MIN_S:g}–{HANDOFF_MAX_S:g}s, and finish by {s.duration_s - HANDOFF_SETTLE_S:g}s so the new "
            "person/place settles into the final frame (never only at the last second)")
    for a in acts:
        if min(a.end_s, h.end_s) - max(a.start_s, h.start_s) > 0.3:
            add("action_during_handoff", s.id, f"action {a.what!r} runs while the camera hands off ({h.start_s}–"
                f"{h.end_s}s): during the move people only react — one moving thing at a time (D3)")


def _first_name(name: str) -> str:
    return re.split(r"[\s(]", name.strip(), maxsplit=1)[0].lower()


def _lint_chain(shots: ShotList, story: Story, add):
    """Continuous mode (directive B12): each clip opens on the one before, the camera hands attention on inside the
    clip, a jump in story time goes through light or a foreground wipe, and a new person is seen arriving."""
    people = {c.name for c in story.cast if c.entity_type == "character"}
    seq = sorted(shots.shots, key=lambda s: s.order)
    if seq and seq[0].continues:
        add("continues_first", seq[0].id, "the first shot has no shot before it: continues=false")
    for prev, cur in zip(seq, seq[1:]):
        if not cur.continues:
            # A new chain = a cut between sequences; a cut to another time still needs its bridge (B7/B11).
            if _norm_period(prev.period) != _norm_period(cur.period) and not cur.bridge:
                add("time_bridge", cur.id, f"cut from '{prev.period}' to '{cur.period}' with no bridge: continue the "
                    "chain through a light bloom instead, or give the cut a bridge seen in both shots")
            continue
        if not prev.handoff:
            add("handoff_missing", prev.id, f"{cur.id} continues from this shot: say how the camera hands attention on "
                "(voice, eyeline, follow, occlusion, light), when (≈3–5s) and to whom")
        if len(prev.final_frame.strip()) < MIN_FINAL_FRAME:
            add("final_frame_missing", prev.id, f"{cur.id} opens on this shot's last frame: write final_frame — who "
                "is where, looking where, holding what, framing and light")
        if _norm_period(prev.period) != _norm_period(cur.period) and (not prev.handoff or
                                                                      prev.handoff.motive not in ("light", "occlusion")):
            add("time_jump_light", prev.id, f"'{prev.period}' → '{cur.period}' inside one camera journey: hand off "
                "through a light bloom (a reflection or flame grows to warm white) or a foreground wipe — never a cut, "
                "sepia, ghosting or one person morphing into another")
        landed = (prev.handoff.to if prev.handoff else "").lower()
        for n in sorted((set(cur.cast) & people) - set(prev.cast)):
            first = _first_name(n)
            seen = first in landed or any(first in a.what.lower() and _ENTRY.search(a.what) for a in cur.actions)
            if not seen:
                add("entrance", cur.id, f"{n} is not in {prev.id}: show them arriving (through a doorway, down the "
                    "stairs, into frame) in a beat, or let the camera land on them in the previous handoff — never "
                    "appear from nowhere")


# Continuous prompts (playbook 09 §4): the user's 7-part template.
_SECTIONS = ("FINAL FRAME CONTRACT", "Camera language", "Performance direction", "Sound", "Visual style", "Avoid")
_SECTION_RE = re.compile(r"^(" + "|".join(re.escape(x) for x in _SECTIONS) + r")\s*:?\s*$", re.I | re.M)
_SECOND = re.compile(r"^SECONDS?\s+(\d+(?:\.\d+)?)\s+TO\s+(\d+(?:\.\d+)?)\s*$", re.I | re.M)
STYLE_TAIL = "\n\nVisual style\n"


def _sections(vp: str) -> dict[str, str]:
    """The text under each header line of a continuous prompt (the part before the first header is "body")."""
    marks = list(_SECTION_RE.finditer(vp))
    out = {"body": vp[:marks[0].start()] if marks else vp}
    for m, nxt in zip(marks, marks[1:] + [None]):
        key = next(x for x in _SECTIONS if x.lower() == m.group(1).lower())
        out[key] = vp[m.end():nxt.start() if nxt else len(vp)].strip()
    return out


def assemble(sp: ShotPrompts) -> ShotPrompts:
    """Continuous mode: append the film's one Visual style block and Avoid list to every prompt (idempotent)."""
    def one(p):
        body = p.video_prompt.split(STYLE_TAIL, 1)[0].rstrip()
        avoid = ", ".join(x.strip().rstrip(".") for x in (sp.avoid_block, p.avoid) if x.strip())
        tail = (STYLE_TAIL + sp.style_block.strip() if sp.style_block.strip() else "") + \
            ("\n\nAvoid\n" + avoid + "." if avoid else "")
        return p.model_copy(update={"video_prompt": body + tail})
    return sp.model_copy(update={"prompts": [one(p) for p in sp.prompts]})


def _lint_prompts_cont(prompts: ShotPrompts, shots: ShotList, story: Story, style_marker: str | None) -> list[LintIssue]:
    out: list[LintIssue] = []
    add = lambda rule, sid, msg: out.append(LintIssue(rule, sid, msg))  # noqa: E731
    prompts = assemble(prompts)
    if len(prompts.style_block.strip()) < 80:
        add("style_block", None, "write style_block once for the film (photoreal/period look, palette, grain, bloom, "
                                 "lens): it is appended word for word to every prompt")
    if len(prompts.avoid_block.strip()) < 40:
        add("avoid_block", None, "write avoid_block once for the film (teleporting, appearing from nowhere, costume or "
                                 "object changes, modern items, camera shake, text, subtitles…)")
    if style_marker and style_marker.lower() not in prompts.style_block.lower():
        add("style_pack", None, f"the film's style pack: write \"{style_marker}\" in style_block")
    by_id = {p.shot_id: p for p in prompts.prompts}
    seq = sorted(shots.shots, key=lambda x: x.order)
    nxt = {a.id: b for a, b in zip(seq, seq[1:])}
    by_order = {s.order: by_id[s.id] for s in seq if s.id in by_id}
    people = {c.name for c in story.cast if c.entity_type == "character"}
    props = {c.name for c in story.cast if c.entity_type == "visual_asset"}
    for s in seq:
        p = by_id.get(s.id)
        if not p:
            add("missing_prompt", s.id, "no prompt for shot")
            continue
        vp = p.video_prompt
        sec = _sections(vp)
        low = vp.lower()
        if s.continues and not ("use the exact ending frame of the previous shot" in low and "preserve exact continuity" in low):
            add("cont_open", s.id, "a continuing clip opens with \"Use the exact ending frame of the previous shot as the "
                                   "starting point.\" then \"Preserve exact continuity: same …\" (people, clothes, place, light)")
        stamps = [(float(a), float(b)) for a, b in _SECOND.findall(sec["body"])]
        ok = (CONT_BEATS[0] <= len(stamps) <= CONT_BEATS[1] and stamps[0][0] == 0
              and abs(stamps[-1][1] - s.duration_s) < 0.01 and all(a < b for a, b in stamps)
              and all(abs(stamps[i][1] - stamps[i + 1][0]) < 0.01 for i in range(len(stamps) - 1)))
        if not ok:
            add("seconds", s.id, f"tell the clip in {CONT_BEATS[0]}–{CONT_BEATS[1]} lines \"SECOND a TO b\" from 0 to "
                f"{s.duration_s:g}, each starting where the last ended: {stamps}")
        elif s.handoff and not any(abs(a - s.handoff.start_s) <= 0.6 for a, _ in stamps):
            add("handoff_prompt", s.id, f"the handoff starts at {s.handoff.start_s:g}s: begin a SECOND block there and "
                                        "write the camera move in it")
        if s.id in nxt and nxt[s.id].continues and not sec.get("FINAL FRAME CONTRACT"):
            add("final_frame_contract", s.id, "the next clip opens on this one: end with a FINAL FRAME CONTRACT section "
                                              "(who is where, looking where, holding what, framing, light)")
        if not sec.get("Camera language"):
            add("camera_language", s.id, "add a \"Camera language\" section: one arrow line (A → B → C) and \"One "
                                         "continuous movement. No hard cut.\"")
        sound = sec.get("Sound", "")
        if "no music" not in sound.lower():
            add("sound_block", s.id, "add a \"Sound\" section with real sounds and \"No music.\" (the user adds the "
                                     "music outside — directive E6)")
        if s.voice_line and _words(s.voice_line) not in _words(sound):
            add("voice_line", s.id, f"Sound must contain the shot's spoken line verbatim in quotes: \"{s.voice_line}\"")
        if p.keyframe_prompt:
            add("keyframe", s.id, "keyframe_prompt must be empty: every shot is r2v")
        if len(vp) > MAX_PROMPT_CHARS_CONT:
            add("too_long", s.id, f"video_prompt {len(vp)} chars > {MAX_PROMPT_CHARS_CONT}: keep to the beats, the "
                                  "contract and the sections; name each object once")
        for name in people - set(s.cast):
            if re.search(rf"\b{re.escape(name)}\b", vp) and not (s.continues and name in (
                    seq[seq.index(s) - 1].cast if seq.index(s) else [])):
                add("extra_person", s.id, f"{name} is mentioned but not in this shot's cast")
        body = sec["body"] + "\n" + sec.get("FINAL FRAME CONTRACT", "")
        for name in set(s.cast) & props:
            if name.lower() not in body.lower():
                add("asset_named", s.id, f"call the prop by its exact asset name \"{name}\" in the beats (another "
                                         "wording draws another object)")
            noun = name.split()[-1].lower().rstrip("s")
            if re.search(rf"\b(?:two|2|both|second|matching|identical|another|pair of)\b(?:\W+\w+){{0,3}}?\W+{re.escape(noun)}",
                         body.lower()):
                add("twin_objects", s.id, f"two identical {noun}s from one reference collapse into one (20/10 Cảnh 1); "
                                          "make the second a different prop with its own reference")
        if (m := _CAMERA_OBJECT.search(vp)):
            add("camera_object", s.id, f"\"{m.group(0)}\" makes the model draw a camera/crew in the shot; describe only "
                                       "the view (\"slow forward dolly\", \"the camera tilts down\"), never the equipment")
        if (shown := _photo_faces(vp, props)):
            add("photo_faces", s.id, f"\"{shown[:120]}\" shows a photograph's picture to the lens: Flow invents sharp "
                                     "faces in it and its safety filter deletes the clip; keep the picture soft and "
                                     "unreadable (\"a faded grey square, no faces readable\") or turn it away")
        if (cue := _news_look(vp)):
            add("news_look", s.id, f"\"{cue}\" {NEWS_LOOK_MSG}")
        if s.bridge and not s.continues:
            prev = by_order.get(s.order - 1)
            if not mentions(s.bridge.element, vp):
                add("bridge_prompt", s.id, f"this shot opens on the bridge \"{s.bridge.element}\": write it verbatim")
            if prev and not mentions(s.bridge.element, prev.video_prompt):
                add("bridge_prompt", prev.shot_id, f"shot {s.id} is bridged by \"{s.bridge.element}\": end this shot on it")
    return out
