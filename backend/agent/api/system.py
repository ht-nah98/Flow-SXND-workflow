"""One place that says whether every part the user depends on is working, and how to fix it."""
import shutil
from pathlib import Path

from fastapi import APIRouter

from pydantic import BaseModel, Field

from agent import config
from agent.services import credits
from agent.services.flow_client import get_flow_client

router = APIRouter(prefix="/system", tags=["system"])


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok")
        probe.unlink()
        return True
    except OSError:
        return False


@router.get("/check")
async def check():
    client = get_flow_client()
    stats = getattr(client, "ws_stats", {}) or {}
    out_dir, data_dir = Path(config.OUTPUT_DIR), Path(config.DATA_DIR)
    free_gb = shutil.disk_usage(out_dir if out_dir.exists() else Path.home()).free / 1e9
    paused = int((getattr(client, "generation_guard_status", None) or {}).get("cooldown_remaining_s", 0))
    checks = [
        ("backend", "Backend", True, f"cổng {config.API_PORT}", ""),
        ("extension", "Extension Chrome", client.connected,
         ", ".join(stats.get("extension_versions") or []) or "chưa kết nối",
         "Mở Chrome profile của Flow, kiểm tra extension đã nạp (chrome://extensions) và mở một tab Google Flow."),
        ("flow_project", "Project Flow", bool(config.FLOW_PROJECT_ID), config.FLOW_PROJECT_ID[:8] or "chưa đặt",
         "Đặt FLOW_PROJECT_ID trong flow-canvas/.env rồi chạy lại backend."),
        ("flow_pause", "Google không chặn", paused == 0, f"tạm dừng {paused}s" if paused else "bình thường",
         "Google báo hoạt động bất thường: hệ thống tự chờ rồi gửi tiếp, không cần làm gì."),
        ("claude", "Claude (đạo diễn)", shutil.which("claude") is not None, shutil.which("claude") or "không tìm thấy",
         "Cài Claude Code và đăng nhập, để lệnh `claude` chạy được trong terminal."),
        ("ffmpeg", "ffmpeg (dựng phim)", shutil.which("ffmpeg") is not None, shutil.which("ffmpeg") or "không tìm thấy",
         "Cài ffmpeg: sudo apt install ffmpeg"),
        ("output", "Thư mục phim", _writable(out_dir), str(out_dir), "Kiểm tra FLOWKIT_OUTPUT_DIR trong .env."),
        ("data", "Thư mục dữ liệu", _writable(data_dir), str(data_dir), "Kiểm tra FLOWKIT_DATA_DIR trong .env."),
        ("disk", "Dung lượng trống", free_gb > 5, f"{free_gb:.0f} GB", "Còn dưới 5 GB: dọn bớt phim/ hoặc du-lieu/qc/."),
    ]
    items = [{"key": k, "label": label, "ok": ok, "detail": detail, "fix": "" if ok else fix}
             for k, label, ok, detail, fix in checks]
    return {"ok": all(i["ok"] for i in items), "items": items}


@router.get("/credits")
async def credit_summary(project_id: str | None = None):
    """Estimated credits spent today (and on one project), and the daily cap."""
    return await credits.summary(project_id)


class Settings(BaseModel):
    daily_credit_cap: int = Field(ge=0, le=100_000)   # 0 = no cap


@router.put("/settings")
async def put_settings(body: Settings):
    return credits.save_settings(**body.model_dump())
