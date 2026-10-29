"""Prompt lint for cut-mode films (the labelled-block template); dispatches the other modes. Split from lint.py on 23/10 (code moved, not changed)."""
import re

from agent.director import knowledge as k
from agent.director.schemas import ShotList, ShotPrompts, Story
from agent.director.lint.common import LintIssue, NEWS_LOOK_MSG, _CAMERA_OBJECT, _news_look, _photo_faces, _words, mentions
from agent.director.lint.ambient import lint_prompts_ambient
from agent.director.lint.continuous import _lint_prompts_cont
from agent.director.lint.keyframe import _lint_prompts_kf

# The FMV prompt template (playbook 03), in Vietnamese — the format that produced the remake — or its English
# twin for films set in an English-speaking world (brief.language == "en"). Keys stay the Vietnamese labels.
BLOCK_LABELS: dict[str, tuple[str, ...]] = {
    "Ảnh tham chiếu": ("Ảnh tham chiếu", "Reference images", "References"),
    "Nhân vật & trang phục": ("Nhân vật & trang phục", "Nhân vật", "Characters & wardrobe", "Characters"),
    "Bối cảnh": ("Bối cảnh", "Setting"),
    "Góc quay": ("Góc quay", "Shot"),
    "Hành động": ("Hành động", "Action"),
    "Chuyển động camera": ("Chuyển động camera", "Camera movement"),
    "Ánh sáng & màu sắc": ("Ánh sáng & màu sắc", "Ánh sáng", "Lighting & color", "Lighting"),
    "Âm thanh": ("Âm thanh", "Audio"),
    "Physics": ("Physics", "Vật lý"),
    "Props": ("Props", "Đạo cụ"),
    "Thời lượng": ("Thời lượng", "Duration"),
}
REQUIRED_BLOCKS: dict[str, tuple[str, ...]] = {
    k: BLOCK_LABELS[k] for k in ("Bối cảnh", "Góc quay", "Hành động", "Chuyển động camera", "Thời lượng")
}
# 20/10: the FMV prompts that worked were ~570 characters; Cảnh 1's were 1,800–2,600 (≈400 words) and the clip
# grew a third mug, a tripod camera and a mug that turned into a pot. Guides agree: ~100–150 words, one gesture.
MAX_PROMPT_CHARS = 1000
_KEY = {re.sub(r"\s+", "", alias.upper()): key for key, aliases in BLOCK_LABELS.items() for alias in aliases}
_LABEL_ALT = "|".join(
    r"\s*".join(re.escape(w) for w in alias.split())
    for alias in sorted((a for aliases in BLOCK_LABELS.values() for a in aliases), key=len, reverse=True))
_HEADER = re.compile(
    rf"^(?P<label>{_LABEL_ALT})\*{{0,2}}\s*(?:\([^)]*\))?\s*\*{{0,2}}:\*{{0,2}}(?P<rest>.*)$", re.I)
_TS = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*s?\s*[–-]\s*(\d+(?:\.\d+)?)\s*s\b")
_HOLD = re.compile(r"giữ|ổn định|đứng yên|\bhold|\bstable")
_SEQ = re.compile(r"\brồi\b|sau đó|→|\bthen\b")
_KEEP = re.compile(r"giữ nguyên|exactly as (?:in )?the reference", re.I)
_CLOSE_LOOK = re.compile(r"không cắt|no cuts?\b|single continuous|one continuous")


def _normalise(line: str) -> str:
    """Strip markdown bullets/headers, a leading list number, and trailing emphasis for header matching."""
    s = re.sub(r"^[\s*#>\-]+", "", line)
    s = re.sub(r"^\d+[.)]\s+", "", s)
    return re.sub(r"[\s*]+$", "", s)


def _parse_blocks(text: str) -> dict[str, str]:
    """Split a prompt into {canonical block label: body}. Only known labels open or end a block."""
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        m = _HEADER.match(_normalise(raw))
        if m:
            current = _KEY[re.sub(r"\s+", "", m.group("label").upper())]
            body = blocks.setdefault(current, [])
            if m.group("rest").strip():
                body.append(m.group("rest").strip())
        elif current is not None:
            blocks[current].append(raw)
    return {k: "\n".join(v) for k, v in blocks.items()}


def _duration_re(d: float) -> re.Pattern:
    return re.compile(rf"(?<![\d.]){re.escape(f'{d:g}')}\s*(?:-\s*)?(?:giây|seconds?|s)\b", re.I)


def lint_prompts(prompts: ShotPrompts, shots: ShotList, story: Story, style_marker: str | None = None,
                 film_mode: str = "cut") -> list[LintIssue]:
    if film_mode == "continuous":
        return _lint_prompts_cont(prompts, shots, story, style_marker)
    if film_mode == "keyframe":
        return _lint_prompts_kf(prompts, shots, story, style_marker)
    if film_mode == "ambient":
        return lint_prompts_ambient(prompts, shots, story, style_marker)
    out: list[LintIssue] = []
    add = lambda rule, sid, msg: out.append(LintIssue(rule, sid, msg))  # noqa: E731
    by_id = {p.shot_id: p for p in prompts.prompts}
    by_order = {s.order: by_id[s.id] for s in shots.shots if s.id in by_id}
    people = {c.name for c in story.cast if c.entity_type == "character"}
    props = {c.name for c in story.cast if c.entity_type == "visual_asset"}
    for s in shots.shots:
        p = by_id.get(s.id)
        if not p:
            add("missing_prompt", s.id, "no prompt for shot")
            continue
        vp = p.video_prompt
        blocks = _parse_blocks(vp)
        # One look for the whole film (style pack): its marker sits in every clip's lighting line.
        if style_marker and style_marker.lower() not in blocks.get("Ánh sáng & màu sắc", "").lower():
            add("style_pack", s.id, f"the film's style pack: write \"{style_marker}\" in the Lighting & color line")
        for name in REQUIRED_BLOCKS:
            if name not in blocks:
                add("missing_block", s.id, f"missing {name} block")
        dur = blocks.get("Thời lượng", "")
        if not (_duration_re(s.duration_s).search(dur) and _CLOSE_LOOK.search(dur.lower())):
            add("duration_block", s.id, f"Thời lượng must state '{s.duration_s:g} giây' and 'không cắt cảnh'")
        if set(s.cast) & people and not _KEEP.search(blocks.get("Nhân vật & trang phục", "")):
            add("constraints", s.id, "Nhân vật & trang phục / Characters & wardrobe must say 'Giữ nguyên đúng như ảnh "
                                     "tham chiếu' / 'exactly as in the reference images'")
        stamps = [(float(a), float(b)) for a, b in _TS.findall(blocks.get("Hành động", ""))]
        if any(b > s.duration_s or a >= b for a, b in stamps) or stamps != sorted(stamps):
            add("timestamps", s.id, f"Hành động timestamps must increase and stay within {s.duration_s:g}s: {stamps}")
        if len(stamps) > 2:
            add("timestamps", s.id, f"{len(stamps)} timed beats; Omni Flash allows at most 2")
        if s.voice_line and _words(s.voice_line) not in _words(blocks.get("Âm thanh", "")):
            add("voice_line", s.id, f"Âm thanh must contain the shot's spoken line verbatim in quotes: \"{s.voice_line}\"")
        for name in people - set(s.cast):
            if re.search(rf"\b{re.escape(name)}\b", vp):
                add("extra_person", s.id, f"{name} is mentioned but not in this shot's cast")
        if p.keyframe_prompt:
            add("keyframe", s.id, "keyframe_prompt must be empty: every shot is r2v")
        body = "\n".join(v for k, v in blocks.items() if k != "Ảnh tham chiếu")
        for name in set(s.cast) & props:
            # 20/10 Cảnh 1: "steel coffee pot" in clip 1, "steel pot" in clip 2 → a saucepan. A referenced prop is
            # called by its exact asset name in every clip.
            if name.lower() not in body.lower():
                add("asset_named", s.id, f"call the prop by its exact asset name \"{name}\" in the Setting/Action "
                                         "lines (another wording draws another object)")
            noun = name.split()[-1].lower().rstrip("s")
            if re.search(rf"\b(?:two|2|both|second|matching|identical|another|pair of)\b(?:\W+\w+){{0,3}}?\W+{re.escape(noun)}",
                         vp.lower()):
                add("twin_objects", s.id, f"two identical {noun}s from one reference collapse into one (20/10 Cảnh 1); "
                                          "make the second a different prop with its own reference")
        if (m := _CAMERA_OBJECT.search(vp)):
            add("camera_object", s.id, f"\"{m.group(0)}\" makes the model draw a camera/crew in the shot; describe only "
                                       "the view (\"static wide shot\", \"slow push-in\"), never the equipment")
        if (shown := _photo_faces(vp, props)):
            add("photo_faces", s.id, f"\"{shown[:120]}\" shows a photograph's picture to the lens: Flow invents sharp "
                                     "faces in it and its safety filter deletes the clip; keep the picture soft and "
                                     "unreadable (\"a faded grey square, no faces readable\") or turn it away")
        if (cue := _news_look(vp)):
            add("news_look", s.id, f"\"{cue}\" {NEWS_LOOK_MSG}")
        if s.bridge:
            prev = by_order.get(s.order - 1)
            if not mentions(s.bridge.element, vp):
                add("bridge_prompt", s.id, f"this shot opens on the bridge \"{s.bridge.element}\": write it verbatim in the prompt")
            if prev and not mentions(s.bridge.element, prev.video_prompt):
                add("bridge_prompt", prev.shot_id, f"shot {s.id} is bridged by \"{s.bridge.element}\": this shot must end "
                                                   "on it — write it verbatim in this prompt")
        if len(vp) > MAX_PROMPT_CHARS:
            add("too_long", s.id, f"video_prompt {len(vp)} chars > {MAX_PROMPT_CHARS}: one short sentence per line, "
                                  "name each object once, cut every detail the shot does not need")
        cam = blocks.get("Chuyển động camera", "").lower()
        moves = [c for c in s.commands if k.group_of(c) == k.MOVEMENT_GROUP]
        if len(moves) == 2 and not (_SEQ.search(cam) or _TS.search(cam)):
            add("movement_sequence", s.id, "two movements must be written in order ('… rồi …' / '→') or with timestamps")
        if s.transition:
            hold = _HOLD.search(cam)
            if not (hold and _SEQ.search(cam, hold.end())):
                add("transition_prompt", s.id,
                    "Chuyển động camera must hold a stable frame first ('giữ khung ổn định …'), then '→'/'rồi' the move")
    return out
