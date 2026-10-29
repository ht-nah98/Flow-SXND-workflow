"""AI Director v2: idea images, the user's own pictures as references, and the published film."""
import pytest

from agent.db import crud
from agent.director import brain, cut, ingest, pipeline, production, stages_film, store
from tests.unit.director.fake_plans import fake_responses, finish
from tests.unit.director.fixtures import KITCHEN


@pytest.fixture
def world(test_db, tmp_path):
    async def done(ids, poll_s=None, **kw):
        return {i: (await finish(i, "COMPLETED")) or await crud.get_request(i) for i in ids}
    production.set_waiter(done)
    yield tmp_path
    brain.reset_brain(); production.reset_waiter()


def _brain(responses):
    calls = []
    fb = brain.FakeBrain(responses)

    async def spy(role, payload, schema, **kw):
        calls.append((role, payload, kw))
        return await fb(role, payload, schema, **kw)
    brain.set_brain(spy)
    return calls


def _with_images(tmp_path, producer_images, provided=None):
    photo, mood = tmp_path / "1-kitchen.jpg", tmp_path / "2-mood.jpg"
    photo.write_bytes(b"jpg"); mood.write_bytes(b"jpg")
    resp = fake_responses()
    resp["producer"][0] = dict(resp["producer"][0], target_s=99, orientation="VERTICAL", images=[
        {"file": str(photo), "use": "location", "name": KITCHEN, "description": "the user's kitchen"},
        {"file": str(mood), "use": "mood", "description": "warm film look"},
        *producer_images])
    story = resp["writer"][0]
    story["cast"] = [dict(c, provided_image=provided(c, photo, mood) if provided else None) for c in story["cast"]]
    brief = {"text": "love", "target_s": 15, "orientation": "HORIZONTAL",
             "images": [{"file": str(photo), "note": "my kitchen"}, {"file": str(mood), "note": None}]}
    return resp, brief, photo, mood


async def test_producer_reads_the_idea_images_and_the_users_choices_win(world):
    resp, brief, photo, mood = _with_images(world, [{"file": "/etc/passwd", "use": "character", "description": "x"}])
    calls = _brain(resp)
    r = await store.create_run(brief, {})
    r = await pipeline.run_until_blocked(r["id"])
    role, payload, kw = calls[0]
    assert role == "producer" and payload["brief"]["images"][0]["note"] == "my kitchen"
    assert kw == {"tools": ["Read"], "add_dirs": [str(world)], "escalate": False}
    b = r["plan"]["brief"]
    assert (b["target_s"], b["orientation"]) == (15, "HORIZONTAL")          # the form, not the producer
    assert [i["file"] for i in b["images"]] == [str(photo), str(mood)]      # never a file the user did not send


async def test_text_only_idea_gives_the_producer_no_tools(world):
    calls = _brain(fake_responses())
    r = await store.create_run({"text": "love", "target_s": 15}, {})
    await pipeline.run_until_blocked(r["id"])
    assert not calls[0][2].get("tools") and not calls[0][2].get("add_dirs")


async def test_only_non_mood_user_pictures_become_references(world, monkeypatch):
    resp, brief, photo, mood = _with_images(
        world, [], provided=lambda c, photo, mood: str(photo) if c["name"] == KITCHEN else str(mood))
    _brain(resp)
    uploads = []

    async def fake_upload(cid, pid, path):
        uploads.append(path)
        await crud.update_character(cid, media_id="22222222-2222-2222-2222-222222222222")
        return True
    monkeypatch.setattr(ingest, "upload_reference", fake_upload)
    r = await store.create_run(brief, {})
    r = await pipeline.run_until_blocked(r["id"])
    cast = {c["name"]: c["provided_image"] for c in r["plan"]["story"]["cast"]}
    assert cast[KITCHEN] == str(photo) and set(cast.values()) == {str(photo), None}
    assert uploads == [str(photo)]
    assert r["gate"] == "SCRIPT" and r["plan"]["gate_budget"]["SCRIPT"] == {"refs": 2}


async def test_upload_reference_falls_back_when_flow_is_offline(world):
    assert await ingest.upload_reference("c1", "p1", str(world / "missing.jpg")) is False


async def test_publish_puts_the_film_on_the_video(world, monkeypatch):
    _brain(fake_responses())
    film = world / "final.mp4"; film.write_bytes(b"mp4")
    monkeypatch.setattr(stages_film, "_contact_sheets", lambda path, out_dir: [str(path)])

    async def local_clip(scene, ori, dest):
        return film
    monkeypatch.setattr(cut, "local_clip", local_clip)

    async def render(paths, trims, out_path, size, music_path=None, edit=None):
        return str(film)
    monkeypatch.setattr(cut, "render_cut", render)
    monkeypatch.setattr(cut, "probe_duration", lambda p: 15.04)
    monkeypatch.setitem(pipeline.HANDLERS, "RETRO", pipeline._stop_here)
    r = await store.create_run({"text": "love", "target_s": 15}, {})
    for gate in (None, "SCRIPT", "ASSETS"):
        if gate:
            await pipeline.approve(r["id"], gate)
        r = await pipeline.run_until_blocked(r["id"])
    assert r["stage"] == "RETRO"
    v = await crud.get_video(r["plan"]["ids"]["video_id"])
    assert (v["horizontal_url"], v["duration"], v["status"]) == (f"file://{film}", 15.0, "COMPLETED")


async def test_writer_director_and_editor_read_the_users_whole_idea(world):
    calls = _brain(fake_responses())
    idea = "Hai bạn trẻ làm bánh kem. Cảnh 1: cô gái chờ trong bếp; Cảnh 2: anh về muộn."   # short: no source map needed
    r = await store.create_run({"text": idea, "target_s": 15}, {})
    await pipeline.run_until_blocked(r["id"])
    by_role = {role: payload for role, payload, _ in calls}
    assert by_role["writer"]["idea"] == idea and by_role["director"]["idea"] == idea
    assert by_role["editor"]["idea"] == idea
