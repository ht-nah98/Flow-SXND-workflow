import subprocess

import pytest

from agent import config
from agent.director import brain, learn, store


@pytest.fixture
def sample(tmp_path, monkeypatch, test_db):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(learn, "PLAYBOOK_SAMPLES", tmp_path / "playbook")
    video = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=160x90:d=2",
                    "-f", "lavfi", "-i", "color=c=blue:s=160x90:d=2", "-filter_complex", "[0][1]concat=n=2:v=1",
                    "-pix_fmt", "yuv420p", str(video)], check=True)
    analysis = {"title": "Mẫu thử", "summary": "s", "structure": "2 shot",
                "shots": [{"start_s": 0, "end_s": 2, "content": "đỏ", "framing": "toàn", "angle": "ngang",
                           "movement": "đứng yên", "transition_in": "cắt thẳng", "look": "đỏ"}],
                "techniques": [{"name": "Flash", "scope": "edit", "rule": "Khi nhảy thời gian, chèn flash trắng",
                                "how": "fade trắng 4 khung", "example": "2.0s"},
                               {"name": "Bỏ", "scope": "prompt", "rule": "x", "how": "y", "example": "z"}]}
    fb = brain.FakeBrain({"analyst": [analysis]})
    brain.set_brain(fb)
    yield video, fb
    brain.reset_brain()


async def test_analyze_finds_the_cut_and_adopt_writes_playbook_and_lessons(sample):
    video, fb = sample
    meta = learn.save_upload("mau.mp4", video.read_bytes())
    meta = await learn.analyze(meta["id"])
    assert meta["status"] == "READY", meta
    payload = fb.calls[0][1]
    assert any(1.5 < c < 2.5 for c in payload["cuts"]) and payload["sheets"]
    meta = await learn.adopt(meta["id"], [0])
    assert meta["status"] == "ADOPTED"
    assert "Flash" in open(meta["playbook"], encoding="utf-8").read()
    rules = [l["rule"] for l in await store.list_lessons(status="ACTIVE")]
    assert any("flash trắng" in r for r in rules) and not any(r.startswith("x") for r in rules)
