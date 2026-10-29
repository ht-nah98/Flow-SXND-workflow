import json

from agent.director import knowledge as k


def test_library_has_all_100_commands_with_unique_ids():
    entries = {id(e): e for e in k.load_commands().values()}.values()
    nums = sorted(e["num"] for e in entries)
    assert nums == list(range(1, 101))


def test_groups_and_types_match_the_bible():
    assert k.group_of("/pov") == "perspective"
    assert k.group_of("dolly-in") == "movement"
    assert k.group_of("/handheld") == "rig"
    assert k.type_of("/macrozoom") == "macro"
    assert k.type_of("/snorricam") == "composite"


def test_alias_resolves_to_canonical_entry():
    assert k.resolve("/360")["id"] == "orbit-360"
    assert k.resolve("/nope") is None


def test_every_avoid_reference_points_to_a_real_command():
    for e in k.load_commands().values():
        for a in e["avoid"]:
            assert k.resolve(a), (e["id"], a)


def test_conflicts_from_bible_section_11():
    assert k.conflicts("/static", "/dolly-in")
    assert k.conflicts("/handheld", "/gimbal")
    assert k.conflicts("/pov", "/over-shoulder")
    assert k.conflicts("/low-angle", "/high-angle")
    assert k.conflicts("/zoom-in", "/dolly-in")
    assert not k.conflicts("/pov", "/handheld")



def _raw_entries():
    return json.loads((k.DIR / "commands.json").read_text(encoding="utf-8"))


def test_ids_and_aliases_are_unique_across_entries():
    names = [n for e in _raw_entries() for n in [e["id"], *e["aliases"]]]
    assert len(names) == len(set(names))


def test_ambiguous_earthzoom_alias_is_dropped():
    assert k.resolve("/earthzoom") is None


def test_no_command_lists_itself_in_avoid():
    for e in _raw_entries():
        assert e["id"] not in e["avoid"], e["id"]
