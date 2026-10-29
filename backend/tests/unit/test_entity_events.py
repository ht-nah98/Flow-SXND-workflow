import pytest

from agent.services.entity_events import classify_mutation


@pytest.mark.parametrize("method,path,expected", [
    ("PATCH", "/api/scenes/s1", {"entity": "scene", "id": "s1", "project_id": None, "action": "updated"}),
    ("POST", "/api/scenes", {"entity": "scene", "id": None, "project_id": None, "action": "created"}),
    ("DELETE", "/api/characters/c1", {"entity": "character", "id": "c1", "project_id": None, "action": "deleted"}),
    ("POST", "/api/characters/c1/restore", {"entity": "character", "id": "c1", "project_id": None, "action": "updated"}),
    ("POST", "/api/projects/p1/characters/c1", {"entity": "project", "id": "p1", "project_id": "p1", "action": "updated"}),
    ("PUT", "/api/projects/p1/canvas/nodes/note:1", {"entity": "canvas", "id": "p1", "project_id": "p1", "action": "updated"}),
    ("POST", "/api/videos/v1/concat", {"entity": "video", "id": "v1", "project_id": None, "action": "updated"}),
])
def test_classify(method, path, expected):
    assert classify_mutation(method, path) == expected


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/scenes/s1"),
    ("POST", "/api/requests/batch"),
    ("POST", "/api/flow/generate-image"),
    ("GET", "/health"),
    ("POST", "/api/projects/p1/export"),  # downloads/zips media, doesn't mutate the project
])
def test_ignored(method, path):
    assert classify_mutation(method, path) is None
