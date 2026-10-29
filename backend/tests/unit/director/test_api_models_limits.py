import pytest
from pydantic import ValidationError

from agent.api.director import IDEA_MAX_CHARS, IdeaPatch, RunCreate


def test_a_long_story_idea_is_accepted():
    story = "Daniel từng có một cuộc sống bình dị. " * 300   # ~11k chars, like a full synopsis
    assert len(RunCreate(text=story).text) > 4000
    assert IdeaPatch(text=story).text == story


def test_idea_over_the_limit_is_rejected():
    with pytest.raises(ValidationError):
        RunCreate(text="x" * (IDEA_MAX_CHARS + 1))
