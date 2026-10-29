"""Shot-list lint for every film mode; the continuous and keyframe extras live in their own modules. Split from lint.py on 23/10 (code moved, not changed)."""
import re

from agent.director import knowledge as k
from agent.director.schemas import ShotList, Story
from agent.director.lint.common import LintIssue, MAX_ACTION_WORDS, _COMPOUND, _norm_period
from agent.director.lint.continuous import _lint_beats, _lint_chain
from agent.director.lint.ambient import lint_shotlist_ambient
from agent.director.lint.keyframe import _lint_kf_chain, _lint_kf_shot

SINGLE_GROUPS = ("framing", "angle", "perspective", "rig")
# Omni Flash accepts 7 references, but the FMV sample (playbook 02/03) uses 2–3 per clip: more pictures dilute the
# faces. 19/10: the rules said 1–3 while lint allowed 7, so the editor caught 4-ref clips only after a full pass.
MAX_REFS = 4   # 20/10: 3 forced Cảnh 1 to drop the kitchen picture once a clip needed two props; 4 = person + place + 2 props
# Keyframe mode: the pictures only draw the still (the clip is made from the still), so a family of four plus their
# room fits. 23/10 "Home for Christmas": the family-photo shot needed 5 and the director failed 3 times at 4.
KF_MAX_REFS = 6
CLIP_S = 10
# Directive E1b: the chosen length is a rough size. The cut keeps ~5.5s of each 10s clip; the estimated film may
# drift freely inside FILM_FLEX_WARN, gets a note inside FILM_FLEX_ERROR, and only a film far off is sent back.
FILM_PER_CLIP_S = 5.5
FILM_FLEX_WARN = (0.75, 1.4)
FILM_FLEX_ERROR = (0.5, 2.0)


def lint_shotlist(shots: ShotList, story: Story, target_s: int, language: str = "en",
                  film_mode: str = "cut") -> list[LintIssue]:
    if film_mode == "ambient":
        return lint_shotlist_ambient(shots, story, target_s)
    cont = film_mode == "continuous"
    kf = film_mode == "keyframe"
    max_words = (MAX_VOICE_WORDS_EN_CONT if language == "en" else MAX_VOICE_WORDS_CONT) if cont else \
        (MAX_VOICE_WORDS_EN if language == "en" else MAX_VOICE_WORDS)
    out: list[LintIssue] = []
    add = lambda rule, sid, msg, sev="error": out.append(LintIssue(rule, sid, msg, sev))  # noqa: E731

    # Every clip is a 10s source and the edit keeps ~5.5s of each (playbook 04). target_s is approximate (E1b).
    # Continuous mode keeps almost the whole clip (playbook 09 §7): only the repeated opening frames go.
    film = (sum(s.duration_s - CONT_TRIM_S for s in shots.shots) if cont
            else sum(s.use_s or KF_USE_DEFAULT_S for s in shots.shots) if kf else len(shots.shots) * FILM_PER_CLIP_S)
    ratio = film / target_s
    per = film / max(1, len(shots.shots)) if cont or kf else FILM_PER_CLIP_S
    # Keyframe mode knows each shot's kept seconds (use_s), so the length can be held tighter (22/10: 14 shots made
    # 51.5s for a 30s ask and passed as a warning).
    flex_error = KF_FLEX_ERROR if kf else FILM_FLEX_ERROR
    if not flex_error[0] <= ratio <= flex_error[1]:
        add("total_duration", None,
            f"{len(shots.shots)} clips make a ~{round(film)}s film, far from the ~{target_s}s asked; "
            f"use about {round(target_s / per)} clips (anything from "
            f"{round(target_s * FILM_FLEX_WARN[0] / per)} to {round(target_s * FILM_FLEX_WARN[1] / per)} is fine)")
    elif not FILM_FLEX_WARN[0] <= ratio <= FILM_FLEX_WARN[1]:
        add("total_duration", None,
            f"the film will run ~{round(film)}s for ~{target_s}s asked; fine if the story needs it", "warning")

    names = {c.name for c in story.cast}
    places = {c.name for c in story.cast if c.entity_type == "location"}
    beats = {b.id: b for b in story.beats}
    for s in shots.shots:
        for n in s.cast:
            if n not in names:
                add("cast_unknown", s.id, f"cast name {n!r} not in story cast {sorted(names)}")
        cap = KF_MAX_REFS if kf else MAX_REFS - 1 if cont and s.continues else MAX_REFS   # cont: last frame is ref #1
        if len(s.cast) > cap:
            add("too_many_refs", s.id, f"{len(s.cast)} refs > {cap}: keep the {cap} the clip leans on "
                "(faces first), describe the rest in the prompt"
                + (" — a continuing clip's first reference is the previous clip's last frame" if cap < MAX_REFS else ""))
        if places and not set(s.cast) & places:
            add("location_ref", s.id, "every clip carries its location picture (without it the room is redrawn "
                "differently from the clip before); drop a lesser prop instead")
        if s.mode != "r2v" and not kf:
            add("mode_r2v", s.id, "every shot is reference-to-video (r2v); no keyframe images")
        if kf:
            _lint_kf_shot(s, story, add)
        elif cont and s.duration_s not in CONT_CLIP_S:
            add("clip_duration", s.id, f"a continuous clip is 8 or 10s (used almost whole), got {s.duration_s}s")
        elif not cont and s.duration_s != CLIP_S:
            add("clip_duration", s.id, f"every clip is {CLIP_S}s (trimmed in the edit), got {s.duration_s}s")
        if not s.cast:
            add("r2v_no_refs", s.id, "r2v needs at least one reference")
        if s.beat_id not in beats:
            add("beat_unknown", s.id, f"beat {s.beat_id!r} not in story")
        if not kf:
            _lint_commands(s, add, cont)
        if cont:
            _lint_beats(s, add)
        elif not kf:
            _lint_actions(s, add)
            _lint_transition(s, add)
        if s.voice_line and len(s.voice_line.split()) > max_words:
            add("voice_too_long", s.id, f"voice_line has {len(s.voice_line.split())} words; at most "
                f"{max_words} fit the ~5s the edit keeps — shorten it or split it over two clips")

    orders = sorted(s.order for s in shots.shots)
    if orders != list(range(1, len(orders) + 1)):
        add("order", None, f"shot order must be 1..N, got {orders}")

    used_seq = {beats[s.beat_id].sequence_id for s in shots.shots if s.beat_id in beats}
    for sq in story.sequences:
        if sq.id not in used_seq:
            add("empty_sequence", None, f"sequence {sq.id} has no shots")
    if cont:
        _lint_chain(shots, story, add)
    elif kf:
        _lint_kf_chain(shots, story, add)
    else:
        _lint_continuity(shots, story, add)
    _lint_recurring_props(shots, story, add)
    return out
KF_USE_DEFAULT_S = 3.0
KF_FLEX_ERROR = (0.7, 1.35)


_COUNTED = re.compile(r"^\s*(?:\d+|one|two|three|a single)\s+(.+)$", re.I)


def _prop_key(entry: str) -> str:
    """The object an entry is about, only for entries that open with a count ("1 steel coffee pot: …")."""
    m = _COUNTED.match(re.split(r"[:→,(]", entry, maxsplit=1)[0])
    if not m:
        return ""
    words = [w for w in re.sub(r"\s+", " ", m.group(1)).strip().lower().split() if w not in ("identical", "matching")]
    return " ".join(words)


def _noun(phrase: str) -> str:
    return phrase.split()[-1].rstrip("s") if phrase else ""


def _lint_recurring_props(shots: ShotList, story: Story, add):
    """20/10 Cảnh 1: the coffee pot was in 4 clips with no reference picture — a percolator in one, a saucepan in the
    next. An object seen in 2+ clips is a cast prop (visual_asset) with its own reference."""
    assets = [c.name.lower() for c in story.cast if c.entity_type == "visual_asset"]
    seen: dict[str, list[str]] = {}
    for s in shots.shots:
        for e in s.props:
            k = _prop_key(e)
            if k and len(k.split()) <= 6:
                seen.setdefault(k, []).append(s.id)
    for k, ids in seen.items():
        if len(set(ids)) >= 2 and _noun(k) not in {_noun(a) for a in assets}:
            add("recurring_prop", ids[0], f"'{k}' appears in {len(set(ids))} clips ({', '.join(sorted(set(ids)))}) without a "
                "reference picture: add it to story.cast as a visual_asset and name it exactly so in every prompt")


def _lint_continuity(shots: ShotList, story: Story, add):
    """Directive B7/B11, said 15/10, 16/10, 19/10: a cut between two story times needs a bridge seen in both shots;
    a cut to another place without one is flagged. Written rules alone were forgotten three times — this is the check."""
    places = {c.name for c in story.cast if c.entity_type == "location"}
    seq = sorted(shots.shots, key=lambda s: s.order)
    for prev, cur in zip(seq, seq[1:]):
        if _norm_period(prev.period) != _norm_period(cur.period):
            if not cur.bridge:
                add("time_bridge", cur.id,
                    f"cut from '{prev.period}' ({prev.id}) to '{cur.period}' needs a bridge: one object, sound or "
                    "gesture seen in both shots — the previous shot ends on it, this one opens on it (e.g. young Daniel "
                    "lifts the ringing phone → present Daniel lifts the same phone; close on the ring → young Daniel "
                    "holding that ring)")
        elif (set(prev.cast) & places) and (set(cur.cast) & places) and not (set(prev.cast) & set(cur.cast) & places) \
                and not cur.bridge and not prev.edit_transition_out:
            add("place_jump", cur.id, f"jumps from {sorted(set(prev.cast) & places)} to {sorted(set(cur.cast) & places)} "
                "with no bridge or edit transition — give the cut a reason (a bridge, or an edit transition)", "warning")


def _lint_commands(s, add, cont: bool = False):
    known = []
    for c in s.commands:
        if not k.resolve(c):
            add("unknown_command", s.id, f"unknown command {c}")
        else:
            known.append(c)
    for g in SINGLE_GROUPS:
        in_g = [c for c in known if k.group_of(c) == g]
        if len(in_g) > 1:
            add("group_duplicate", s.id, f"more than one {g} command: {in_g}")
    moves = [c for c in known if k.group_of(c) == k.MOVEMENT_GROUP]
    # Continuous mode: the clip IS one camera journey (dolly → lower → follow), so several moves chain in order.
    if not cont and (len(moves) > 2 or (len(moves) == 2 and s.duration_s < 8)):
        add("movement_count", s.id, f"one primary movement per shot (2 only if ≥8s, sequential): {moves}")
    for i, a in enumerate(known):
        for b in known[i + 1:]:
            if k.conflicts(a, b):
                add("conflict", s.id, f"{a} conflicts with {b}")
    macros = [c for c in known if k.type_of(c) == "macro"]
    if not cont and (len(macros) > 1 or (macros and any(k.type_of(m) == "atomic" for m in moves))):
        add("macro", s.id, f"max one macro and no extra atomic movement: {macros + moves}")


def _lint_actions(s, add):
    for a in s.actions:
        if len(a.what.split()) > MAX_ACTION_WORDS or _COMPOUND.search(a.what):
            add("action_compound", s.id, f"action {a.what!r} is a chain; one action = ONE gesture of ≤{MAX_ACTION_WORDS} "
                "words (a pour, a reach, a turn) — split the rest into another clip")
    limit = 1 if s.duration_s == 4 else 2
    if not 1 <= len(s.actions) <= limit:
        add("actions_count", s.id, f"{len(s.actions)} actions; Omni Flash allows 1..{limit} in a {s.duration_s}s clip")
    for a in s.actions:
        if a.end_s > s.duration_s or a.start_s >= a.end_s:
            add("action_range", s.id, f"action {a.what!r} {a.start_s}-{a.end_s}s outside 0-{s.duration_s}s")
    ordered = sorted(s.actions, key=lambda a: a.start_s)
    for x, y in zip(ordered, ordered[1:]):
        if x.end_s - y.start_s > 1:
            add("action_overlap", s.id, f"actions {x.what!r} and {y.what!r} overlap > 1s")


def _lint_transition(s, add):
    t = s.transition
    if not t:
        return
    if s.stable_open_s < 2 or t.start_s < s.stable_open_s or s.duration_s - t.start_s < 1.5:
        add("transition_timing", s.id,
            f"transition must start after ≥2s stable framing and leave ≥1.5s (stable_open={s.stable_open_s}, "
            f"start={t.start_s}, clip={s.duration_s}s)")
    moves = [c for c in s.commands if k.group_of(c) == k.MOVEMENT_GROUP
             and k.resolve(c) is not k.resolve(t.technique)]
    if moves:
        add("transition_plus_movement", s.id, f"a clip with a transition may not add another movement: {moves}")
MAX_VOICE_WORDS = 18     # Vietnamese speech ≈ 4 syllables/s; a line must fit inside the ~5s kept from each clip
MAX_VOICE_WORDS_EN = 13  # English ≈ 2.5 words/s
# Continuous mode (directive B12, playbook 09; the user's SIU Christmas film, 21/10).
CONT_CLIP_S = (8, 10)
CONT_TRIM_S = 0.5          # the repeated opening frames of a clip that continues the one before
MAX_VOICE_WORDS_CONT = 28  # the clip is kept almost whole, so a line may fill ~6s
MAX_VOICE_WORDS_EN_CONT = 18
