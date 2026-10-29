import json

import pytest
from pydantic import ValidationError

from agent.director.schemas import Shot, ShotList, json_schema
from tests.unit.director.fixtures import fmv_shotlist


def test_duration_must_be_an_omni_flash_step():
    s = fmv_shotlist().shots[0].model_dump()
    s["duration_s"] = 5
    with pytest.raises(ValidationError):
        Shot(**s)


def test_json_schema_is_valid_json_for_the_cli():
    schema = json.loads(json_schema(ShotList))
    assert schema["type"] == "object" and "shots" in schema["properties"]


def test_fixture_round_trips():
    sl = fmv_shotlist()
    assert ShotList.model_validate_json(sl.model_dump_json()) == sl
