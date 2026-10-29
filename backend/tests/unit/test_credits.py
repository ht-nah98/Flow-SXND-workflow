import pytest

from agent import config
from agent.db import crud
from agent.services import credits


@pytest.fixture
def settings_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))


async def _req(status, type_="GENERATE_VIDEO_REFS"):
    p = await crud.create_project(name="p")
    r = await crud.create_request(type_, project_id=p["id"])
    await crud.update_request(r["id"], status=status)
    return p["id"]


async def test_spent_counts_requests_that_reached_flow(test_db, settings_dir):
    await _req("COMPLETED"); await _req("PROCESSING"); await _req("FAILED"); await _req("PENDING")
    await _req("COMPLETED", "GENERATE_CHARACTER_IMAGE")
    price = config.DIRECTOR_CREDIT_TABLE
    assert await credits.spent_today() == 2 * price["video"] + price["image"]


async def test_cap_holds_flow_work_once_reached(test_db, settings_dir):
    await _req("COMPLETED")
    assert await credits.cap_blocks("GENERATE_VIDEO_REFS") is False          # no cap set
    credits.save_settings(daily_credit_cap=config.DIRECTOR_CREDIT_TABLE["video"] + 1)
    assert await credits.cap_blocks("GENERATE_VIDEO_REFS") is True
    assert await credits.cap_blocks("GENERATE_CHARACTER_IMAGE") is False     # 1 credit still fits
    assert (await credits.summary())["left_today"] == 1
