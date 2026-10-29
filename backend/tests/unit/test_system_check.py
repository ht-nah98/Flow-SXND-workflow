from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api.system import router


def test_system_check_lists_every_part_with_a_fix_when_broken(monkeypatch):
    import agent.api.system as sysmod
    monkeypatch.setattr(sysmod.shutil, "which", lambda name: None if name == "claude" else f"/usr/bin/{name}")
    app = FastAPI(); app.include_router(router, prefix="/api")
    body = TestClient(app).get("/api/system/check").json()
    by = {i["key"]: i for i in body["items"]}
    assert {"backend", "extension", "claude", "ffmpeg", "output", "data", "disk"} <= set(by)
    assert by["claude"]["ok"] is False and "Claude Code" in by["claude"]["fix"]
    assert by["ffmpeg"]["ok"] is True and by["ffmpeg"]["fix"] == ""
    assert body["ok"] is False
