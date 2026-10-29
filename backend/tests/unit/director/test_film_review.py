"""Agent Review (21/10): the cut film → per-clip sheets + seam images + plan → reviewer → findings placed on the film."""
import json
import subprocess

import pytest

from agent.director import brain, cut, film_review
from tests.unit.director.fake_plans import fake_responses
from tests.unit.director.test_qc_cut_stage import to_qc, world  # noqa: F401  (fixture)

REVIEW = {"summary": "Phim chạy được.", "strengths": ["ánh sáng"],
          "scores": [{"layer": l, "score": 6, "note": "ổn"} for l in ("story", "clips", "continuity", "edit")],
          "findings": [{"layer": "clips", "severity": "HIGH", "scene": 2, "clip_t": 5.5, "title": "Bình thành nồi",
                        "evidence": "sheet 2, khung 5", "cause": "asset", "cause_detail": "bình không có ảnh",
                        "fix": "thêm asset Steel Coffee Percolator", "action": "add_asset",
                        "rule": "A prop seen in 2+ clips needs its own reference image."}]}


@pytest.fixture
def clip(tmp_path):
    p = tmp_path / "c.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=10",
                    "-pix_fmt", "yuv420p", str(p)], check=True)
    return p


def test_clip_sheet_and_seam_are_single_images(clip, tmp_path):
    sheet = film_review.clip_sheet(clip, tmp_path / "s.jpg", 10)
    seam = film_review.seam_image(clip, 8.0, clip, 1.0, tmp_path / "seam.jpg")
    assert sheet.stat().st_size > 0 and seam.stat().st_size > 0


def test_film_time_places_a_finding_inside_the_used_window():
    clips = [{"used_in_film_s": [1.0, 8.0], "film_start_s": 0.0}, {"used_in_film_s": [2.0, 7.0], "film_start_s": 7.0}]
    assert film_review.film_time(clips, 2, 5.5) == 10.5
    assert film_review.film_time(clips, 2, 9.0) == 12.0          # past the window → its end
    assert film_review.film_time(clips, 3, 1.0) is None


async def test_review_sends_every_sheet_and_seam_and_saves_findings(world, clip, monkeypatch, tmp_path):
    monkeypatch.setattr("agent.config.DATA_DIR", str(tmp_path))
    resp = fake_responses() | {"reviewer": [REVIEW]}
    r = await to_qc(resp)

    async def real_clip(scene, ori, dest):
        return clip
    monkeypatch.setattr(cut, "local_clip", real_clip)
    entry = await film_review.review(r["id"], "giây 12 cái bình thành nồi")
    role, payload = [c for c in to_qc.brain.calls if c[0] == "reviewer"][0]
    n = len(payload["clips"])
    assert n == 3 and len(payload["seams"]) == n - 1 and payload["user_note"].startswith("giây 12")
    assert all(c["sheet"].endswith(".jpg") for c in payload["clips"])
    f = entry["findings"][0]
    assert f["id"] == "F1" and f["shot_id"] == payload["clips"][1]["shot_id"] and f["film_t"] is not None
    assert film_review.list_reviews(r["id"])[0]["id"] == entry["id"]
    json.dumps(entry)                                              # stored as JSON


async def test_the_reviews_rules_become_lessons_for_the_next_film(test_db):
    """22/10: each finding carries a rule for next time; none was kept, so the next film could not learn."""
    from agent.director import lessons, store
    f = [{"layer": "continuity", "severity": "CRITICAL", "shot_id": "SH03", "title": "lamp between two jungles",
          "rule": "In a light bridge never name the source object from the other time."},
         {"layer": "story", "severity": "MINOR", "shot_id": "SH06", "title": "weak choice", "rule": "Show the rejected choice."},
         {"layer": "clips", "severity": "HIGH", "title": "no rule", "rule": None}]
    await lessons.learn_from_film_review(f, "r1")
    await lessons.learn_from_film_review(f[:1], "r2")                       # same rule again: one lesson, two films
    rows = {l["rule"]: l for l in await store.list_lessons()}
    bridge = rows["In a light bridge never name the source object from the other time."]
    assert (bridge["scope"], bridge["status"], len(bridge["evidence"])) == ("omni_flash", "ACTIVE", 2)
    assert rows["Show the rejected choice."]["status"] == "PROPOSED" and len(rows) == 2
    assert "never name the source object" in await lessons.context_for("dp")
