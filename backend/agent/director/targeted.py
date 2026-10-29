"""Targeted revision (19/10): an editor fix rewrites only what it names, not the whole film.

Daniel v3 took 40 minutes to reach the script gate: every editor pass sent the writer, the director and the DP back
over all 27 beats and 55 shots for 8 fixes. Here the writer revises its previous story, the code finds which beats
and cast actually changed, the director re-plans only those beats' shots, the DP rewrites only the touched prompts.
Pure functions; the pipeline decides when a change is too big and redoes the stage in full."""
from agent.director.schemas import ShotList, ShotPrompts, Story

BEAT_FIELDS = ("sequence_id", "summary", "emotion", "voice_line")
CAST_FIELDS = ("entity_type", "description", "personality", "signature", "provided_image")


def plan_revision(fixes) -> dict:
    """What an editor report asks to redo: per stage, the shots it names, and the stages it hits film-wide."""
    plan = {"shots": {}, "film_wide": []}
    for f in fixes:
        if f.shot_id:
            plan["shots"].setdefault(f.target_stage, [])
            if f.shot_id not in plan["shots"][f.target_stage]:
                plan["shots"][f.target_stage].append(f.shot_id)
        elif f.target_stage != "STORY" and f.target_stage not in plan["film_wide"]:
            plan["film_wide"].append(f.target_stage)
    return plan


def story_changes(old: Story, new: Story) -> tuple[set[str], set[str]] | None:
    """(changed beat ids, changed cast names), or None when the beat list itself changed (added, removed, reordered):
    then every shot may move and the shotlist is redone in full."""
    if [b.id for b in old.beats] != [b.id for b in new.beats]:
        return None
    before = {b.id: b for b in old.beats}
    beats = {b.id for b in new.beats if any(getattr(b, f) != getattr(before[b.id], f) for f in BEAT_FIELDS)}
    was = {c.name: c for c in old.cast}
    cast = {c.name for c in new.cast
            if c.name not in was or any(getattr(c, f, None) != getattr(was[c.name], f, None) for f in CAST_FIELDS)}
    return beats, cast


def merge_shots(old: ShotList, new_shots: list, beats: set[str], story: Story) -> tuple[ShotList, set[str]]:
    """Replace the shots of `beats` with `new_shots` (each kept in story beat order), renumber, keep ids unique.
    Returns the merged list and the ids of the shots that are new or rewritten."""
    by_beat: dict[str, list] = {}
    for s in old.shots:
        if s.beat_id not in beats:
            by_beat.setdefault(s.beat_id, []).append(s)
    kept_ids = {s.id for ss in by_beat.values() for s in ss}
    touched, n = set(), 0
    for s in sorted(new_shots, key=lambda s: s.order):
        if s.beat_id not in beats:
            continue                                   # the director answered for a beat it was not asked about
        sid = s.id
        while sid in kept_ids or sid in touched:
            n += 1
            sid = f"{s.id}-r{n}"
        by_beat.setdefault(s.beat_id, []).append(s.model_copy(update={"id": sid}))
        touched.add(sid)
    order = [b.id for b in story.beats] + sorted(set(by_beat) - {b.id for b in story.beats})
    shots = [s for bid in order for s in by_beat.get(bid, [])]
    shots = [s.model_copy(update={"order": i}) for i, s in enumerate(shots, 1)]
    return old.model_copy(update={"shots": shots}), touched


def merge_prompts(old: ShotPrompts, new: ShotPrompts, shots: ShotList, ids: set[str]) -> ShotPrompts:
    """Prompts in shot order: rewritten ones for `ids`, the previous ones for the rest; dropped shots lose theirs."""
    fresh = {p.shot_id: p for p in new.prompts if p.shot_id in ids}
    prev = {p.shot_id: p for p in old.prompts}
    return old.model_copy(update={
        "prompts": [fresh.get(s.id) or prev[s.id] for s in shots.shots if s.id in fresh or s.id in prev],
        "style_block": new.style_block or old.style_block, "avoid_block": new.avoid_block or old.avoid_block})
