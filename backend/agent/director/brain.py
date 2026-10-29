"""Claude as the director's brain: one headless `claude -p` call per stage (spec §2.1)."""
import asyncio
import contextvars
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path

from pydantic import BaseModel, ValidationError

from agent import config
from agent.director.schemas import json_schema

logger = logging.getLogger(__name__)
KNOWLEDGE = Path(__file__).parent / "knowledge"
PLAYBOOK = KNOWLEDGE / "playbook"
MAX_ATTEMPTS = 3
# The user's production playbook (proven on the FMV remake), by role.
PLAYBOOK_FOR = {
    "writer": ["01-kich-ban.md", "02-asset.md"],
    "director": ["03-prompt-video.md", "06-hieu-ung.md"],
    "dp": ["03-prompt-video.md", "05-xu-ly-loi.md"],
    "reshoot": ["03-prompt-video.md", "05-xu-ly-loi.md"],
    "analyst": ["03-prompt-video.md", "04-dung-phim.md"],
    "editor": ["03-prompt-video.md", "04-dung-phim.md", "06-hieu-ung.md"],
    "qc": ["03-prompt-video.md", "04-dung-phim.md"],
    "assistant": ["02-asset.md", "03-prompt-video.md"],
    "reviewer": ["01-kich-ban.md", "03-prompt-video.md", "04-dung-phim.md", "06-hieu-ung.md", "07-nhat-ky-bai-hoc.md"],
}


# The user's standing directives: every role reads them first, whatever its playbook files.
DIRECTIVES = "00-loi-dan-nguoi-dung.md"
# rules.md is the shot/prompt rule book: only the roles that plan, write or judge shots need it.
RULES_FOR = {"director", "dp", "reshoot", "editor", "qc", "analyst", "assistant", "reviewer"}
EFFECTS_FOR = {"director", "editor"}   # roles that choose film_look / edit_fx / edit_transition_out


# The Claude CLI's account limit ("You've hit your session limit · resets 6:20pm"): no retry helps.
USAGE_LIMIT = re.compile(r"hit your (session|usage|weekly) limit|usage limit reached", re.I)


class BrainError(Exception):
    pass


def keyframe_playbook() -> str:
    """Playbook 10, for the roles of a film in keyframe mode (directive B13); it overrides the cut-mode rules."""
    f = PLAYBOOK / "10-phim-keyframe.md"
    return ("## THIS FILM IS IN KEYFRAME MODE (brief.film_mode = keyframe) — playbook 10 overrides the cut-mode "
            f"rules above where they differ\n\n{f.read_text(encoding='utf-8')}") if f.exists() else ""


def ambient_playbook() -> str:
    """Playbook 11, for the roles of an ambient film (directive B14): no story; it overrides the story and cut rules."""
    f = PLAYBOOK / "11-phim-khong-khi.md"
    return ("## THIS FILM IS IN AMBIENT MODE (brief.film_mode = ambient) — NO STORY; playbook 11 overrides the story, "
            f"cut-mode and voice rules above where they differ\n\n{f.read_text(encoding='utf-8')}") if f.exists() else ""


def continuous_playbook() -> str:
    """Playbook 09, for the roles of a film in continuous mode (directive B12); it overrides the cut-mode rules."""
    f = PLAYBOOK / "09-phim-lien-mach.md"
    return ("## THIS FILM IS IN CONTINUOUS MODE (brief.film_mode = continuous) — playbook 09 overrides the cut-mode "
            f"rules above where they differ\n\n{f.read_text(encoding='utf-8')}") if f.exists() else ""


def _system_prompt(role: str, context: str) -> str:
    role_file = KNOWLEDGE / "roles" / f"{role}.md"
    parts = [role_file.read_text(encoding="utf-8") if role_file.exists() else f"You are the {role}."]
    directives = PLAYBOOK / DIRECTIVES
    if directives.exists():
        parts.append(f"## User directives (highest priority — they override anything below)\n\n"
                     f"{directives.read_text(encoding='utf-8')}")
    rules = KNOWLEDGE / "rules.md"
    if role in RULES_FOR and rules.exists():
        parts.append(rules.read_text(encoding="utf-8"))
    for name in PLAYBOOK_FOR.get(role, []):
        f = PLAYBOOK / name
        if f.exists():
            parts.append(f"## Playbook: {name}\n\n{f.read_text(encoding='utf-8')}")
    if role in EFFECTS_FOR:
        from agent.director import effects
        parts.append("## Edit effects (ids you may use; anything else becomes a plain cut)\n\n" + effects.catalog_text())
    if context:
        parts.append(context)
    return "\n\n".join(parts)


async def _run_once(args: list[str], text: str) -> tuple[int, bytes, bytes]:
    """Run claude with the prompt on stdin (argv strings are capped at 128KB on Linux)."""
    proc = await asyncio.create_subprocess_exec(
        *args, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=text.encode("utf-8")), config.DIRECTOR_CLAUDE_TIMEOUT_S)
    except (TimeoutError, asyncio.CancelledError):
        proc.kill()  # no orphan claude processes (timeout, or the run was cancelled)
        raise
    return proc.returncode, stdout, stderr


def model_for(role: str, *, escalate: bool = False) -> str | None:
    """The role's model; a retry after a rejected answer escalates to the strong model."""
    return config.DIRECTOR_ESCALATE_MODEL if escalate else config.DIRECTOR_ROLE_MODELS.get(role)


# The director run a Claude call belongs to, so the call shows in that run's 📋 Nhật ký (set by the pipeline loop).
CURRENT_RUN: contextvars.ContextVar[str | None] = contextvars.ContextVar("director_run", default=None)
ROLE_VI = {"producer": "Đọc ý tưởng", "writer": "Biên kịch", "director": "Đạo diễn chia cảnh", "dp": "Viết prompt",
           "editor": "Duyệt kịch bản", "qc": "Kiểm tra video", "reshoot": "Sửa prompt cảnh lỗi", "coach": "Rút bài học",
           "reviewer": "Agent Review", "analyst": "Phân tích video mẫu", "assistant": "Trợ lý"}


def _log_event(role: str, model: str | None, attempt: int, out: dict, ms: int) -> None:
    rid = CURRENT_RUN.get()
    if not rid:
        return
    from agent.director import store
    u = out.get("usage") or {}
    ok = not out.get("is_error")
    data = {"role": role, "model": model or "default", "attempt": attempt, "ms": ms, "ok": ok,
            "cost_usd": round(out.get("total_cost_usd") or 0, 4), "out_tokens": u.get("output_tokens")}
    title = f"{ROLE_VI.get(role, role)} · {model or 'default'}" + (f" · lần {attempt}" if attempt > 1 else "")
    try:
        asyncio.get_running_loop().create_task(store.log_event(rid, "ai", title, data, "info" if ok else "error"))
    except RuntimeError:
        pass


def _log_usage(role: str, model: str | None, attempt: int, out: dict, ms: int) -> None:
    """One line per Claude call in <data>/logs/brain-usage.jsonl, to tune the role→model table on real numbers."""
    try:
        path = config.DATA_DIR / "logs" / "brain-usage.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        u = out.get("usage") or {}
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "role": role, "model": model or "default",
               "used": sorted((out.get("modelUsage") or {}).keys()), "attempt": attempt, "ms": ms,
               "ok": not out.get("is_error"), "cost_usd": round(out.get("total_cost_usd") or 0, 4),
               "in": u.get("input_tokens"), "cache_read": u.get("cache_read_input_tokens"),
               "cache_write": u.get("cache_creation_input_tokens"), "out": u.get("output_tokens")}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:  # accounting must never break a film
        logger.exception("brain usage log failed")


async def _claude(role, payload, schema, *, tools=None, add_dirs=None, escalate=False, model=None) -> BaseModel:
    context = payload.pop("_context", "")
    system = _system_prompt(role, context)
    prompt = json.dumps(payload, ensure_ascii=False)
    schema_json = json_schema(schema)
    last_err = ""
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False) as f:
        f.write(system)
        system_path = f.name
    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            text = prompt if not last_err else (
                f"{prompt}\n\nYour previous answer was rejected. Validation error:\n{last_err}\n"
                "Return a corrected answer.")
            args = ["claude", "-p", "--system-prompt-file", system_path, "--output-format", "json",
                    "--json-schema", schema_json, "--tools", ",".join(tools or [])]
            # The last validation retry goes to the strong model rather than repeating the same mistake.
            chosen = model if model and not (escalate or attempt == MAX_ATTEMPTS) else \
                model_for(role, escalate=escalate or attempt == MAX_ATTEMPTS)
            if chosen:
                args += ["--model", chosen]
            effort = config.DIRECTOR_ROLE_EFFORT.get(role)
            if effort:
                args += ["--effort", effort]
            for d in add_dirs or []:
                args += ["--add-dir", d]
            t0 = time.monotonic()
            try:
                rc, stdout, stderr = await _run_once(args, text)
            except TimeoutError:
                last_err = f"timeout after {config.DIRECTOR_CLAUDE_TIMEOUT_S}s"
                continue
            try:
                out = json.loads(stdout or b"{}")
            except json.JSONDecodeError:
                last_err = f"non-JSON CLI output: {(stdout or b'')[-300:]!r} {(stderr or b'')[-300:]!r}"
                continue
            _log_usage(role, chosen, attempt, out, int((time.monotonic() - t0) * 1000))
            _log_event(role, chosen, attempt, out, int((time.monotonic() - t0) * 1000))
            if rc != 0 or out.get("is_error"):
                last_err = str(out.get("result") or (stderr or b"")[-300:])
                if USAGE_LIMIT.search(last_err):   # retrying cannot help before the reset time
                    raise BrainError(f"{role}: Claude đã hết lượt dùng — {last_err.strip()} "
                                     "Bấm 'Chạy lại bước' sau giờ reset (không tốn credit Flow).")
                continue
            try:
                return schema.model_validate(out.get("structured_output"))
            except ValidationError as e:
                last_err = f"validation: {e}"
                logger.info("brain %s attempt %d invalid: %s", role, attempt, e)
    finally:
        os.unlink(system_path)
    raise BrainError(f"{role}: {last_err}")


_brain = _claude


def set_brain(fn) -> None:
    global _brain
    _brain = fn


def reset_brain() -> None:
    global _brain
    _brain = _claude


async def think(role: str, payload: dict, schema: type[BaseModel], *, tools=None, add_dirs=None,
                escalate: bool = False, model: str | None = None) -> BaseModel:
    """`model` lets the user pick the model for one request (the canvas assistant); roles otherwise use their table."""
    kw = {"model": model} if model else {}
    return await _brain(role, dict(payload), schema, tools=tools, add_dirs=add_dirs, escalate=escalate, **kw)


class FakeBrain:
    """Deterministic brain for tests/E2E: pops canned responses per role."""

    def __init__(self, responses: dict[str, list[dict]]):
        self.responses = {k: list(v) for k, v in responses.items()}
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, role, payload, schema, **kw):
        self.calls.append((role, payload))
        queue = self.responses.get(role) or []
        if not queue:
            raise BrainError(f"FakeBrain has no response left for {role}")
        data = queue.pop(0) if len(queue) > 1 else queue[0]  # last response repeats
        return schema.model_validate(data)
