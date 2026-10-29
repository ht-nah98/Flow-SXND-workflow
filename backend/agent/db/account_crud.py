"""FK-LOCAL: Google accounts that run Flow (account rotation plan, 19/10)."""
from datetime import datetime, UTC

from agent.db.schema import _db_lock, get_db

STATUSES = ("ACTIVE", "EXHAUSTED", "DISABLED")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def seen(email: str, name: str | None = None) -> dict:
    """An extension reported this account: remember it (first seen goes to the end of the rotation order)."""
    db = await get_db()
    async with _db_lock:
        cur = await db.execute("SELECT COALESCE(MAX(priority), -1) + 1 FROM flow_account")
        nxt = (await cur.fetchone())[0]
        await db.execute(
            """INSERT INTO flow_account (email, name, priority, last_seen_at) VALUES (?,?,?,?)
               ON CONFLICT(email) DO UPDATE SET name=COALESCE(excluded.name, flow_account.name),
                 last_seen_at=excluded.last_seen_at""", (email.lower(), name, nxt, _now()))
        await db.commit()
    return await get(email)


async def get(email: str) -> dict | None:
    db = await get_db()
    cur = await db.execute("SELECT * FROM flow_account WHERE email=?", (email.lower(),))
    r = await cur.fetchone()
    return dict(r) if r else None


async def list_all() -> list[dict]:
    db = await get_db()
    cur = await db.execute("SELECT * FROM flow_account ORDER BY priority, email")
    return [dict(r) for r in await cur.fetchall()]


async def update(email: str, **kw) -> dict | None:
    allowed = {"label", "status", "priority", "exhausted_at", "last_error"}
    kw = {k: v for k, v in kw.items() if k in allowed}
    if "status" in kw and kw["status"] not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    if kw:
        db = await get_db()
        async with _db_lock:
            await db.execute(f"UPDATE flow_account SET {', '.join(f'{k}=?' for k in kw)} WHERE email=?",
                             (*kw.values(), email.lower()))
            await db.commit()
    return await get(email)


QUOTA_MARKERS = ("public_error_user_quota_reached", "public_error_per_model_daily_quota_reached")


def is_quota_error(message) -> bool:
    """Flow's out-of-credit answers. Quota belongs to the account: no other tab of that account can help."""
    low = str(message or "").lower()
    return any(m in low for m in QUOTA_MARKERS)


async def mark_exhausted(email: str, error: str) -> dict | None:
    """Step 3: the account ran out of credit — its films stop queueing until the user moves them or reactivates it."""
    if not await get(email):
        await seen(email)
    return await update(email, status="EXHAUSTED", exhausted_at=_now(), last_error=str(error)[:300])


async def reactivate(email: str) -> dict | None:
    return await update(email, status="ACTIVE", exhausted_at=None, last_error=None)


async def exhausted() -> set[str]:
    db = await get_db()
    cur = await db.execute("SELECT email FROM flow_account WHERE status='EXHAUSTED'")
    return {r[0] for r in await cur.fetchall()}
