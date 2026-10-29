"""Create Flow requests through the budget guard and wait for them (restart-safe)."""
import asyncio

from agent import config
from agent.db import account_crud, crud
from agent.director import budget, store

TERMINAL = {"COMPLETED", "FAILED"}


class Paused(Exception):
    """The run left RUNNING while we were waiting; the caller should stop without failing."""


class AccountExhausted(Exception):
    """The film's Google account ran out of credit while its requests wait (account rotation step 3)."""
    def __init__(self, account: str, waiting: int):
        super().__init__(account)
        self.account, self.waiting = account, waiting


async def _held_account(run_id: str) -> str | None:
    run = await store.get_run(run_id)
    project = await crud.get_project(run["project_id"]) if run.get("project_id") else None
    account = (project or {}).get("flow_account")
    return account if account and account in await account_crud.exhausted() else None


async def _poll(request_ids: list[str], poll_s: float | None = None,
                run_id: str | None = None) -> dict[str, dict]:
    while True:
        if run_id and (await store.get_run(run_id))["status"] != "RUNNING":
            raise Paused(run_id)
        rows = {}
        for rid in request_ids:
            rows[rid] = await crud.get_request(rid) or {"id": rid, "status": "FAILED"}
        if all(r["status"] in TERMINAL for r in rows.values()):
            return rows
        if run_id and (account := await _held_account(run_id)):
            raise AccountExhausted(account, sum(1 for r in rows.values() if r["status"] not in TERMINAL))
        await asyncio.sleep(poll_s or config.DIRECTOR_POLL_S)


_waiter = _poll


def set_waiter(fn):
    global _waiter
    _waiter = fn


def reset_waiter():
    global _waiter
    _waiter = _poll


async def wait_requests(request_ids: list[str], poll_s: float | None = None,
                        run_id: str | None = None) -> dict[str, dict]:
    return await _waiter(request_ids, poll_s=poll_s, run_id=run_id)


# Pause fails what is still queued with this message: it never reached Flow (api/director.py _stop_queued).
STOPPED = "Đã dừng theo yêu cầu (chưa gửi Flow)."


async def request_for(run: dict, key: str, kind: str, *, retry_failed: bool = False, **kw) -> str:
    """Return the request already created for `key`, or create it under budget and remember it."""
    reqs = run["plan"].setdefault("requests", {})
    if key in reqs:
        row = await crud.get_request(reqs[key])
        if row and row["status"] == "FAILED" and row.get("error_message") == STOPPED:
            # 23/10 Blue Morning: resume adopted the paused clips as failed and re-sent nothing. A stopped request
            # never reached Flow, so it goes again on the reservation it already holds.
            reqs[key] = (await crud.create_request(**kw))["id"]
            await store.update_run(run["id"], plan=run["plan"])
            return reqs[key]
        if not (retry_failed and row and row["status"] == "FAILED"):
            return reqs[key]
    else:
        # a crash between create_request and persisting the key must not cost a second reservation
        for q in await crud.list_requests(project_id=kw.get("project_id")):
            if (q["id"] not in reqs.values()      # already owned by another key (e.g. the original video)
                    and q["type"] == kw["req_type"] and q["status"] != "FAILED"
                    and q.get("scene_id") == kw.get("scene_id")
                    and q.get("character_id") == kw.get("character_id")):
                reqs[key] = q["id"]
                await store.update_run(run["id"], plan=run["plan"])
                return q["id"]
    row = await budget.guarded_request(run["id"], kind, **kw)
    reqs[key] = row["id"]
    await store.update_run(run["id"], plan=run["plan"])   # persist before waiting (restart safety)
    return row["id"]
