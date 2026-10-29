"""One background task per run; resumes RUNNING runs after a restart (spec §10)."""
import asyncio
import logging

from agent.director import pipeline, store

logger = logging.getLogger(__name__)
_tasks: dict[str, asyncio.Task] = {}
_rekick: set[str] = set()   # kicks that arrived while the task was still live


def is_running(rid: str) -> bool:
    t = _tasks.get(rid)
    return bool(t and not t.done())


def kick(rid: str) -> None:
    if is_running(rid):
        _rekick.add(rid)    # the live task may be finishing; it re-checks the run before exiting
        return

    async def _go():
        try:
            while True:
                await pipeline.run_until_blocked(rid)
                if rid not in _rekick:
                    break
                _rekick.discard(rid)
                run = await store.get_run(rid)
                if not run or run["status"] != "RUNNING" or run["stage"] == "DONE":
                    break
        except Exception as e:  # never let a crash leave the run silently RUNNING
            logger.exception("director run %s crashed", rid)
            await store.update_run(rid, status="FAILED", error=f"crash: {e}")
        finally:
            _rekick.discard(rid)
            _tasks.pop(rid, None)
    _tasks[rid] = asyncio.create_task(_go())


async def cancel(rid: str) -> None:
    """End the run's task now (its Claude subprocess is killed on cancellation)."""
    _rekick.discard(rid)
    t = _tasks.get(rid)
    if t and not t.done():
        t.cancel()
        try:
            await t
        except BaseException:   # CancelledError, or whatever the stage raised while stopping
            pass


async def resume_all() -> None:
    for r in await store.list_runs(status="RUNNING"):
        kick(r["id"])
