"""Directive B13 (22/10, playbook 10): keyframe mode — stills per shot from the cast pictures, a gate to look at them,
then i2v clips that end on the next still when the next shot joins, cut by use_s."""
from agent.db import crud
from agent.director import cut, pipeline, store
from agent.director.schemas import Shot
from tests.unit.director.test_ingest_gates import at_assets, world  # noqa: F401 — the fixture

JOINS = ["cut", "occlusion", "cut"]


async def keyframe_run_at_assets():
    r = await at_assets()
    plan = r["plan"]
    plan["brief"]["film_mode"] = "keyframe"
    for s, join in zip(sorted(plan["shotlist"]["shots"], key=lambda x: x["order"]), JOINS):
        s.update(mode="i2v", duration_s=4, join_in=join, use_s=3.0, keyframe=f"still of {s['id']}")
    return await store.update_run(r["id"], plan=plan)


async def test_a_keyframe_film_makes_its_stills_and_waits_before_any_video(world):  # noqa: F811
    r = await keyframe_run_at_assets()
    r = await pipeline.approve(r["id"], "ASSETS", budget={"videos": 3, "regens": 1, "images": 3})
    assert r["stage"] == "KEYFRAMES"
    r = await pipeline.run_until_blocked(r["id"])
    assert (r["status"], r["gate"]) == ("WAITING_GATE", "KEYFRAMES")
    reqs = await crud.list_requests(project_id=r["plan"]["ids"]["project_id"])
    assert sorted(q["type"] for q in reqs if q["type"].startswith("GENERATE_") and "CHARACTER" not in q["type"]) \
        == ["GENERATE_IMAGE"] * 3                                          # stills only, no video yet


async def test_each_clip_ends_on_the_next_still_when_the_next_shot_joins(world, monkeypatch):  # noqa: F811
    monkeypatch.setitem(pipeline.HANDLERS, "QC", pipeline._stop_here)
    r = await keyframe_run_at_assets()
    await pipeline.approve(r["id"], "ASSETS", budget={"videos": 3, "regens": 1, "images": 3})
    r = await pipeline.run_until_blocked(r["id"])
    r = await pipeline.approve(r["id"], "KEYFRAMES")
    r = await pipeline.run_until_blocked(r["id"])
    ids = r["plan"]["ids"]
    order = [s["id"] for s in sorted(r["plan"]["shotlist"]["shots"], key=lambda x: x["order"])]
    scenes = [await crud.get_scene(ids["scenes"][sid]) for sid in order]
    assert scenes[0]["horizontal_end_scene_media_id"] == scenes[1]["horizontal_image_media_id"]   # shot 2 joins
    assert not scenes[1]["horizontal_end_scene_media_id"] and not scenes[2]["horizontal_end_scene_media_id"]
    vids = [q for q in await crud.list_requests(project_id=ids["project_id"]) if "VIDEO" in q["type"]]
    assert {q["type"] for q in vids} == {"GENERATE_VIDEO"} and len(vids) == 3


async def test_the_keyframe_gate_needs_every_still(world):  # noqa: F811
    r = await keyframe_run_at_assets()
    await pipeline.approve(r["id"], "ASSETS", budget={"videos": 3, "regens": 1, "images": 3})
    r = await pipeline.run_until_blocked(r["id"])
    first = r["plan"]["ids"]["scenes"][sorted(r["plan"]["shotlist"]["shots"], key=lambda x: x["order"])[0]["id"]]
    await crud.update_scene(first, horizontal_image_media_id="")
    try:
        await pipeline.approve(r["id"], "KEYFRAMES")
        raise AssertionError("approved without a still")
    except ValueError as e:
        assert "cảnh 1" in str(e)


def _s(i, join, use=3.0, dur=4):
    return Shot(id=f"s{i}", beat_id="b1", order=i, duration_s=dur, idea="x", story_beat="x", cast=[], mode="i2v",
                mode_reason="x", actions=[], commands=[], stable_open_s=0, join_in=join, use_s=use)


def test_the_edit_keeps_use_s_against_the_pinned_stills():
    shots = [_s(1, "cut", 2.0), _s(2, "occlusion", 4.0), _s(3, "action", 2.5, 6), _s(4, "cut", 3.0, 6)]
    # s1 → s2 joined: s1 ends on its last frame; s2 joined both ends: whole; s3 joined in only; s4 alone: centred
    assert cut.keyframe_trims(shots) == [[2.0, 4.0], [0.0, 4.0], [0.0, 2.5], [1.5, 4.5]]
    edit = {"look": None, "clips": [{"shot_id": s.id, "fx": [], "transition_out": "nhay-trang"} for s in shots]}
    assert [c["transition_out"] for c in cut.keyframe_edit(edit, shots)["clips"]] == ["cat", "cat", "nhay-trang", "nhay-trang"]


async def test_run_all_still_stops_to_look_at_the_stills(world):  # noqa: F811
    """23/10 Blue Morning: "⏩ Chạy toàn bộ" sent 21 videos straight after the stills — nobody had seen them, and a
    character who looked like a celebrity cost a round of refused clips. The stills are the cheap step to check."""
    r = await keyframe_run_at_assets()
    plan = r["plan"]
    plan["mode"] = "auto"
    await store.update_run(r["id"], plan=plan)
    r = await pipeline.approve(r["id"], "ASSETS", budget={"videos": 3, "regens": 1, "images": 3})
    r = await pipeline.run_until_blocked(r["id"])
    assert (r["status"], r["gate"]) == ("WAITING_GATE", "KEYFRAMES")
    assert not [q for q in await crud.list_requests(project_id=r["plan"]["ids"]["project_id"]) if "VIDEO" in q["type"]]


async def test_the_script_gate_total_counts_the_keyframe_stills(world):  # noqa: F811
    """23/10 Blue Morning: 21 stills were granted with "Chạy toàn bộ" but missing from the shown ≈417 credits."""
    r = await keyframe_run_at_assets()
    cut_film = {"plan": {**r["plan"], "brief": {**r["plan"]["brief"], "film_mode": "cut"}}}
    p, plain = pipeline.script_payload(r, 2, 1), pipeline.script_payload(cut_film, 2, 1)
    assert p["keyframes"] == 3 and p["total_credits_est"] == plain["total_credits_est"] + p["keyframe_credits_est"] > 0
    assert "keyframes" not in plain
