"""Keyframe mode (B13, 22/10): re-making a still (Leo Marsh K8 was blocked) must move the end-frame pin of the clip
before it, or that clip's next video lands on a picture that is no longer the next shot's first frame."""
from agent.db import crud
from agent.worker import processor


async def test_a_remade_still_carries_the_end_pin_with_it(test_db):
    p = await crud.create_project(name="Leo")
    v = await crud.create_video(project_id=p["id"], title="Leo")
    s7 = await crud.create_scene(video_id=v["id"], display_order=6, prompt="7")
    s8 = await crud.create_scene(video_id=v["id"], display_order=7, prompt="8")
    await crud.update_scene(s8["id"], horizontal_image_media_id="old-k8")
    await crud.update_scene(s7["id"], horizontal_end_scene_media_id="old-k8")
    req = {"scene_id": s8["id"], "video_id": v["id"]}
    assert await processor._scene_image_media(s8["id"], "HORIZONTAL") == "old-k8"
    await processor._repin_end_frames(req, "HORIZONTAL", "old-k8", "new-k8")
    assert (await crud.get_scene(s7["id"]))["horizontal_end_scene_media_id"] == "new-k8"
    assert (await crud.get_scene(s8["id"]))["horizontal_end_scene_media_id"] in (None, "")
