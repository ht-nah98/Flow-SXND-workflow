"""23/10: the user renamed the root folder (YOUTUBE → "Workflow Video Omini Making"); the DB still held 38 absolute
paths (films, idea images) and the canvas could not open the film. The backend now notices the move at start-up."""
import json

from agent.db import crud, rebase
from agent.db.schema import get_db
from agent.director import store


async def test_a_moved_root_folder_is_rewritten_in_the_db_once(test_db, tmp_path):
    old, new = tmp_path / "YOUTUBE", tmp_path / "Workflow Video Omini Making"
    (new / "du-lieu").mkdir(parents=True)
    (new / "du-lieu" / rebase.MARK).write_text(json.dumps({"data_dir": str(old / "du-lieu"),
                                                          "output_dir": str(old / "phim")}))
    p = await crud.create_project(name="Leo")
    v = await crud.create_video(project_id=p["id"], title="Leo")
    await crud.update_video(v["id"], horizontal_url=f"file://{old}/phim/leo_2a041c02/final.mp4")
    run = await store.create_run({"text": "x", "images": [{"file": f"{old}/du-lieu/uploads/ideas/a/1.jpg"}]}, {})
    await store.update_run(run["id"], final_path=f"{old}/phim/leo_2a041c02/final.mp4")

    out = await rebase.rebase_paths(new / "du-lieu", new / "phim")
    assert out["rows"] == 3 and (new / "du-lieu" / "backup").exists()
    assert (await crud.get_video(v["id"]))["horizontal_url"] == f"file://{new}/phim/leo_2a041c02/final.mp4"
    r = await store.get_run(run["id"])
    assert r["final_path"] == f"{new}/phim/leo_2a041c02/final.mp4"
    assert r["brief"]["images"][0]["file"] == f"{new}/du-lieu/uploads/ideas/a/1.jpg"
    assert json.loads((new / "du-lieu" / rebase.MARK).read_text())["output_dir"] == str(new / "phim")
    assert (await rebase.rebase_paths(new / "du-lieu", new / "phim"))["rows"] == 0      # nothing moved since


async def test_the_first_start_only_records_where_things_are(test_db, tmp_path):
    out = await rebase.rebase_paths(tmp_path / "du-lieu", tmp_path / "phim")
    assert out == {"rows": 0, "moved": {}} and (tmp_path / "du-lieu" / rebase.MARK).exists()
    db = await get_db()
    assert db is not None
