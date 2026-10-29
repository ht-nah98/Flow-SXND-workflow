import asyncio

from agent.db import crud
from agent.director import store


async def test_run_round_trip_and_json_columns(test_db):
    r = await store.create_run({"text": "love story", "target_s": 30}, {"refs": 4})
    assert r["status"] == "RUNNING" and r["stage"] == "BRIEF"
    await store.update_run(r["id"], plan={"brief": {"logline": "x"}}, stage="STORY")
    got = await store.get_run(r["id"])
    assert got["plan"]["brief"]["logline"] == "x" and got["brief"]["target_s"] == 30


async def test_reserve_is_atomic_and_capped(test_db):
    r = await store.create_run({"text": "t", "target_s": 30}, {"videos": 3})
    results = await asyncio.gather(*[store.reserve(r["id"], "videos") for _ in range(5)])
    assert results.count(True) == 3
    assert (await store.get_run(r["id"]))["spent"]["videos"] == 3
    assert await store.reserve(r["id"], "images") is False  # no budget for that kind


async def test_steps_and_lessons(test_db):
    r = await store.create_run({"text": "t", "target_s": 30}, {})
    await store.add_step(r["id"], "BRIEF", 1, {"a": 1}, {"b": 2}, [], "OK", 10)
    assert (await store.list_steps(r["id"]))[0]["output"] == {"b": 2}
    l = await store.add_lesson("omni_flash", "≤2 actions", "seed", "ACTIVE", id="seed-1")
    await store.update_lesson(l["id"], status="RETIRED")
    assert await store.list_lessons(status="ACTIVE") == []


async def test_scene_has_director_columns(test_db):
    p = await crud.create_project(name="P")
    v = await crud.create_video(project_id=p["id"], title="V")
    s = await crud.create_scene(video_id=v["id"], display_order=0, prompt="x")
    s = await crud.update_scene(s["id"], video_mode="r2v", shot_spec='{"idea":"x"}')
    assert s["video_mode"] == "r2v"


async def test_update_whitelist_rejects_credit_and_unknown_keys(test_db):
    import pytest
    r = await store.create_run({"text": "t", "target_s": 30}, {"videos": 1})
    for bad in ({"spent": {"videos": 0}}, {"budget": {"videos": 99}}, {"status=1; --": 1}):
        with pytest.raises(ValueError):
            await store.update_run(r["id"], **bad)
    l = await store.add_lesson("s", "r", "seed", "ACTIVE")
    with pytest.raises(ValueError):
        await store.update_lesson(l["id"], id="x")


async def test_add_budget_and_reserve_guard(test_db):
    import pytest
    r = await store.create_run({"text": "t", "target_s": 30}, {"videos": 1})
    got = await store.add_budget(r["id"], {"videos": 2, "images": 1})
    assert got["budget"] == {"videos": 3, "images": 1}
    with pytest.raises(ValueError):
        await store.add_budget(r["id"], {"videos": -1})
    with pytest.raises(ValueError):
        await store.add_budget(r["id"], {"videos": 1.5})
    assert await store.reserve(r["id"], "videos", 0) is False
    assert (await store.get_run(r["id"]))["spent"] == {}
