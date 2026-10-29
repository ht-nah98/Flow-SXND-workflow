"""GENERATE_VIDEO_REFS must honour the project's video_model_family.

Veo r2v takes at most 3 refs and the worker drops locations; Omni Flash takes
up to 7 ingredients (locations included) and a per-scene duration. The test
drives the same entry point the worker uses (ops.generate_scene_video_refs,
agent/worker/processor.py) with a mocked Flow client — no network.
"""
from unittest.mock import AsyncMock, MagicMock

from agent.db import crud
from agent.sdk.services import flow_provider
from agent.sdk.services.operations import OperationService

UUIDS = [f"{i}{i}{i}{i}{i}{i}{i}{i}-0000-0000-0000-000000000000" for i in range(1, 10)]
_DONE = {"data": {"operations": [{"operation": {"name": "op1"},
                                  "status": "MEDIA_GENERATION_STATUS_SUCCESSFUL"}]}}


def _ops():
    client = MagicMock()
    client.connected = True
    client.generate_video_from_references = AsyncMock(return_value=_DONE)
    return OperationService(flow_client=client, repo=None), client


async def _scene_with_entities(project, kinds, **scene_kw):
    v = await crud.create_video(project_id=project["id"], title="V", orientation="HORIZONTAL")
    names = []
    for i, kind in enumerate(kinds):
        c = await crud.create_character(name=f"E{i}", entity_type=kind, media_id=UUIDS[i])
        await crud.link_character_to_project(project["id"], c["id"])
        names.append(c["name"])
    s = await crud.create_scene(video_id=v["id"], display_order=0, prompt="p", video_prompt="vp",
                                character_names=names)
    if scene_kw:
        await crud.update_scene(s["id"], **scene_kw)
    scene = await crud.get_scene(s["id"])
    scene["_project_id"] = project["id"]
    return scene


async def test_omni_project_sends_up_to_7_refs_including_locations(test_db, monkeypatch):
    p = await crud.create_project(name="P", video_model_family="omni_flash")
    scene = await _scene_with_entities(
        p, ["character"] * 3 + ["location"] * 2 + ["visual_asset"] * 3, duration=6)
    omni = AsyncMock(return_value=_DONE)
    monkeypatch.setattr(flow_provider, "generate_omni_flash_video", omni, raising=False)
    ops, client = _ops()

    result = await ops.generate_scene_video_refs(scene, "HORIZONTAL", provider="flow")

    assert "error" not in result
    client.generate_video_from_references.assert_not_called()
    kw = omni.await_args.kwargs
    refs = kw["reference_media_ids"]
    assert len(refs) == 7                                  # 8 candidates, capped at 7
    assert set(UUIDS[5:8]) <= set(refs)                    # visual_assets first
    assert set(UUIDS[0:3]) <= set(refs)                    # then characters
    assert {UUIDS[3], UUIDS[4]} & set(refs)                # a location made it in
    assert kw["duration_s"] == 6
    assert kw["resolution"] == "720p"
    assert kw["aspect_ratio"] == "VIDEO_ASPECT_RATIO_LANDSCAPE"
    assert kw["project_id"] == p["id"] and kw["scene_id"] == scene["id"]


async def test_veo_project_keeps_three_ref_cap_and_no_locations(test_db, monkeypatch):
    p = await crud.create_project(name="P")  # veo
    scene = await _scene_with_entities(p, ["location"] + ["character"] * 4)
    omni = AsyncMock(return_value=_DONE)
    monkeypatch.setattr(flow_provider, "generate_omni_flash_video", omni, raising=False)
    ops, client = _ops()

    await ops.generate_scene_video_refs(scene, "HORIZONTAL", provider="flow")

    omni.assert_not_called()
    refs = client.generate_video_from_references.await_args.kwargs["reference_media_ids"]
    assert len(refs) == 3
    assert UUIDS[0] not in refs                            # location still excluded on Veo


async def test_r2v_request_does_not_wait_for_a_scene_image(test_db):
    """r2v renders from references; deferring it until a keyframe exists starves it forever."""
    from agent.worker.processor import _prerequisites_met
    p = await crud.create_project(name="P", video_model_family="omni_flash")
    v = await crud.create_video(project_id=p["id"], title="V", orientation="HORIZONTAL")
    s = await crud.create_scene(video_id=v["id"], display_order=0, prompt="p")
    refs = {"type": "GENERATE_VIDEO_REFS", "scene_id": s["id"]}
    i2v = {"type": "GENERATE_VIDEO", "scene_id": s["id"]}
    assert await _prerequisites_met(refs, "HORIZONTAL") is True
    assert await _prerequisites_met(i2v, "HORIZONTAL") is False


def test_character_references_are_landscape_sheets():
    """Character refs are 3-view character sheets (close-up, front, back), which need a wide frame."""
    from agent.sdk.services.operations import _reference_aspect_ratio
    assert _reference_aspect_ratio("character") == "IMAGE_ASPECT_RATIO_LANDSCAPE"
    assert _reference_aspect_ratio("location") == "IMAGE_ASPECT_RATIO_LANDSCAPE"
    assert _reference_aspect_ratio("visual_asset") == "IMAGE_ASPECT_RATIO_PORTRAIT"


async def test_location_reference_follows_the_film_orientation(test_db):
    from agent.db import crud
    from agent.sdk.services.operations import _location_aspect_ratio
    p = await crud.create_project(name="p")
    assert await _location_aspect_ratio(p["id"], "VERTICAL") == "IMAGE_ASPECT_RATIO_PORTRAIT"
    assert await _location_aspect_ratio(p["id"], "HORIZONTAL") == "IMAGE_ASPECT_RATIO_LANDSCAPE"
    assert await _location_aspect_ratio(p["id"], None) == "IMAGE_ASPECT_RATIO_LANDSCAPE"   # no video yet
    await crud.create_video(project_id=p["id"], title="v", orientation="VERTICAL")
    assert await _location_aspect_ratio(p["id"], None) == "IMAGE_ASPECT_RATIO_PORTRAIT"    # canvas regen
