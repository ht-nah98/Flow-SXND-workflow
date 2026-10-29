"""E2E only: load canned brain responses when FLOWKIT_DIRECTOR_FAKE_RESPONSES points to a JSON file."""
import json
import os

from agent.director import brain


def install_if_configured() -> bool:
    path = os.environ.get("FLOWKIT_DIRECTOR_FAKE_RESPONSES")
    if not path:
        return False
    with open(path, encoding="utf-8") as f:
        brain.set_brain(brain.FakeBrain(json.load(f)))
    return True
