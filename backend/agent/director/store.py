"""Persistence for director runs, steps and lessons (spec §2.2, §9)."""
import json
import logging
import uuid
from datetime import datetime, UTC

from agent.db.crud import _db_lock, get_db

logger = logging.getLogger(__name__)
_JSON = {"brief", "budget", "spent", "plan", "input", "output", "lint", "evidence", "data"}


_RUN_SETTABLE = {"project_id", "stage", "status", "gate", "plan", "final_path", "error", "brief"}
_LESSON_SETTABLE = {"scope", "rule", "source", "status", "evidence"}


def _check(kw: dict, allowed: set) -> None:
    bad = set(kw) - allowed
    if bad:
        raise ValueError(f"not updatable: {sorted(bad)}")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _dec(row) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for key in _JSON & d.keys():
        if isinstance(d[key], str):
            d[key] = json.loads(d[key])
    return d


def _enc(kw: dict) -> dict:
    return {k: json.dumps(v, ensure_ascii=False) if k in _JSON else v for k, v in kw.items()}


async def _insert(table: str, row: dict) -> None:
    row = _enc(row)
    db = await get_db()
    async with _db_lock:
        await db.execute(f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join('?' * len(row))})",
                         list(row.values()))
        await db.commit()


async def _one(table: str, key: str) -> dict | None:
    db = await get_db()
    cur = await db.execute(f"SELECT * FROM {table} WHERE id=?", (key,))
    return _dec(await cur.fetchone())


async def _update(table: str, key: str, kw: dict) -> dict | None:
    kw = _enc(kw)
    if table != "director_step":
        kw["updated_at"] = _now()
    db = await get_db()
    async with _db_lock:
        await db.execute(f"UPDATE {table} SET {', '.join(f'{c}=?' for c in kw)} WHERE id=?",
                         [*kw.values(), key])
        await db.commit()
    return await _one(table, key)


async def create_run(brief: dict, budget: dict) -> dict:
    rid, now = str(uuid.uuid4()), _now()
    await _insert("director_run", {"id": rid, "brief": brief, "stage": "BRIEF", "status": "RUNNING",
                                   "budget": budget, "spent": {}, "plan": {}, "created_at": now, "updated_at": now})
    return await get_run(rid)


async def get_run(rid: str) -> dict | None:
    return await _one("director_run", rid)


async def update_run(rid: str, **kw) -> dict | None:
    _check(kw, _RUN_SETTABLE)
    return await _update("director_run", rid, kw)


async def list_runs(project_id: str | None = None, status: str | None = None) -> list[dict]:
    q, params = "SELECT * FROM director_run WHERE 1=1", []
    if project_id:
        q += " AND project_id=?"; params.append(project_id)
    if status:
        q += " AND status=?"; params.append(status)
    db = await get_db()
    cur = await db.execute(q + " ORDER BY created_at DESC", params)
    return [_dec(r) for r in await cur.fetchall()]


async def add_step(rid, stage, attempt, input, output, lint, status, duration_ms) -> dict:
    sid = str(uuid.uuid4())
    await _insert("director_step", {"id": sid, "run_id": rid, "stage": stage, "attempt": attempt,
                                    "input": input, "output": output, "lint": lint, "status": status,
                                    "duration_ms": duration_ms, "created_at": _now()})
    return await _one("director_step", sid)


async def log_event(rid: str, kind: str, title: str, data: dict | None = None, level: str = "info") -> None:
    """The run's activity log (canvas 📋 Nhật ký, 21/10): what the AI and the pipeline did, in Vietnamese titles.
    kind: stage | ai | gate | chain | qc | error. level: info | ok | warn | error. Never breaks the film."""
    try:
        await _insert("director_event", {"id": str(uuid.uuid4()), "run_id": rid, "kind": kind, "level": level,
                                         "title": title, "data": data or {}, "created_at": _now()})
        from agent.services.event_bus import event_bus
        await event_bus.emit("director_log", {"run_id": rid, "kind": kind})
    except Exception:  # noqa: BLE001
        logger.exception("log_event failed for %s", rid)


async def list_events(rid: str) -> list[dict]:
    db = await get_db()
    cur = await db.execute("SELECT * FROM director_event WHERE run_id=? ORDER BY created_at", (rid,))
    return [_dec(r) for r in await cur.fetchall()]


async def list_steps(rid: str) -> list[dict]:
    db = await get_db()
    cur = await db.execute("SELECT * FROM director_step WHERE run_id=? ORDER BY created_at", (rid,))
    return [_dec(r) for r in await cur.fetchall()]


async def typical_stage_ms() -> dict[str, int]:
    """Median duration of each stage over the last successful steps: the ETA shown while writing."""
    db = await get_db()
    cur = await db.execute("SELECT stage, duration_ms FROM director_step WHERE status='OK' AND duration_ms > 0 "
                           "ORDER BY created_at DESC LIMIT 400")
    by: dict[str, list[int]] = {}
    for stage, ms in await cur.fetchall():
        by.setdefault(stage, []).append(int(ms))
    return {k: sorted(v)[len(v) // 2] for k, v in by.items()}


async def reserve(rid: str, kind: str, n: int = 1) -> bool:
    """Atomically claim n generations of `kind` against the approved budget."""
    if n < 1:
        return False
    db = await get_db()
    async with _db_lock:
        cur = await db.execute("SELECT budget, spent FROM director_run WHERE id=?", (rid,))
        row = await cur.fetchone()
        if not row:
            return False
        budget, spent = json.loads(row["budget"]), json.loads(row["spent"])
        if spent.get(kind, 0) + n > budget.get(kind, 0):
            return False
        spent[kind] = spent.get(kind, 0) + n
        await db.execute("UPDATE director_run SET spent=?, updated_at=? WHERE id=?",
                         (json.dumps(spent), _now(), rid))
        await db.commit()
    return True


async def add_budget(rid: str, delta: dict[str, int]) -> dict | None:
    """Raise the approved budget by non-negative integer deltas."""
    for k, v in delta.items():
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValueError(f"budget delta for {k!r} must be a non-negative int")
    db = await get_db()
    async with _db_lock:
        cur = await db.execute("SELECT budget FROM director_run WHERE id=?", (rid,))
        row = await cur.fetchone()
        if not row:
            return None
        budget = json.loads(row["budget"])
        for k, v in delta.items():
            budget[k] = budget.get(k, 0) + v
        await db.execute("UPDATE director_run SET budget=?, updated_at=? WHERE id=?",
                         (json.dumps(budget), _now(), rid))
        await db.commit()
    return await get_run(rid)


async def add_lesson(scope, rule, source, status, evidence=None, id=None) -> dict:
    lid, now = id or str(uuid.uuid4()), _now()
    await _insert("director_lesson", {"id": lid, "scope": scope, "rule": rule, "source": source,
                                      "status": status, "evidence": evidence or [],
                                      "created_at": now, "updated_at": now})
    return await _one("director_lesson", lid)


async def get_lesson(lid: str) -> dict | None:
    return await _one("director_lesson", lid)


async def list_lessons(status: str | None = None, scopes: list[str] | None = None) -> list[dict]:
    q, params = "SELECT * FROM director_lesson WHERE 1=1", []
    if status:
        q += " AND status=?"; params.append(status)
    if scopes:
        q += f" AND scope IN ({','.join('?' * len(scopes))})"; params += scopes
    db = await get_db()
    cur = await db.execute(q + " ORDER BY created_at", params)
    return [_dec(r) for r in await cur.fetchall()]


async def update_lesson(lid: str, **kw) -> dict | None:
    _check(kw, _LESSON_SETTABLE)
    return await _update("director_lesson", lid, kw)
