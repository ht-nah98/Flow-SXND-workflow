"""Story lint (spine, hook pacing, source text). Split from lint.py on 23/10 (code moved, not changed)."""
import re

from agent.director.schemas import Story
from agent.director.lint.common import LintIssue

# An idea this long is a story the user wrote: the script adapts it and must account for every part.
SOURCE_STORY_CHARS = 600


HOOK_EVERY_S = 30   # SciCloud sample: a strong line or image every 25–30s keeps a short-video viewer


def lint_story(story: Story, idea: str = "", target_s: int | None = None) -> list[LintIssue]:
    """The spine comes first: a story without a line, a message and a value for the viewer is a montage.
    A written idea is the source story: every part is kept, compressed or (with a reason) dropped."""
    out = []
    for field in ("story_line", "message", "viewer_value"):
        if len(getattr(story, field).strip()) < 10:
            out.append(LintIssue("story_spine", None, f"Story.{field} is missing: decide it before writing beats"))
    if len(story.director_notes) < 2:
        out.append(LintIssue("director_notes", None,
                             "write director_notes: the anti-cliché choice, the structure and why, the title line"))
    for c in story.cast:
        if c.entity_type == "visual_asset" and _PLURAL_PROP.search(f"{c.name} {c.description}"):
            out.append(LintIssue("prop_single", None,
                                 f"prop '{c.name}' shows several objects; a prop reference is ONE object on a plain "
                                 "background (20/10: a 'two mugs' picture put a third mug on the table). Make it one "
                                 "item and say the count in the shot"))
    beat_ids = {b.id for b in story.beats}
    if target_s:
        need = max(1, target_s // HOOK_EVERY_S - 1)
        if len(story.hooks) < need:
            out.append(LintIssue("hooks", None, f"a ~{target_s}s film needs at least {need} hooks (one every "
                                                f"25–30s), got {len(story.hooks)}"))
    for h in story.hooks:
        if h.beat_id not in beat_ids:
            out.append(LintIssue("hooks", None, f"hook at {h.at_s}s names unknown beat {h.beat_id}"))
    if len(idea.strip()) >= SOURCE_STORY_CHARS:
        if len(story.source_map) < 3:
            out.append(LintIssue("source_map", None,
                                 "the user wrote a full story: list every part of it (acts, key events, key lines) in "
                                 "source_map and the beats that show each part"))
        for sp in story.source_map:
            if sp.kept != "dropped" and not sp.beats:
                out.append(LintIssue("source_map", None, f"source part {sp.part!r} is kept but no beat shows it"))
            if any(b not in beat_ids for b in sp.beats):
                out.append(LintIssue("source_map", None, f"source part {sp.part!r} names unknown beats {sp.beats}"))
            if sp.kept == "dropped" and len(sp.note.strip()) < 10:
                out.append(LintIssue("source_map", None, f"source part {sp.part!r} is dropped without a reason in note"))
        dropped = [sp for sp in story.source_map if sp.kept == "dropped"]
        if story.source_map and len(dropped) * 4 > len(story.source_map):
            out.append(LintIssue("source_map", None,
                                 f"{len(dropped)}/{len(story.source_map)} parts of the user's story are dropped: "
                                 "compress them instead (one beat per part) and tell the user in notes_for_user "
                                 "if the length is too short"))
    return out

_PLURAL_PROP = re.compile(r"\b(?:two|three|pair of|twin|set of|several|exactly two)\b|\bhai\b|\bđôi\b|\bbộ\b", re.I)
