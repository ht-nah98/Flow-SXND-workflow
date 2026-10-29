"""AI Director state machine (spec §2.3). One handler per stage; each returns the next stage.

Split on 23/10 (plan docs/thiet-ke/ke-hoach-tach-pipeline-lint.md): the stages and the user's actions live in
stage_common / stages_script / stages_media / stages_film / actions; every name stays importable from here."""
import logging
import time
from collections.abc import Awaitable, Callable


from agent.db import crud
from agent.director import brain
from agent.director import lessons, production, store
from agent.services.event_bus import event_bus
from agent.services.flow_client import CURRENT_ACCOUNT
from agent.director.stage_common import (  # noqa: F401
    CONTINUOUS_ROLES,
    Gate,
    MAX_LINT_ATTEMPTS,
    STAGES,
    StageFailed,
    _ask,
    _gen,
    _keyframe_budget,
    _keyframe_mode,
    _models,
    _public,
    _shot_ctx,
    agent_on,
    think_with_lint,
)
from agent.director.stages_script import (  # noqa: F401
    EDITOR_PASS_SCORE,
    MAX_EDIT_LOOPS,
    REVISE_STORY,
    _ASKS_VOICE,
    _dp_shots,
    _plain_brief,
    _revision_beats,
    _revision_prompts,
    h_brief,
    h_edit_review,
    h_prompts,
    h_shotlist,
    h_story,
)
from agent.director.stages_media import (  # noqa: F401
    MissingRefs,
    _check_refs,
    _missing_keyframes,
    _pin_keyframes,
    _refs_needed,
    h_ingest,
    h_keyframes,
    h_refs,
    h_videos,
    script_payload,
)
from agent.director.stages_film import (  # noqa: F401
    QC_BATCH,
    UNREVIEWED_TRIM,
    _clip_media,
    _contact_sheets,
    _qc_batch,
    _qc_one,
    _video_type,
    current_edit,
    h_cut,
    h_publish,
    h_qc,
    h_retro,
    save_edit,
)
from agent.director.actions import (  # noqa: F401
    AFTER_GATE,
    _one_prompt,
    apply_rewrite,
    approve,
    clips_missing,
    make_missing_refs,
    recut,
    resolve_shot_failure,
    revise,
    rewrite_issues,
    rewrite_shot,
)

logger = logging.getLogger(__name__)


async def _stop_here(run):
    raise Gate("TEST_STOP")


HANDLERS: dict[str, Callable[[dict], Awaitable[str]]] = {
    "BRIEF": h_brief, "STORY": h_story, "SHOTLIST": h_shotlist, "PROMPTS": h_prompts,
    "EDIT_REVIEW": h_edit_review, "INGEST": h_ingest, "REFS": h_refs, "KEYFRAMES": h_keyframes,
    "VIDEOS": h_videos, "QC": h_qc, "CUT": h_cut, "PUBLISH": h_publish,
}
HANDLERS["RETRO"] = h_retro
STAGE_VI = {"BRIEF": "Đọc ý tưởng", "STORY": "Viết câu chuyện", "SHOTLIST": "Chia cảnh", "PROMPTS": "Viết prompt",
            "EDIT_REVIEW": "Biên tập duyệt", "INGEST": "Tạo node trên canvas", "REFS": "Tạo ảnh asset", "KEYFRAMES": "Tạo ảnh keyframe",
            "VIDEOS": "Tạo video", "QC": "Kiểm tra video", "CUT": "Dựng phim", "PUBLISH": "Đưa phim lên canvas",
            "RETRO": "Rút bài học", "RESHOOT": "Viết lại prompt 1 clip"}
GATE_VI = {"SCRIPT": "duyệt kịch bản", "ASSETS": "duyệt ảnh asset", "KEYFRAMES": "duyệt ảnh keyframe", "SHOT_FAILED": "cảnh lỗi — chọn cách xử lý",
           "BUDGET_EXCEEDED": "hết credit đã duyệt", "ACCOUNT_EXHAUSTED": "tài khoản Flow hết credit"}


async def run_until_blocked(rid: str) -> dict:
    await lessons.ensure_seed()
    run = await store.get_run(rid)
    while run["status"] == "RUNNING" and run["stage"] != "DONE":
        stage = run["stage"]
        try:
            handler = HANDLERS.get(stage)
            if handler is None:
                raise StageFailed(f"no handler for stage {stage}")
            # Flow work for this film goes to the Google account that holds its project (account rotation).
            project = await crud.get_project(run["project_id"]) if run.get("project_id") else None
            token = CURRENT_ACCOUNT.set((project or {}).get("flow_account"))
            rtoken = brain.CURRENT_RUN.set(rid)
            t0 = time.monotonic()
            await store.log_event(rid, "stage", f"Bắt đầu: {STAGE_VI.get(stage, stage)}", {"stage": stage})
            try:
                nxt = await handler(run)
            finally:
                CURRENT_ACCOUNT.reset(token)
                brain.CURRENT_RUN.reset(rtoken)
            await store.log_event(rid, "stage", f"Xong: {STAGE_VI.get(stage, stage)}",
                                  {"stage": stage, "ms": int((time.monotonic() - t0) * 1000)}, "ok")
        except Gate as g:
            if g.gate == "TEST_STOP":
                return await store.update_run(rid, plan=run["plan"])
            run["plan"]["gate_payload"] = g.payload       # what the canvas shows at the gate
            run = await store.update_run(rid, plan=run["plan"], status="WAITING_GATE", gate=g.gate)
            await store.log_event(rid, "gate", f"Dừng chờ anh: {GATE_VI.get(g.gate, g.gate)}",
                                  {"gate": g.gate, "payload": g.payload}, "warn")
            await event_bus.emit("director_gate", {"run_id": rid, "gate": g.gate, "payload": g.payload})
            return run
        except production.Paused:
            return await store.update_run(rid, plan=run["plan"])
        except production.AccountExhausted as e:
            payload = {"account": e.account, "waiting": e.waiting, "stage": stage}
            run["plan"]["gate_payload"] = payload
            run = await store.update_run(rid, plan=run["plan"], status="WAITING_GATE", gate="ACCOUNT_EXHAUSTED")
            await event_bus.emit("director_gate", {"run_id": rid, "gate": "ACCOUNT_EXHAUSTED", "payload": payload})
            return run
        except Exception as e:
            if isinstance(e, StageFailed):
                msg = str(e)
            else:
                logger.exception("director stage %s crashed for run %s", stage, rid)
                msg = f"{type(e).__name__}: {e}"
            run = await store.update_run(rid, plan=run["plan"], status="FAILED", error=msg)
            await store.log_event(rid, "error", f"Lỗi ở bước {STAGE_VI.get(stage, stage)}", {"stage": stage,
                                                                                          "message": msg}, "error")
            await event_bus.emit("director_error", {"run_id": rid, "stage": stage, "message": msg})
            return run
        fresh = await store.get_run(rid)            # a pause may have arrived while we worked
        status = "DONE" if nxt == "DONE" else fresh["status"]
        run = await store.update_run(rid, plan=run["plan"], stage=nxt, status=status)
        await event_bus.emit("director_stage", {"run_id": rid, "stage": nxt, "status": status})
    return await store.get_run(rid)   # handlers may write columns directly (e.g. final_path)
