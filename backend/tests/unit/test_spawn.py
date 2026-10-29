"""23/10 code check (ruff RUF006): 8 fire-and-forget create_task calls kept no reference — asyncio holds tasks weakly,
so one could be collected mid-run (a film review or a recut stuck "running"), and their errors went unlogged."""
import asyncio
import gc
import logging

from agent.utils.tasks import running, spawn


async def test_a_spawned_task_is_kept_until_it_finishes_and_its_error_is_logged(caplog):
    done = asyncio.Event()

    async def work():
        await asyncio.sleep(0.01)
        done.set()

    async def broken():
        raise RuntimeError("boom")

    spawn(work())
    gc.collect()
    assert len(running()) == 1
    await asyncio.wait_for(done.wait(), 1)
    with caplog.at_level(logging.ERROR):
        spawn(broken(), name="broken-job")
        for _ in range(5):
            await asyncio.sleep(0)
    assert not running()
    assert "broken-job" in caplog.text and "boom" in caplog.text
