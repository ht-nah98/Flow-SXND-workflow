from pathlib import Path

ROLES = ["producer", "writer", "director", "dp", "editor", "qc", "coach"]
K = Path("agent/director/knowledge")


def test_every_role_has_a_prompt_that_names_its_output():
    for r in ROLES:
        text = (K / "roles" / f"{r}.md").read_text(encoding="utf-8")
        assert len(text) > 400, r


def test_rules_carry_the_omni_flash_limits_and_the_11_blocks():
    rules = (K / "rules.md").read_text(encoding="utf-8")
    for must in ("at most 2 actions", "at most 1 transition", "2–3 seconds", "exactly 10 seconds", "r2v",
                 "Giữ nguyên đúng như ảnh tham chiếu", "Thời lượng:", "không cắt cảnh", "one primary camera"):
        assert must in rules, must


def test_roles_get_their_playbook_chapters():
    from agent.director.brain import PLAYBOOK, PLAYBOOK_FOR, _system_prompt
    for role, files in PLAYBOOK_FOR.items():
        text = _system_prompt(role, "")
        for f in files:
            assert (PLAYBOOK / f).exists() and f"## Playbook: {f}" in text, (role, f)
    assert "## Playbook" not in _system_prompt("producer", "")


def test_every_role_reads_the_user_directives_first():
    from agent.director.brain import _system_prompt
    for role in ["writer", "director", "dp", "reshoot", "analyst", "editor", "qc", "producer", "coach"]:
        text = _system_prompt(role, "CTX")
        assert "## User directives" in text, role
        assert "Mặc định LUÔN là r2v" in text and "Chuyển cảnh mỗi 5–8 giây" in text, role
        assert text.index("## User directives") < text.index("CTX")
        assert "Quy tắc làm việc cho Claude Code" not in text  # 08 is for Claude Code, not the film roles


def test_shot_rules_only_reach_the_shot_roles():
    from agent.director.brain import RULES_FOR, _system_prompt
    marker = "# Shot-writing rules"
    for role in ["director", "dp", "reshoot", "editor", "qc"]:
        assert role in RULES_FOR and marker in _system_prompt(role, ""), role
    for role in ["writer", "producer", "coach"]:
        assert marker not in _system_prompt(role, ""), role


def test_no_role_is_told_to_keep_the_film_in_one_place():
    """Directive B3b (19/10): the old 'cover a main location' rule boxed every script into one room."""
    from agent.director.brain import _system_prompt
    for role in ["writer", "director", "editor", "dp"]:
        text = _system_prompt(role, "")
        for banned in ("Cover a main location", "for each main location", "CÙNG một không gian", "1–4 locations"):
            assert banned not in text, (role, banned)
    assert "never one room" in _system_prompt("writer", "")


def test_writer_and_editor_know_the_creativity_levels():
    from agent.director.brain import _system_prompt
    for role in ("writer", "editor"):
        text = _system_prompt(role, "")
        assert all(level in text for level in ('"faithful"', '"balanced"', '"bold"')), role


def test_prompt_examples_never_teach_more_than_two_timestamps():
    """19/10: playbook 03 showed '0-4s … 4-6s … 6-10s'; the DP copied it into all 44 prompts, lint rejected every one
    and the whole stage was redone on Opus. Every example a role reads must pass the same rule as the lint."""
    import re
    from agent.director.brain import _system_prompt
    for role in ("dp", "reshoot", "director"):
        for line in _system_prompt(role, "").splitlines():
            if line.lstrip("`> ").startswith(("Hành động:", "Action:")):
                assert len(re.findall(r"\d+(?:\.\d+)?-\d+(?:\.\d+)?s", line)) <= 2, (role, line)


def test_character_sheets_have_four_views():
    """SciCloud sample (19/10): close-up, front, side profile, back — the side view keeps profile shots on model."""
    from agent.director.brain import _system_prompt
    text = _system_prompt("writer", "")
    assert "side profile" in text and "three panels" not in text


def test_playbook_does_not_name_a_default_film_mode_the_code_does_not_use():
    """24/10: 00, 01, 03, 04, 09 and README called continuous "the default" while new ideas defaulted to cut (mistake
    #2); the user then decided "Liền mạch là mặc định". Only the code's default mode may be called the default."""
    from agent.api.director import RunCreate
    default = RunCreate.model_fields["film_mode"].default
    assert default == "continuous"
    titles = {"continuous": "09-phim-lien-mach.md", "keyframe": "10-phim-keyframe.md", "ambient": "11-phim-khong-khi.md"}
    for mode, name in titles.items():
        head = (K / "playbook" / name).read_text(encoding="utf-8").split("\n", 1)[0]
        assert ("mặc định" in head) == (mode == default), (name, head)
    star = [ln for ln in (K / "playbook" / "README.md").read_text(encoding="utf-8").splitlines() if "⭐ chế độ mặc định" in ln]
    assert len(star) == 1 and titles[default] in star[0], star
