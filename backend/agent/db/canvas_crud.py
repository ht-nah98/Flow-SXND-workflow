"""FK-LOCAL: persistence for canvas layout rows."""
import json
from datetime import datetime, UTC

from agent.db.schema import get_db, _db_lock


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(r) -> dict:
    d = dict(r)
    d["data"] = json.loads(d["data"]) if d.get("data") else {}
    return d


async def upsert_node(project_id: str, node_key: str, x: float, y: float,
                      w: float | None = None, h: float | None = None,
                      data: dict | None = None) -> dict:
    db = await get_db()
    async with _db_lock:
        await db.execute(
            """INSERT INTO canvas_node (project_id,node_key,x,y,w,h,data,updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(project_id,node_key) DO UPDATE SET
                 x=excluded.x, y=excluded.y,
                 w=COALESCE(excluded.w, canvas_node.w),
                 h=COALESCE(excluded.h, canvas_node.h),
                 data=COALESCE(excluded.data, canvas_node.data),
                 updated_at=excluded.updated_at""",
            (project_id, node_key, x, y, w, h,
             json.dumps(data) if data is not None else None, _now()))
        await db.commit()
    cur = await db.execute(
        "SELECT * FROM canvas_node WHERE project_id=? AND node_key=?", (project_id, node_key))
    return _row(await cur.fetchone())


async def delete_node(project_id: str, node_key: str) -> None:
    db = await get_db()
    async with _db_lock:
        await db.execute(
            "DELETE FROM canvas_node WHERE project_id=? AND node_key=?", (project_id, node_key))
        await db.commit()


async def list_nodes(project_id: str) -> list[dict]:
    """Return layout rows, pruning rows whose entity no longer belongs to the project."""
    db = await get_db()
    async with _db_lock:
        await db.execute(
            """DELETE FROM canvas_node WHERE project_id=? AND (
                 (node_key LIKE 'character:%' AND substr(node_key,11) NOT IN
                    (SELECT character_id FROM project_character WHERE project_id=?))
              OR (node_key LIKE 'video:%' AND substr(node_key,7) NOT IN
                    (SELECT id FROM video WHERE project_id=?))
              OR (node_key LIKE 'final:%' AND substr(node_key,7) NOT IN
                    (SELECT id FROM video WHERE project_id=?))
              OR (node_key LIKE 'scene:%' AND substr(node_key,7) NOT IN
                    (SELECT s.id FROM scene s JOIN video v ON s.video_id=v.id WHERE v.project_id=?))
              OR (node_key LIKE 'script:%' AND substr(node_key,8) != ?)
              OR (node_key LIKE 'idea:%' AND substr(node_key,6) NOT IN
                    (SELECT id FROM director_run WHERE project_id=?))
              OR (node_key LIKE 'review:%' AND substr(node_key,8) NOT IN
                    (SELECT id FROM director_run WHERE project_id=?))
            )""",
            (project_id, project_id, project_id, project_id, project_id, project_id, project_id, project_id))
        await db.commit()
    cur = await db.execute(
        "SELECT * FROM canvas_node WHERE project_id=? ORDER BY node_key", (project_id,))
    return [_row(r) for r in await cur.fetchall()]
