"""Credit accounting and the daily cap.

Flow does not tell us the balance on the batch transport, so credits are counted locally from the
requests that reached Flow, at the estimated price per kind (config.DIRECTOR_CREDIT_TABLE). The
daily cap is the user's safety net: once today's spend would pass it, Flow work waits in the queue.
"""
import json
from datetime import datetime, time, UTC
from pathlib import Path

from agent import config
from agent.db.crud import get_db

VIDEO_TYPES = {"GENERATE_VIDEO", "GENERATE_VIDEO_REFS", "REGENERATE_VIDEO", "GENERATE_VIDEO_TEXT"}
IMAGE_TYPES = {"GENERATE_IMAGE", "REGENERATE_IMAGE", "EDIT_IMAGE", "GENERATE_CHARACTER_IMAGE",
               "REGENERATE_CHARACTER_IMAGE", "EDIT_CHARACTER_IMAGE"}
# A request costs once it reached Flow: finished, or being rendered right now.
_CHARGED = ("COMPLETED", "PROCESSING")


def cost(req_type: str) -> int:
    if req_type in VIDEO_TYPES:
        return config.DIRECTOR_CREDIT_TABLE["video"]
    if req_type in IMAGE_TYPES:
        return config.DIRECTOR_CREDIT_TABLE["image"]
    return 0


def _settings_path() -> Path:
    return Path(config.DATA_DIR) / "settings.json"


def load_settings() -> dict:
    try:
        return {"daily_credit_cap": 0} | json.loads(_settings_path().read_text())
    except (OSError, ValueError):
        return {"daily_credit_cap": 0}


def save_settings(**changes) -> dict:
    s = load_settings() | changes
    _settings_path().parent.mkdir(parents=True, exist_ok=True)
    _settings_path().write_text(json.dumps(s, indent=2))
    return s


def _day_start_utc(now: datetime | None = None) -> str:
    """Local midnight, as the UTC timestamp format the request table uses."""
    local = (now or datetime.now().astimezone())
    start = datetime.combine(local.date(), time.min, tzinfo=local.tzinfo)
    return start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def spent(since: str | None = None, project_id: str | None = None) -> int:
    db = await get_db()
    q = f"SELECT type, COUNT(*) FROM request WHERE status IN ({','.join('?' * len(_CHARGED))})"
    params: list = list(_CHARGED)
    if since:
        q += " AND updated_at >= ?"; params.append(since)
    if project_id:
        q += " AND project_id = ?"; params.append(project_id)
    cur = await db.execute(q + " GROUP BY type", params)
    return sum(cost(t) * n for t, n in await cur.fetchall())


async def spent_today() -> int:
    return await spent(since=_day_start_utc())


async def cap_blocks(req_type: str) -> bool:
    """True when submitting one more request of this type would pass today's cap."""
    cap = int(load_settings().get("daily_credit_cap") or 0)
    return cap > 0 and cost(req_type) > 0 and await spent_today() + cost(req_type) > cap


async def summary(project_id: str | None = None) -> dict:
    cap = int(load_settings().get("daily_credit_cap") or 0)
    today = await spent_today()
    out = {"today": today, "cap": cap, "left_today": max(0, cap - today) if cap else None,
           "prices": dict(config.DIRECTOR_CREDIT_TABLE), "estimated": True}
    if project_id:
        out["project"] = await spent(project_id=project_id)
    return out
