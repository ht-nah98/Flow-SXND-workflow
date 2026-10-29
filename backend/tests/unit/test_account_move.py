"""Account rotation step 4 (22/10): Google flagged Hoang mid-film — move the film to another account without credit."""
import json

import pytest

from agent.db import crud
from agent.services import account_move
from agent.services import flow_client as fc
from agent.services.flow_client import CURRENT_ACCOUNT, FlowClient

PID = "11111111-1111-4111-8111-111111111111"
NEW = "22222222-2222-4222-8222-222222222222"


class RecWS:
    def __init__(self, client):
        self.client, self.params = client, []

    async def send(self, raw):
        msg = json.loads(raw)
        self.params.append(msg["params"])
        await self.client.handle_message({"id": msg["id"], "ok": True}, self)


async def test_a_moved_film_is_sent_under_its_new_flow_project():
    c = FlowClient()
    ws = RecWS(c)
    c.set_extension(ws)
    fc.PROJECT_ALIASES[PID] = NEW
    try:
        await c._send("batch_rpc", {"rpcid": "x", "freq": f'[["{PID}",1]]', "n": 3}, timeout=2)
    finally:
        fc.PROJECT_ALIASES.pop(PID)
    assert ws.params[0] == {"rpcid": "x", "freq": f'[["{NEW}",1]]', "n": 3}


async def test_googles_unusual_activity_block_holds_only_the_blocked_account():
    c = FlowClient()
    t = CURRENT_ACCOUNT.set("hoang@gmail.com")
    try:
        c._generation_unusual_until = 10**12
        assert c.generation_cooldown_remaining() > 0
    finally:
        CURRENT_ACCOUNT.reset(t)
    t = CURRENT_ACCOUNT.set("olya@gmail.com")
    try:
        assert c.generation_cooldown_remaining() == 0
    finally:
        CURRENT_ACCOUNT.reset(t)
    assert list(c.generation_guard_status["cooldown_by_account"]) == ["hoang@gmail.com"]


@pytest.fixture
async def film(test_db, monkeypatch):
    await crud.create_project(name="Old Walt", id=PID)
    await crud.update_project(PID, flow_account="hoang@gmail.com")
    done = await crud.create_character(name="Young Walt", media_id="old-media", reference_image_url="https://x/young.jpg")
    todo = await crud.create_character(name="Old Walt")
    for ch in (done, todo):
        await crud.link_character_to_project(PID, ch["id"])
    req = await crud.create_request(req_type="GENERATE_CHARACTER_IMAGE", project_id=PID, character_id=todo["id"])
    # the worker keeps picking it up while Hoang is offline: PROCESSING, yet nothing is in flight
    await crud.update_request(req["id"], status="PROCESSING", retry_count=2, error_message="ACCOUNT_NOT_CONNECTED")

    class Client:
        uploads, created_in = [], []

        def connected_accounts(self):
            return {"olya@gmail.com": 1}

        async def create_project(self, title, tool_name="PINHOLE"):
            self.created_in.append(CURRENT_ACCOUNT.get())
            return {"data": {"projectId": NEW}}

        async def upload_image(self, b64, mime_type, project_id, file_name):
            self.uploads.append((project_id, CURRENT_ACCOUNT.get()))
            return {"_mediaId": "new-media"}

    client = Client()
    monkeypatch.setattr(fc, "get_flow_client", lambda: client)

    async def download(url):
        return b"jpeg", "image/jpeg"
    monkeypatch.setattr(account_move, "_download", download)
    yield client, done, req
    fc.PROJECT_ALIASES.pop(PID, None)


async def test_a_film_moves_to_another_account_with_its_pictures_and_queue(film):
    client, done, req = film
    out = await account_move.move_project(PID, "olya@gmail.com")
    assert out["pictures"] == ["Young Walt"] and client.created_in == ["olya@gmail.com"]
    assert client.uploads == [(NEW, "olya@gmail.com")]
    assert (await crud.get_character(done["id"]))["media_id"] == "new-media"
    p = await crud.get_project(PID)
    assert (p["flow_account"], p["flow_project_alias"]) == ("olya@gmail.com", NEW) and fc.PROJECT_ALIASES[PID] == NEW
    q = await crud.get_request(req["id"])
    assert q["status"] == "PROCESSING" and q["retry_count"] == 0       # Hoang's blocks do not count against Olya


async def test_nothing_moves_when_a_picture_cannot_be_fetched_or_the_account_is_offline(film, monkeypatch):
    client, done, _ = film
    with pytest.raises(ValueError, match="chưa kết nối"):
        await account_move.move_project(PID, "linda@gmail.com")

    async def broken(url):
        raise ValueError("HTTP 403")
    monkeypatch.setattr(account_move, "_download", broken)
    with pytest.raises(ValueError, match="Young Walt"):
        await account_move.move_project(PID, "olya@gmail.com")
    assert client.created_in == [] and (await crud.get_project(PID))["flow_account"] == "hoang@gmail.com"


async def test_a_request_inside_google_for_the_old_account_blocks_the_move(film, monkeypatch):
    client, _, _ = film
    monkeypatch.setattr(type(client), "connected_accounts", lambda self: {"olya@gmail.com": 1, "hoang@gmail.com": 1})
    with pytest.raises(ValueError, match="đợi nó xong"):
        await account_move.move_project(PID, "olya@gmail.com")


async def test_a_film_whose_flow_project_is_missing_gets_a_new_one_in_the_same_account(film, monkeypatch):
    """23/10 Blue Morning: the Flow project was made in another profile, so the film's own account had no such project
    ("Không tìm thấy dự án") and every clip came back NO_MEDIA_CREATED. Its pictures and pinned end frames were made
    in the right account, so a repair only needs a new project there — nothing re-uploaded, no pin dropped."""
    client, done, req = film
    await crud.update_project(PID, flow_account="olya@gmail.com")
    await crud.update_request(req["id"], status="FAILED")      # the refused clips are over before the repair
    v = await crud.create_video(project_id=PID, title="Blue Morning")
    s = await crud.create_scene(v["id"], 0, "SH01")
    await crud.update_scene(s["id"], horizontal_end_scene_media_id="pinned-keyframe")
    with pytest.raises(ValueError, match="đã ở tài khoản"):
        await account_move.move_project(PID, "olya@gmail.com")
    out = await account_move.move_project(PID, "olya@gmail.com", repair=True)
    assert out["flow_project_id"] == NEW and client.created_in == ["olya@gmail.com"] and client.uploads == []
    assert (await crud.get_character(done["id"]))["media_id"] == "old-media"
    assert (await crud.get_scene(s["id"]))["horizontal_end_scene_media_id"] == "pinned-keyframe"
    assert (await crud.get_project(PID))["flow_project_alias"] == NEW and fc.PROJECT_ALIASES[PID] == NEW
