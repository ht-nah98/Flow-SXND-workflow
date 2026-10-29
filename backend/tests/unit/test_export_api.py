import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api.export import router as export_router
from agent.config import OUTPUT_DIR
from agent.db import crud
from agent.utils.paths import project_folder


@pytest.fixture
def api(test_db):
    app = FastAPI()
    app.include_router(export_router, prefix="/api")
    return TestClient(app)


def _write(path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


@pytest.fixture
async def project_with_media(tmp_path):
    proj = await crud.create_project(name="Export Test XYZ")
    char_img = _write(tmp_path / "char.jpg", b"char-image-bytes")
    char = await crud.create_character(name="Lan", entity_type="character",
                                        reference_image_url=f"file://{char_img}", media_id="m1")
    await crud.link_character_to_project(proj["id"], char["id"])

    video = await crud.create_video(project_id=proj["id"], title="V1", orientation="HORIZONTAL")
    scene_img = _write(tmp_path / "scene.jpg", b"scene-image-bytes")
    scene_vid = _write(tmp_path / "scene.mp4", b"scene-video-bytes")
    scene = await crud.create_scene(video_id=video["id"], display_order=0, prompt="x")
    await crud.update_scene(scene["id"], horizontal_image_url=f"file://{scene_img}",
                            horizontal_video_url=f"file://{scene_vid}")
    return proj, char, video, scene


def _slug(proj):
    return project_folder(proj)


async def test_export_downloads_and_zips_current_media(api, project_with_media):
    proj, char, video, scene = project_with_media
    r = api.post(f"/api/projects/{proj['id']}/export")
    assert r.status_code == 200
    body = r.json()
    assert body["downloaded"] == 3
    assert body["skipped"] == []

    slug = _slug(proj)
    project_dir = OUTPUT_DIR / slug
    assert (project_dir / "characters" / "lan.jpg").read_bytes() == b"char-image-bytes"
    assert (project_dir / "scenes" / "horizontal" / f"scene_000_{scene['id']}_image.jpg").read_bytes() == b"scene-image-bytes"
    assert (project_dir / "scenes" / "horizontal" / f"scene_000_{scene['id']}_video.mp4").read_bytes() == b"scene-video-bytes"

    assert body["zip_path"].startswith("file://")
    zip_path = Path(body["zip_path"].removeprefix("file://"))
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert any(n.endswith("lan.jpg") for n in names)
    assert any(n.endswith("_image.jpg") for n in names)
    assert any(n.endswith("_video.mp4") for n in names)


async def test_export_skips_missing_media_without_failing(api, test_db):
    proj = await crud.create_project(name="Export Empty XYZ")
    r = api.post(f"/api/projects/{proj['id']}/export")
    assert r.status_code == 200
    body = r.json()
    assert body["downloaded"] == 0
    assert body["skipped"] == []


async def test_export_reports_broken_link_but_continues(api, tmp_path, test_db):
    proj = await crud.create_project(name="Export Broken XYZ")
    good_img = _write(tmp_path / "ok.jpg", b"ok-bytes")
    char_ok = await crud.create_character(name="Good", entity_type="character",
                                          reference_image_url=f"file://{good_img}", media_id="m1")
    char_broken = await crud.create_character(name="Broken", entity_type="character",
                                              reference_image_url=f"file:///no/such/file.jpg", media_id="m2")
    await crud.link_character_to_project(proj["id"], char_ok["id"])
    await crud.link_character_to_project(proj["id"], char_broken["id"])

    r = api.post(f"/api/projects/{proj['id']}/export")
    assert r.status_code == 200
    body = r.json()
    assert body["downloaded"] == 1
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["id"] == char_broken["id"]

    slug = _slug(proj)
    assert (OUTPUT_DIR / slug / "characters" / "good.jpg").is_file()


async def test_export_unknown_project_404(api, test_db):
    r = api.post("/api/projects/does-not-exist/export")
    assert r.status_code == 404
