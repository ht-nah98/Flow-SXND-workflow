"""Account rotation, step 1 (19/10): know which Google account each extension connection is signed in to."""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api.flow import router
from agent.db import account_crud
from agent.services.flow_client import FlowClient


class FakeWS:
    def __init__(self, client, reply):
        self.client, self.reply, self.sent = client, reply, []

    async def send(self, raw):
        msg = json.loads(raw)
        self.sent.append(msg)
        if msg.get("method") == "get_account":
            await self.client.handle_message({"id": msg["id"], "result": self.reply}, self)


async def test_each_connection_reports_its_account(test_db):
    c = FlowClient()
    olya = FakeWS(c, {"email": "Olya@gmail.com", "name": "Olya Test"})
    old = FakeWS(c, {"error": "unknown method"})                 # extension < 0.6.0
    c.set_extension(olya); c.set_extension(old)
    assert await c.identify(olya) == "olya@gmail.com"
    assert await c.identify(old) is None
    assert c.connected_accounts() == {"olya@gmail.com": 1, "?": 1}
    row = await account_crud.get("olya@gmail.com")
    assert row["name"] == "Olya Test" and row["status"] == "ACTIVE"


async def test_accounts_keep_their_rotation_order_and_can_be_edited(test_db):
    await account_crud.seen("a@gmail.com"); await account_crud.seen("b@gmail.com"); await account_crud.seen("a@gmail.com")
    assert [(a["email"], a["priority"]) for a in await account_crud.list_all()] == [("a@gmail.com", 0), ("b@gmail.com", 1)]
    app = FastAPI(); app.include_router(router, prefix="/api")
    api = TestClient(app)
    got = api.patch("/api/flow/accounts/b@gmail.com", json={"label": "Phụ", "status": "EXHAUSTED"}).json()
    assert (got["label"], got["status"]) == ("Phụ", "EXHAUSTED")
    assert api.patch("/api/flow/accounts/nobody@gmail.com", json={"label": "x"}).status_code == 404
    assert api.patch("/api/flow/accounts/b@gmail.com", json={"status": "BROKEN"}).status_code == 422


class EchoWS:
    """A profile that answers every request with its own name."""
    def __init__(self, client, name, error=None):
        self.client, self.name, self.error, self.calls = client, name, error, 0

    async def send(self, raw):
        msg = json.loads(raw)
        self.calls += 1
        result = {"error": self.error} if self.error else {"by": self.name}
        await self.client.handle_message({"id": msg["id"], **result}, self)


def _two_accounts():
    c = FlowClient()
    a, b = EchoWS(c, "A"), EchoWS(c, "B")
    c.set_extension(a); c.set_extension(b)
    c._extensions[a]["account"], c._extensions[b]["account"] = "a@gmail.com", "b@gmail.com"
    return c, a, b


async def test_a_film_only_talks_to_its_own_account():
    from agent.services.flow_client import CURRENT_ACCOUNT
    c, a, b = _two_accounts()
    token = CURRENT_ACCOUNT.set("b@gmail.com")
    try:
        assert (await c._send("anything", {}, timeout=2))["by"] == "B"
        assert c.last_account == "b@gmail.com" and a.calls == 0
    finally:
        CURRENT_ACCOUNT.reset(token)


async def test_out_of_quota_never_fails_over_to_another_account():
    """16/10: a quota error used to retry on any other profile — another account, where the film's media do not exist."""
    from agent.services.flow_client import CURRENT_ACCOUNT
    c = FlowClient()
    a = EchoWS(c, "A", error="PUBLIC_ERROR_USER_QUOTA_REACHED")
    b = EchoWS(c, "B")
    c.set_extension(a); c.set_extension(b)
    c._extensions[a]["account"], c._extensions[b]["account"] = "a@gmail.com", "b@gmail.com"
    token = CURRENT_ACCOUNT.set("a@gmail.com")
    try:
        res = await c._send("generate", {}, timeout=2)
    finally:
        CURRENT_ACCOUNT.reset(token)
    assert "QUOTA" in res["error"] and b.calls == 0


async def test_a_film_whose_account_is_offline_waits_with_a_clear_message():
    from agent.services.flow_client import ACCOUNT_NOT_CONNECTED, CURRENT_ACCOUNT
    c, a, b = _two_accounts()
    token = CURRENT_ACCOUNT.set("olya@gmail.com")
    try:
        res = await c._send("generate", {}, timeout=2)
    finally:
        CURRENT_ACCOUNT.reset(token)
    assert res["error"].startswith(ACCOUNT_NOT_CONNECTED) and "olya@gmail.com" in res["error"]
    assert a.calls == b.calls == 0


async def test_the_worker_runs_each_request_in_its_projects_account(test_db, monkeypatch):
    from agent.db import crud
    from agent.services.flow_client import CURRENT_ACCOUNT
    from agent.worker import processor
    p = await crud.create_project(name="phim")
    await crud.update_project(p["id"], flow_account="b@gmail.com")
    seen = {}

    async def fake(req, deferred=None, retry_after=None):
        seen["account"] = CURRENT_ACCOUNT.get()
    monkeypatch.setattr(processor, "_process_request", fake)
    await processor._process_one({"id": "r1", "type": "GENERATE_VIDEO_REFS", "project_id": p["id"]})
    assert seen["account"] == "b@gmail.com" and CURRENT_ACCOUNT.get() is None


# --- Step 3: an out-of-credit account holds its films instead of failing them ---

async def test_quota_error_marks_the_account_and_keeps_the_request_queued(test_db):
    from agent.db import crud
    from agent.services.flow_client import CURRENT_ACCOUNT
    from agent.worker import processor
    p = await crud.create_project(name="phim")
    req = await crud.create_request(req_type="GENERATE_VIDEO_REFS", project_id=p["id"])
    token = CURRENT_ACCOUNT.set("a@gmail.com")
    try:
        await processor._handle_failure(req["id"], req, {"error": "PUBLIC_ERROR_USER_QUOTA_REACHED"})
    finally:
        CURRENT_ACCOUNT.reset(token)
    row = await crud.get_request(req["id"])
    assert row["status"] == "PENDING" and row["retry_count"] == 0
    assert row["error_message"].startswith("ACCOUNT_EXHAUSTED")
    acc = await account_crud.get("a@gmail.com")
    assert acc["status"] == "EXHAUSTED" and acc["exhausted_at"] and "QUOTA" in acc["last_error"]


async def test_the_worker_holds_only_the_exhausted_accounts_films(test_db):
    from agent.db import crud
    from agent.worker import processor
    a = await crud.create_project(name="A"); b = await crud.create_project(name="B")
    await crud.update_project(a["id"], flow_account="a@gmail.com")
    await crud.update_project(b["id"], flow_account="b@gmail.com")
    await account_crud.mark_exhausted("a@gmail.com", "quota")
    cache: dict = {}
    assert await processor._account_held({"project_id": a["id"]}, cache)
    assert not await processor._account_held({"project_id": b["id"]}, cache)
    await account_crud.reactivate("a@gmail.com")
    assert not await processor._account_held({"project_id": a["id"]}, {})


async def test_an_offline_account_waits_without_spending_attempts(test_db):
    from agent.db import crud
    from agent.services.flow_client import ACCOUNT_NOT_CONNECTED
    from agent.worker import processor
    req = await crud.create_request(req_type="GENERATE_VIDEO_REFS")
    await processor._handle_failure(req["id"], req, {"error": f"{ACCOUNT_NOT_CONNECTED}: tài khoản x chưa kết nối"})
    row = await crud.get_request(req["id"])
    assert row["status"] == "PENDING" and row["retry_count"] == 0


async def test_unbound_film_does_not_jump_accounts_on_quota_either():
    c = FlowClient()
    a = EchoWS(c, "A", error="PUBLIC_ERROR_USER_QUOTA_REACHED")
    b = EchoWS(c, "B")
    c.set_extension(a); c.set_extension(b)
    c._extension_ws = a
    res = await c._send("generate", {}, timeout=2)
    assert "QUOTA" in res.get("error", "") and b.calls == 0


def test_a_new_film_after_a_restart_still_gets_the_connected_account():
    """20/10: Daniel v3 was created before any request answered, so it stayed unbound."""
    c, a, b = _two_accounts()
    assert c.last_account is None and c.home_account() is None          # two accounts: cannot guess
    c.remove_extension(b) if hasattr(c, "remove_extension") else c._extensions.pop(b)
    assert c.home_account() == "a@gmail.com"
