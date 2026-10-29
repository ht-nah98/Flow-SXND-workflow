"""Canvas 'ask AI' bar (SciCloud sample, 19/10): proposals only for the selected nodes, applied by the user."""
from agent.db import crud
from agent.director import assist, brain, store


async def _scene():
    p = await crud.create_project(name="phim")
    v = await crud.create_video(project_id=p["id"], title="v")
    s = await crud.create_scene(video_id=v["id"], display_order=0, prompt="ông ngồi bên cửa sổ")
    c = await crud.create_character(name="Old Gus", entity_type="character", description="old man")
    return p, s, c


async def test_proposals_stay_on_the_selected_nodes(test_db):
    p, s, c = await _scene()
    seen = []

    async def fake(role, payload, schema, **kw):
        seen.append((role, payload, kw))
        return schema.model_validate({"answer": "Đã tối ưu prompt.", "changes": [
            {"kind": "scene", "id": s["id"], "field": "video_prompt", "value": "References: Old Gus\nShot: wide"},
            {"kind": "scene", "id": "not-selected", "field": "video_prompt", "value": "x"},
            {"kind": "scene", "id": s["id"], "field": "image_prompt", "value": "wrong field for a scene"},
            {"kind": "character", "id": c["id"], "field": "description", "value": "not selected either"}]})
    brain.set_brain(fake)
    try:
        out = await assist.ask(p["id"], "tối ưu prompt video", [{"kind": "scene", "id": s["id"]}], model="opus")
    finally:
        brain.reset_brain()
    role, payload, kw = seen[0]
    assert role == "assistant" and kw["model"] == "opus"
    assert payload["targets"][0]["prompt"] == "ông ngồi bên cửa sổ" and payload["film"] == {}
    assert [(c["id"], c["field"]) for c in out["changes"]] == [(s["id"], "video_prompt")]


async def test_the_film_context_comes_from_the_latest_script(test_db):
    p, s, _ = await _scene()
    r = await store.create_run({"text": "x"}, {})
    await store.update_run(r["id"], project_id=p["id"])
    await store.update_run(r["id"], plan={"brief": {"language": "en"}, "story": {"message": "love stays", "synopsis": "s"}})
    film = await assist._film(p["id"])
    assert film["language"] == "en" and film["message"] == "love stays"


def test_the_assistant_reads_the_prompt_rules():
    from agent.director.brain import _system_prompt
    text = _system_prompt("assistant", "")
    assert "# Shot-writing rules" in text and "## Playbook: 03-prompt-video.md" in text


async def test_scenes_named_by_number_are_targets_and_neighbours_are_context(test_db):
    """19/10: "cảnh 7 … cảnh 8" got the answer "select scenes 7 and 8 and send again"."""
    p = await crud.create_project(name="phim")
    v = await crud.create_video(project_id=p["id"], title="v")
    ss = [await crud.create_scene(video_id=v["id"], display_order=i, prompt=f"shot {i + 1}") for i in range(10)]
    seen = []

    async def fake(role, payload, schema, **kw):
        seen.append(payload)
        return schema.model_validate({"answer": "ok", "changes": [
            {"kind": "scene", "id": ss[7]["id"], "field": "video_prompt", "value": "x"}]})
    brain.set_brain(fake)
    try:
        out = await assist.ask(p["id"], "Sao cảnh 7 đang nhảy múa thì cảnh 8 lại nghe điện thoại?", [])
    finally:
        brain.reset_brain()
    assert [t["order"] for t in seen[0]["targets"]] == [7, 8]
    assert [n["order"] for n in seen[0]["neighbours"]] == [6, 9]
    assert [c["id"] for c in out["changes"]] == [ss[7]["id"]]
