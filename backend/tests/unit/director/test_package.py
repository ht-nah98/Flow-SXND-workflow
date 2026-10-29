"""SciCloud sample (19/10): every script comes as a readable package — README, script, storyboard + prompts."""
from agent.director import package
from tests.unit.director.fixtures import fmv_prompts, fmv_shotlist, fmv_story


def _run():
    story = fmv_story().model_dump()
    story["cast"][0]["personality"] = "nói thẳng, cười to"
    story["sequences"][0].update(start_s=0, end_s=30)
    return {"brief": {"text": "x"}, "plan": {
        "brief": {"logline": "Two lovers bake.", "target_s": 30, "language": "en", "voice": "none"},
        "story": story, "shotlist": fmv_shotlist().model_dump(), "prompts": fmv_prompts().model_dump(),
        "editor": {"score": 82}}}


def test_the_package_reads_like_a_handover():
    files = package.build(_run(), "Bánh kem")
    assert list(files) == list(package.FILES)
    readme, script, board = files.values()
    assert "## Ý đồ của đạo diễn" in readme and "Không kể chia tay bằng cãi vã" in readme
    assert "**0:08** — vệt bột trên má" in readme
    assert "3 clip 10s" in readme and "~45 credit" in readme and "Editor chấm 82/100" in readme
    assert "Màn 1 (0:00–0:30) — Baking" in script and "Tính cách: nói thẳng, cười to" in script
    assert "⏱ **0:08**" in script
    assert "### Clip 1 — baking together" in board and "Hành động: 0-6s" in board


def test_the_users_canvas_edits_win():
    files = package.build(_run(), "Bánh kem", {"s1": {"video_prompt": "MY OWN PROMPT", "horizontal_video_status": "COMPLETED"}})
    assert "MY OWN PROMPT" in files["phan-canh-prompt.md"] and "Video đã có: 1/3 clip" in files["README.md"]


def test_it_is_saved_next_to_the_film(tmp_path, monkeypatch):
    from agent import config
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))
    folder = package.write({"id": "abcdef12-0000", "name": "Bánh kem"}, {"README.md": "hi"})
    assert folder.name == "kich-ban" and (folder / "README.md").read_text() == "hi"
