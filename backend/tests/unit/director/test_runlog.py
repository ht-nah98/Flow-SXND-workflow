"""📋 Nhật ký (21/10): the user sees why a step was sent back, in Vietnamese, with the scene — and what the AI did."""
import re
from pathlib import Path

from agent.director import runlog, store


def test_every_lint_rule_has_a_vietnamese_name():
    src = "\n".join(f.read_text(encoding="utf-8") for f in (Path(runlog.__file__).parent / "lint").glob("*.py"))
    rules = set(re.findall(r'(?:add|LintIssue)\("([a-z_]+)"', src))
    assert rules and rules <= set(runlog.RULE_VI), sorted(rules - set(runlog.RULE_VI))


async def test_the_log_names_the_reason_and_the_scene(test_db):
    run = await store.create_run({"text": "old soldier", "target_s": 40}, {})
    run = await store.update_run(run["id"], plan={"shotlist": {"shots": [{"id": "SH03", "order": 3}]}})
    await store.add_step(run["id"], "SHOTLIST", 1, None, None,
                         [{"rule": "entrance", "shot_id": "SH03", "message": "Eddie is not in SH02", "severity": "error"}],
                         "LINT_FAILED", 312000)
    await store.log_event(run["id"], "ai", "Đạo diễn chia cảnh · opus", {"role": "director", "ms": 300000})
    log = await runlog.build(await store.get_run(run["id"]))
    step = log["steps"][0]
    assert step["label"] == "Chia cảnh" and step["status"] == "LINT_FAILED"
    assert step["issues"][0] | {} == {"rule": "entrance", "label": "Nhân vật xuất hiện từ hư không", "shot_id": "SH03",
                                      "scene": 3, "message": "Eddie is not in SH02", "severity": "error"}
    assert log["events"][0]["kind"] == "ai" and log["events"][0]["data"]["role"] == "director"
