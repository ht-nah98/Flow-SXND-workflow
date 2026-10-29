import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api.canvas import router as canvas_router
from agent.db import crud


@pytest.fixture
def api(test_db):
    app = FastAPI()
    app.include_router(canvas_router, prefix="/api")
    return TestClient(app)


@pytest.fixture
async def project(test_db):
    p = await crud.create_project(name="P")
    v = await crud.create_video(project_id=p["id"], title="V")
    c = await crud.create_character(name="Lan", entity_type="character")
    await crud.link_character_to_project(p["id"], c["id"])
    s = await crud.create_scene(video_id=v["id"], display_order=0, prompt="x")
    return {"pid": p["id"], "vid": v["id"], "cid": c["id"], "sid": s["id"]}


async def test_upsert_and_get(api, project):
    pid = project["pid"]
    r = api.put(f"/api/projects/{pid}/canvas/nodes/note:n1", json={"x": 10, "y": 20, "data": {"text": "hi"}})
    assert r.status_code == 200
    assert r.json()["data"] == {"text": "hi"}
    r = api.put(f"/api/projects/{pid}/canvas/nodes/note:n1", json={"x": 11, "y": 21})
    assert r.json()["x"] == 11
    assert r.json()["data"] == {"text": "hi"}  # data kept when omitted
    nodes = api.get(f"/api/projects/{pid}/canvas").json()["nodes"]
    assert [n["node_key"] for n in nodes] == ["note:n1"]


async def test_bulk_upsert(api, project):
    pid, cid, sid, vid = project["pid"], project["cid"], project["sid"], project["vid"]
    body = {"nodes": [
        {"node_key": f"character:{cid}", "x": 0, "y": 0},
        {"node_key": f"scene:{sid}", "x": 300, "y": 0},
        {"node_key": f"video:{vid}", "x": 600, "y": 0},
        {"node_key": f"final:{vid}", "x": 900, "y": 0},
    ]}
    r = api.put(f"/api/projects/{pid}/canvas/nodes", json=body)
    assert r.status_code == 200
    assert len(api.get(f"/api/projects/{pid}/canvas").json()["nodes"]) == 4


async def test_invalid_node_key_rejected(api, project):
    r = api.put(f"/api/projects/{project['pid']}/canvas/nodes/bogus:1", json={"x": 0, "y": 0})
    assert r.status_code == 422


async def test_orphans_pruned_on_read(api, project):
    pid, sid = project["pid"], project["sid"]
    api.put(f"/api/projects/{pid}/canvas/nodes/scene:{sid}", json={"x": 0, "y": 0})
    await crud.delete_scene(sid)
    assert api.get(f"/api/projects/{pid}/canvas").json()["nodes"] == []


async def test_delete(api, project):
    pid = project["pid"]
    api.put(f"/api/projects/{pid}/canvas/nodes/note:n1", json={"x": 0, "y": 0})
    assert api.delete(f"/api/projects/{pid}/canvas/nodes/note:n1").json() == {"ok": True}
    assert api.get(f"/api/projects/{pid}/canvas").json()["nodes"] == []


async def test_final_node_pruned_with_its_video(api, project):
    pid, vid = project["pid"], project["vid"]
    api.put(f"/api/projects/{pid}/canvas/nodes/final:{vid}", json={"x": 0, "y": 0})
    assert len(api.get(f"/api/projects/{pid}/canvas").json()["nodes"]) == 1
    await crud.delete_video(vid)
    assert api.get(f"/api/projects/{pid}/canvas").json()["nodes"] == []


async def test_script_node_kept_only_for_its_project(api, project):
    pid = project["pid"]
    api.put(f"/api/projects/{pid}/canvas/nodes/script:{pid}", json={"x": 0, "y": 0})
    api.put(f"/api/projects/{pid}/canvas/nodes/script:other-project", json={"x": 0, "y": 0})
    assert [n["node_key"] for n in api.get(f"/api/projects/{pid}/canvas").json()["nodes"]] == [f"script:{pid}"]


async def test_idea_node_kept_only_for_a_run_of_this_project(api, project):
    from agent.director import store
    pid = project["pid"]
    run = await store.create_run({"text": "idea"}, {})
    other = await store.create_run({"text": "other"}, {})
    await store.update_run(run["id"], project_id=pid)
    for rid in (run["id"], other["id"]):
        api.put(f"/api/projects/{pid}/canvas/nodes/idea:{rid}", json={"x": 0, "y": 0})
    assert [n["node_key"] for n in api.get(f"/api/projects/{pid}/canvas").json()["nodes"]] == [f"idea:{run['id']}"]


async def test_review_node_saves_and_is_kept_only_for_a_run_of_this_project(api, project):
    """Agent Review (21/10): the review box's place must persist — an unknown key kind used to be refused (422)."""
    from agent.director import store
    pid = project["pid"]
    run = await store.create_run({"text": "idea"}, {})
    other = await store.create_run({"text": "other"}, {})
    await store.update_run(run["id"], project_id=pid)
    for rid in (run["id"], other["id"]):
        assert api.put(f"/api/projects/{pid}/canvas/nodes/review:{rid}", json={"x": 0, "y": 0}).status_code == 200
    assert [n["node_key"] for n in api.get(f"/api/projects/{pid}/canvas").json()["nodes"]] == [f"review:{run['id']}"]
