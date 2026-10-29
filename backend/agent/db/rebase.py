"""Absolute paths stored in the DB follow the data and film folders when they move.

23/10: the user renamed the root folder (YOUTUBE → "Workflow Video Omini Making"). The DB still held 38 absolute
paths — films (video urls, run final_path) and idea images (run brief/plan, step logs) — so the canvas could not
open a finished film until they were fixed by hand. The folders in use are recorded in DATA_DIR/paths.json (it moves
with the data); at start-up a change is rewritten in the columns below, after a backup of the DB."""
import json
import logging
import time
from pathlib import Path

from agent.db.schema import get_db

logger = logging.getLogger(__name__)
MARK = "paths.json"
COLUMNS = {"video": ("vertical_url", "horizontal_url"),
           "director_run": ("brief", "plan", "final_path"),
           "director_step": ("input", "output")}


async def rebase_paths(data_dir: Path, output_dir: Path) -> dict:
    now = {"data_dir": str(Path(data_dir).resolve()), "output_dir": str(Path(output_dir).resolve())}
    mark = Path(data_dir) / MARK
    try:
        last = json.loads(mark.read_text())
    except (FileNotFoundError, ValueError):
        last = {}
    moved = {last[k]: now[k] for k in now if last.get(k) and last[k] != now[k]}
    rows = 0
    if moved:
        db = await get_db()
        backup = Path(data_dir) / "backup" / f"flow_agent-truoc-doi-thu-muc-{time.strftime('%Y%m%d-%H%M%S')}.db"
        backup.parent.mkdir(parents=True, exist_ok=True)
        await db.execute("VACUUM INTO ?", (str(backup),))
        for old, new in sorted(moved.items(), key=lambda kv: -len(kv[0])):   # the longer folder first
            for table, cols in COLUMNS.items():
                for col in cols:
                    cur = await db.execute(f"UPDATE {table} SET {col} = replace({col}, ?, ?) WHERE {col} LIKE ?",
                                           (old + "/", new + "/", f"%{old}/%"))
                    rows += cur.rowcount
        await db.commit()
        logger.warning("Folders moved %s: rewrote %d DB rows (backup %s)", moved, rows, backup.name)
    mark.parent.mkdir(parents=True, exist_ok=True)
    mark.write_text(json.dumps(now, ensure_ascii=False))
    return {"rows": rows, "moved": moved}
