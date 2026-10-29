import asyncio
import json

import pytest

from agent import config
from agent.director import brain
from agent.director.schemas import BriefAnalysis

GOOD = {"logline": "l", "genre": "romance", "tone": "warm", "target_s": 30,
        "orientation": "HORIZONTAL", "material": "realistic", "language": "vi"}


class FakeProc:
    def __init__(self, out: dict, rc=0):
        self.returncode, self._out = rc, json.dumps(out).encode()
        self.stdin_bytes = None
        self.killed = False

    async def communicate(self, input=None):
        self.stdin_bytes = input
        return self._out, b""

    def kill(self):
        self.killed = True


@pytest.fixture
def spawn(monkeypatch):
    calls, procs = [], []

    def install(*outs):
        it = iter(outs)

        async def fake_exec(*args, **kw):
            calls.append(args)
            procs.append(FakeProc(next(it)))
            return procs[-1]
        monkeypatch.setattr(brain.asyncio, "create_subprocess_exec", fake_exec)
        return calls, procs
    return install


async def test_reads_structured_output(spawn):
    calls, procs = spawn({"is_error": False, "structured_output": GOOD})
    out = await brain.think("producer", {"text": "x"}, BriefAnalysis)
    assert out.target_s == 30
    args = calls[0]
    assert args[0] == "claude" and "--json-schema" in args and args[args.index("--tools") + 1] == ""
    assert "--system-prompt-file" in args
    assert args[1] == "-p" and args[2].startswith("--")  # prompt goes on stdin, not argv
    assert b'"text"' in procs[0].stdin_bytes


async def test_invalid_output_is_retried_with_the_error(spawn):
    _, procs = spawn({"is_error": False, "structured_output": {"logline": "only"}},
                     {"is_error": False, "structured_output": GOOD})
    out = await brain.think("producer", {"text": "x"}, BriefAnalysis)
    assert out.genre == "romance"
    assert "validation" in procs[1].stdin_bytes.decode().lower()


async def test_gives_up_after_three_attempts(spawn):
    bad = {"is_error": True, "result": "overloaded"}
    spawn(bad, bad, bad)
    with pytest.raises(brain.BrainError, match="overloaded"):
        await brain.think("producer", {"text": "x"}, BriefAnalysis)


async def test_timeout_kills_process_and_retries(monkeypatch):
    procs = []

    class Hang(FakeProc):
        async def communicate(self, input=None):
            await asyncio.sleep(10)

    async def fake_exec(*args, **kw):
        procs.append(Hang({}) if not procs else FakeProc({"is_error": False, "structured_output": GOOD}))
        return procs[-1]
    monkeypatch.setattr(brain.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(config, "DIRECTOR_CLAUDE_TIMEOUT_S", 0.05)
    out = await brain.think("producer", {"text": "x"}, BriefAnalysis)
    assert out.tone == "warm" and procs[0].killed


async def test_system_prompt_file_is_removed(spawn):
    import os
    calls, _ = spawn({"is_error": False, "structured_output": GOOD})
    await brain.think("producer", {"text": "x", "_context": "LESSONS"}, BriefAnalysis)
    args = calls[0]
    assert not os.path.exists(args[args.index("--system-prompt-file") + 1])


async def test_fake_brain_swaps_in():
    fake = brain.FakeBrain({"producer": [GOOD]})
    brain.set_brain(fake)
    try:
        out = await brain.think("producer", {"text": "x"}, BriefAnalysis)
    finally:
        brain.reset_brain()
    assert out.tone == "warm" and fake.calls[0][0] == "producer"


def _flag(args, name):
    return args[args.index(name) + 1] if name in args else None


async def test_each_role_runs_on_its_own_model_and_effort(spawn):
    calls, _ = spawn({"is_error": False, "structured_output": GOOD})
    await brain.think("producer", {"text": "x"}, BriefAnalysis)
    assert _flag(calls[0], "--model") == config.DIRECTOR_ROLE_MODELS["producer"] == "haiku"
    assert _flag(calls[0], "--effort") == "low"


def test_role_table_keeps_judgement_on_opus_and_templates_cheaper():
    m = config.DIRECTOR_ROLE_MODELS
    assert m["writer"] == m["director"] == m["editor"] == m["analyst"] == "opus"
    assert m["dp"] == "sonnet" and m["producer"] == "haiku"
    assert brain.model_for("dp", escalate=True) == config.DIRECTOR_ESCALATE_MODEL == "opus"


async def test_the_last_validation_retry_escalates_to_the_strong_model(spawn):
    bad = {"is_error": False, "structured_output": {"logline": "only"}}
    calls, _ = spawn(bad, bad, {"is_error": False, "structured_output": GOOD})
    await brain.think("producer", {"text": "x"}, BriefAnalysis)
    assert [_flag(a, "--model") for a in calls] == ["haiku", "haiku", "opus"]


async def test_escalate_flag_uses_the_strong_model_from_the_first_try(spawn):
    calls, _ = spawn({"is_error": False, "structured_output": GOOD})
    await brain.think("producer", {"text": "x"}, BriefAnalysis, escalate=True)
    assert _flag(calls[0], "--model") == "opus"


async def test_every_call_logs_its_tokens_and_cost(spawn):
    log = config.DATA_DIR / "logs" / "brain-usage.jsonl"
    before = log.read_text().count("\n") if log.exists() else 0
    spawn({"is_error": False, "structured_output": GOOD, "total_cost_usd": 0.0123,
           "usage": {"input_tokens": 5, "output_tokens": 7}, "modelUsage": {"claude-haiku-5-5": {}}})
    await brain.think("producer", {"text": "x"}, BriefAnalysis)
    row = json.loads(log.read_text().splitlines()[before])
    assert row["role"] == "producer" and row["model"] == "haiku" and row["used"] == ["claude-haiku-5-5"]
    assert row["cost_usd"] == 0.0123 and row["out"] == 7


async def test_account_limit_is_not_retried(spawn):
    """16/10: 'You've hit your session limit' was retried 3 times in 9 seconds; nothing changes before the reset."""
    calls, _ = spawn({"is_error": True, "result": "You've hit your session limit · resets 6:20pm (Asia/Bangkok)"})
    with pytest.raises(brain.BrainError, match="hết lượt.*6:20pm"):
        await brain.think("editor", {"x": 1}, BriefAnalysis)
    assert len(calls) == 1
