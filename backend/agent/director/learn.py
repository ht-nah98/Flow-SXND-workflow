"""Learn from a sample video: find its shots, let Claude read the frames, and turn what works into
playbook notes and director lessons — but only the techniques the user adopts."""
import asyncio
import json
import re
import shutil
import subprocess
import uuid
from datetime import datetime, UTC
from pathlib import Path

from agent import config
from agent.director import brain, cut, store
from agent.director.schemas import SampleAnalysis
from agent.services import video_reviewer
from agent.utils.slugify import slugify

PLAYBOOK_SAMPLES = Path(__file__).parent / "knowledge" / "playbook" / "samples"


def samples_dir() -> Path:
    return Path(config.DATA_DIR) / "samples"


def _meta_path(sid: str) -> Path:
    return samples_dir() / sid / "meta.json"


def read_meta(sid: str) -> dict | None:
    try:
        return json.loads(_meta_path(sid).read_text())
    except (OSError, ValueError):
        return None


def _write_meta(sid: str, **changes) -> dict:
    meta = (read_meta(sid) or {}) | changes
    _meta_path(sid).write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def list_samples() -> list[dict]:
    if not samples_dir().exists():
        return []
    metas = [m for d in samples_dir().iterdir() if (m := read_meta(d.name))]
    return sorted(metas, key=lambda m: m.get("created_at", ""), reverse=True)


def scene_cuts(path: str, threshold: float = 0.3) -> list[float]:
    """Seconds where the picture changes sharply: the sample's shot boundaries."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vf", f"select='gt(scene,{threshold})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    return [round(float(t), 2) for t in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def save_upload(filename: str, data: bytes) -> dict:
    sid = uuid.uuid4().hex[:12]
    folder = samples_dir() / sid
    folder.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix.lower() or ".mp4"
    video = folder / f"mau{ext}"
    video.write_bytes(data)
    return _write_meta(sid, id=sid, name=Path(filename).stem, video=str(video), status="ANALYZING", error=None,
                       created_at=datetime.now(UTC).isoformat())


async def analyze(sid: str) -> dict:
    meta = read_meta(sid)
    video = meta["video"]
    try:
        duration = await asyncio.to_thread(cut.probe_duration, video) or 0
        cuts = await asyncio.to_thread(scene_cuts, video)
        interval = 1.0 if duration <= 90 else 2.0
        sheet_dir = samples_dir() / sid / "sheets"
        sheet_dir.mkdir(exist_ok=True)
        sheets, _, _ = await asyncio.to_thread(video_reviewer._create_contact_sheets, video, 1 / interval, str(sheet_dir))
        out = await brain.think("analyst", {"duration_s": duration, "cuts": cuts, "frame_interval_s": interval,
                                            "sheets": [str(s) for s in sheets]},
                                SampleAnalysis, tools=["Read"], add_dirs=[str(sheet_dir)])
        (samples_dir() / sid / "analysis.json").write_text(out.model_dump_json(indent=2))
        return _write_meta(sid, status="READY", title=out.title, duration_s=duration, shots=len(out.shots))
    except Exception as e:  # noqa: BLE001 — the page shows the reason and offers a retry
        return _write_meta(sid, status="FAILED", error=f"{type(e).__name__}: {e}")


def read_analysis(sid: str) -> SampleAnalysis | None:
    try:
        return SampleAnalysis.model_validate_json((samples_dir() / sid / "analysis.json").read_text())
    except (OSError, ValueError):
        return None


def _markdown(a: SampleAnalysis, adopted: list[int]) -> str:
    rows = "\n".join(f"| {i + 1} | {s.start_s:.1f}–{s.end_s:.1f}s | {s.content} | {s.framing} | {s.angle} | "
                     f"{s.movement} | {s.transition_in} | {s.look} |" for i, s in enumerate(a.shots))
    tech = "\n".join(f"- 🧪 **{t.name}** ({t.scope}): {t.rule}\n  - Cách làm: {t.how}\n  - Trong mẫu: {t.example}"
                     for i, t in enumerate(a.techniques) if i in adopted)
    return (f"# Mẫu: {a.title}\n\n{a.summary}\n\n## Cấu trúc\n\n{a.structure}\n\n## Từng shot\n\n"
            "| # | Thời gian | Nội dung | Cỡ cảnh | Góc máy | Chuyển động | Vào cảnh | Ánh sáng/màu |\n"
            f"|---|---|---|---|---|---|---|---|\n{rows}\n\n## Kỹ thuật áp dụng (🧪 chưa kiểm chứng)\n\n{tech}\n")


async def adopt(sid: str, picks: list[int]) -> dict:
    """Write the sample into the playbook and make the picked techniques active director lessons."""
    a = read_analysis(sid)
    if not a:
        raise LookupError("no analysis for this sample")
    picks = sorted({i for i in picks if 0 <= i < len(a.techniques)})
    PLAYBOOK_SAMPLES.mkdir(parents=True, exist_ok=True)
    note = PLAYBOOK_SAMPLES / f"{slugify(a.title)[:50] or sid}.md"
    note.write_text(_markdown(a, picks), encoding="utf-8")
    for i in picks:
        t = a.techniques[i]
        await store.add_lesson(t.scope, f"{t.rule} — Cách làm: {t.how}", f"sample:{a.title}", "ACTIVE",
                               evidence=[{"sample": sid, "example": t.example}])
    shutil.rmtree(samples_dir() / sid / "sheets", ignore_errors=True)   # frames are no longer needed
    return _write_meta(sid, status="ADOPTED", adopted=picks, playbook=str(note))
