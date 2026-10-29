"""Fire-and-forget background tasks that stay alive until they finish.

asyncio keeps only a weak reference to a task, so a bare ``asyncio.create_task(...)`` may be collected mid-run and its
error is never logged (23/10 code check, ruff RUF006: a recut, the film review, lesson learning, the extension
handshake and the worker's requests all did this)."""
import asyncio
import logging
from collections.abc import Coroutine

logger = logging.getLogger(__name__)
_running: set[asyncio.Task] = set()


def spawn(coro: Coroutine, name: str | None = None) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    _running.add(task)
    task.add_done_callback(_finished)
    return task


def running() -> set[asyncio.Task]:
    return set(_running)


def _finished(task: asyncio.Task) -> None:
    _running.discard(task)
    if not task.cancelled() and (exc := task.exception()):
        logger.error("background task %s failed", task.get_name(), exc_info=exc)
