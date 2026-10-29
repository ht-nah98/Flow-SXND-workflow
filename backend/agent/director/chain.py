"""Continuous mode (directive B12, playbook 09 §6): clips of one chain are made one after another, each opening on the
real last frame of the clip before — the way the user made "SIU Phẩm Giáng Sinh 1" by hand.

A chain is a run of shots joined by `continues`. Chains do not wait for each other. Inside a chain: clip N finishes →
its last frame is cut out of the video → uploaded to Flow → set as the next scene's end-scene image, which the r2v
request puts first among the references → clip N+1 is generated. A failed clip stops the rest of its chain: making
them from a wrong frame would only spend credit."""
import asyncio
import logging
import subprocess
from pathlib import Path

from agent import config
from agent.db import crud
from agent.director import cut as cut_mod
from agent.director import production, store
from agent.director.schemas import Shot

logger = logging.getLogger(__name__)
BLOCKED = "chain"          # failed[...] reason: the clip before it failed, so it was not made


def chains(shots: list[Shot]) -> list[list[Shot]]:
    out: list[list[Shot]] = []
    for s in sorted(shots, key=lambda x: x.order):
        if s.continues and out:
            out[-1].append(s)
        else:
            out.append([s])
    return out


def last_frame(clip: Path, out: Path) -> Path:
    """The clip's final frame at full resolution (a quarter second before the end: the very last one can be black)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.25", "-i", str(clip), "-frames:v", "1", "-update", "1",
                    "-q:v", "2", str(out)], check=True, capture_output=True, timeout=60)
    return out


async def _upload(path: Path, project_id: str) -> str:
    from agent.api.flow import _upload_image_bytes
    from agent.services.flow_client import get_flow_client
    up = await _upload_image_bytes(get_flow_client(), path.read_bytes(), project_id=project_id,
                                   mime_type="image/jpeg", file_name=path.name)
    if not up.get("media_id"):
        raise RuntimeError(f"Flow returned no media id for {path.name}")
    return up["media_id"]


async def link(run: dict, prev: Shot, cur: Shot) -> str:
    """Make prev's last frame the first reference of cur. Done once per take of prev (a new take is linked again)."""
    ids, ori = run["plan"]["ids"], run["plan"]["brief"]["orientation"]
    prefix = "vertical" if ori == "VERTICAL" else "horizontal"
    scene = await crud.get_scene(ids["scenes"][prev.id])
    take = scene.get(f"{prefix}_video_media_id")
    links = run["plan"].setdefault("chain_frames", {})
    got = links.get(cur.id)
    if got and got.get("from_take") == take:
        return got["media_id"]
    work = Path(config.DATA_DIR) / "chain" / run["id"]
    clip = await cut_mod.local_clip(scene, ori, work / "clips")
    img = await asyncio.to_thread(last_frame, clip, work / f"{prev.id}-{(take or 'x')[:8]}-last.jpg")
    media = await _upload(img, ids["project_id"])
    await crud.update_scene(ids["scenes"][cur.id], **{f"{prefix}_end_scene_media_id": media})
    links[cur.id] = {"media_id": media, "from_take": take, "from_shot": prev.id, "path": str(img)}
    await store.update_run(run["id"], plan=run["plan"])
    await store.log_event(run["id"], "chain", f"Nối chuỗi: khung cuối cảnh {prev.order} → ảnh #1 của cảnh {cur.order}",
                          {"from_shot": prev.id, "to_shot": cur.id, "scene": cur.order, "path": str(img)}, "ok")
    return media


async def make_chain(run: dict, chain: list[Shot], gen, failed: dict) -> None:
    """Generate one chain in order. `gen(shot)` creates (or returns) the shot's video request id."""
    for s in chain:                       # recomputed: a clip made since (retry, by hand) unblocks the rest
        if failed.get(s.id) in (BLOCKED, "chain_frame"):
            failed.pop(s.id)
    prev: Shot | None = None
    for s in chain:
        if prev is not None:
            if prev.id in failed:
                failed[s.id] = BLOCKED
                await store.log_event(run["id"], "chain", f"Cảnh {s.order} chưa tạo: cảnh {prev.order} trước nó bị lỗi",
                                      {"to_shot": s.id, "scene": s.order}, "warn")
                continue
            try:
                await link(run, prev, s)
            except Exception as e:  # noqa: BLE001 — without the frame the clip would not continue: stop the chain
                logger.warning("chain link %s → %s failed: %s", prev.id, s.id, e)
                failed[s.id] = "chain_frame"
                await store.log_event(run["id"], "chain", f"Không nối được cảnh {prev.order} → {s.order}",
                                      {"to_shot": s.id, "scene": s.order, "message": str(e)}, "error")
                prev = s
                continue
        rid = await gen(s)
        rows = await production.wait_requests([rid], run_id=run["id"])
        if rows[rid]["status"] == "FAILED":
            failed[s.id] = "video"
        elif failed.get(s.id) == "video":       # made since it failed (retry, by hand): the chain goes on from it
            failed.pop(s.id)
        prev = s
    await store.update_run(run["id"], plan=run["plan"])


async def make_all(run: dict, shots: list[Shot], gen) -> None:
    """All chains at once; inside each, one clip at a time. A gate (budget) raised by any chain is raised here."""
    failed = run["plan"].setdefault("failed", {})
    results = await asyncio.gather(*(make_chain(run, c, gen, failed) for c in chains(shots)), return_exceptions=True)
    for r in results:
        if isinstance(r, BaseException):
            raise r
