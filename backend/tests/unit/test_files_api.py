import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api import files as files_api


@pytest.fixture
def api(tmp_path, monkeypatch):
    out = tmp_path / "output"
    (out / "proj").mkdir(parents=True)
    (out / "proj" / "final.mp4").write_bytes(b"MP4DATA")
    (tmp_path / "secret.txt").write_text("nope")
    monkeypatch.setattr(files_api, "OUTPUT_DIR", out)
    app = FastAPI()
    app.include_router(files_api.router, prefix="/api")
    return TestClient(app), tmp_path


def test_serves_file_url_inside_output(api):
    client, tmp = api
    r = client.get("/api/files", params={"path": f"file://{tmp}/output/proj/final.mp4"})
    assert r.status_code == 200 and r.content == b"MP4DATA"


def test_rejects_outside_output(api):
    client, tmp = api
    assert client.get("/api/files", params={"path": f"{tmp}/secret.txt"}).status_code == 403


def test_rejects_traversal(api):
    client, tmp = api
    r = client.get("/api/files", params={"path": f"file://{tmp}/output/../secret.txt"})
    assert r.status_code == 403


def test_rejects_symlink_escaping_output(api):
    client, tmp = api
    (tmp / "output" / "proj" / "link.txt").symlink_to(tmp / "secret.txt")
    assert client.get("/api/files", params={"path": f"{tmp}/output/proj/link.txt"}).status_code == 403


def test_missing_file_404(api):
    client, tmp = api
    assert client.get("/api/files", params={"path": f"{tmp}/output/proj/none.mp4"}).status_code == 404
