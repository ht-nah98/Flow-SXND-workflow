"""Background worker — processes pending requests via Chrome extension.

Thin dispatcher: picks up PENDING requests, delegates to OperationService
for actual API work, handles status transitions + retry + scene updates.
"""
import asyncio
import base64
import json
import logging
import time

import aiohttp

from agent.db import account_crud, crud
from agent.services import credits
from agent.services.flow_client import ACCOUNT_NOT_CONNECTED, CURRENT_ACCOUNT, get_flow_client
from agent.services.event_bus import event_bus
from agent.config import POLL_INTERVAL, MAX_RETRIES, FLOW_UNUSUAL_ACTIVITY_MAX_ATTEMPTS

CAPTCHA_MAX_ATTEMPTS = 3   # FK-LOCAL: was 10 — repeated captcha failures look like a bot to Google
PAGE_RELOAD_SETTLE_S = 30      # FK-LOCAL: let a reloaded Flow tab load reCAPTCHA before the retry
PAGE_RELOAD_COOLDOWN_S = 120   # one reload covers every request that failed at the same time
_last_page_reload = 0.0


async def _reload_flow_tab() -> bool:
    """FK-LOCAL: ask the extension to reload flow.google.com; at most once per cooldown."""
    global _last_page_reload
    if time.time() - _last_page_reload < PAGE_RELOAD_COOLDOWN_S:
        return True   # a reload just happened; this request simply waits for it
    from agent.services.flow_client import get_flow_client
    res = await get_flow_client()._send("reload_flow_tab", {}, timeout=30)
    if res.get("error") or not (res.get("reloaded") or (res.get("result") or {}).get("reloaded")):
        logger.error("Flow tab reload failed: %s", res)
        return False
    _last_page_reload = time.time()
    return True


PAGE_CAPTCHA_MSG = ("CAPTCHA_FAILED: trang Flow chưa tải reCAPTCHA (đã tự tải lại tab 1 lần mà vẫn lỗi). "
                    "Tải lại tab flow.google.com (F5), kiểm tra còn đăng nhập, rồi bấm Tiếp tục / tạo lại. "
                    "Hàng chờ đã dừng để không gửi lặp.")
from agent.worker._parsing import _is_error
from agent.sdk.services.result_handler import parse_result, apply_scene_result, apply_character_result
from agent.utils.tasks import spawn

logger = logging.getLogger(__name__)

_API_CALL_TYPES = {"GENERATE_IMAGE", "REGENERATE_IMAGE", "EDIT_IMAGE",
                   "GENERATE_VIDEO", "REGENERATE_VIDEO", "GENERATE_VIDEO_REFS", "UPSCALE_VIDEO",
                   "GENERATE_CHARACTER_IMAGE", "REGENERATE_CHARACTER_IMAGE",
                   "EDIT_CHARACTER_IMAGE"}

_TYPE_PRIORITY = {
    "GENERATE_CHARACTER_IMAGE": 0, "REGENERATE_CHARACTER_IMAGE": 0, "EDIT_CHARACTER_IMAGE": 0,
    "GENERATE_IMAGE": 1, "REGENERATE_IMAGE": 1, "EDIT_IMAGE": 1,
    "GENERATE_VIDEO": 2, "REGENERATE_VIDEO": 2, "GENERATE_VIDEO_REFS": 2,
    "UPSCALE_VIDEO": 3,
}


class APIRateLimiter:
    """Enforces max concurrent requests AND minimum gap between API calls."""
    def __init__(self, max_concurrent: int, cooldown_seconds: float):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._cooldown = cooldown_seconds
        self._last_call = 0.0
        self._gate = asyncio.Lock()

    async def acquire(self):
        await self._semaphore.acquire()
        async with self._gate:
            elapsed = time.monotonic() - self._last_call
            if elapsed < self._cooldown:
                await asyncio.sleep(self._cooldown - elapsed)
            self._last_call = time.monotonic()

    def release(self):
        self._semaphore.release()


def _request_provider_name(req: dict) -> str:
    """Provider backend for a request row (persisted per request)."""
    from agent.config import DEFAULT_PROVIDER
    return ((req.get("provider") or DEFAULT_PROVIDER) or "").strip().lower() or "flow"


def _get_registry():
    """Shared provider registry (via the SDK singleton when initialized)."""
    try:
        from agent.sdk.services.operations import get_operations
        return get_operations().registry
    except RuntimeError:
        # SDK not initialized (e.g. unit tests) — build a standalone one.
        from agent.sdk.services.registry import ProviderRegistry
        from agent.services.flow_client import get_flow_client
        return ProviderRegistry(get_flow_client())


class WorkerController:
    """Controls the background worker loop with rate limiting and graceful shutdown."""

    def __init__(self):
        self._shutdown = asyncio.Event()
        self._active_ids: set[str] = set()
        self._active_provider: dict[str, str] = {}  # rid -> provider name
        # Per-provider rate limiters, built lazily from provider capabilities
        # (Flow: 5 concurrent + 10s cooldown; assistant: 2 concurrent, no
        # cooldown). Replaces the old single global limiter.
        self._limiters: dict[str, APIRateLimiter] = {}
        self._deferred: dict[str, float] = {}  # rid -> defer_until timestamp
        self._cap_logged: set[str] = set()  # requests already reported as held by the daily credit cap
        self._retry_after: dict[str, float] = {}  # rid -> retry_after timestamp

    @property
    def active_count(self) -> int:
        """Number of currently active requests."""
        return len(self._active_ids)

    def _limiter_for(self, provider_name: str, max_concurrent: int,
                     cooldown_s: float) -> APIRateLimiter:
        limiter = self._limiters.get(provider_name)
        if limiter is None:
            limiter = APIRateLimiter(max_concurrent, cooldown_s)
            self._limiters[provider_name] = limiter
            logger.info("Rate limiter for provider '%s': max_concurrent=%d cooldown=%.1fs",
                        provider_name, max_concurrent, cooldown_s)
        return limiter

    def _active_for_provider(self, provider_name: str) -> int:
        return sum(1 for p in self._active_provider.values() if p == provider_name)

    async def start(self):
        """Start the worker loop."""
        await self._cleanup_stale_processing()
        await self._run_loop()

    def request_shutdown(self):
        """Signal the worker to stop after current tasks drain."""
        self._shutdown.set()

    async def drain(self, timeout: float = 30.0):
        """Wait until all active tasks complete, with timeout."""
        deadline = time.monotonic() + timeout
        while self._active_ids and time.monotonic() < deadline:
            await asyncio.sleep(0.5)
        if self._active_ids:
            logger.warning("Drain timeout: %d tasks still active after %.0fs", len(self._active_ids), timeout)

    async def _cleanup_stale_processing(self):
        """Reset any requests stuck in PROCESSING state from a previous run."""
        try:
            stale = await crud.list_requests(status="PROCESSING")
            for req in stale:
                await crud.update_request(req["id"], status="PENDING",
                                          error_message="reset: stale PROCESSING on startup")
                logger.warning("Stale request reset: %s type=%s", req["id"][:8], req.get("type"))
            if stale:
                logger.info("Cleaned up %d stale PROCESSING requests", len(stale))
        except Exception as e:
            logger.warning("Could not clean up stale requests: %s", e)

    async def _run_loop(self):
        registry = _get_registry()

        while not self._shutdown.is_set():
            try:
                now = time.time()

                # Fetch a generous window of actionable requests; per-request
                # provider gating below decides what actually runs.
                fetch_limit = 0
                for name in registry.names():
                    caps = registry.get(name).capabilities
                    fetch_limit += max(0, caps.max_concurrent - self._active_for_provider(name))
                if fetch_limit <= 0:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                pending = await crud.list_actionable_requests(
                    exclude_ids=self._active_ids, limit=fetch_limit
                )

                pending_count = len(pending)
                await event_bus.emit("worker_tick", {
                    "active": len(self._active_ids),
                    "pending": pending_count,
                })

                if pending:
                    logger.info("Worker: %d actionable, %d active",
                                len(pending), len(self._active_ids))

                held_cache: dict = {}
                for req in pending:
                    rid = req["id"]

                    # Skip in-flight
                    if rid in self._active_ids:
                        continue

                    # Skip recently deferred (prereq or retry cooldown)
                    if rid in self._deferred and self._deferred[rid] > now:
                        continue
                    self._deferred.pop(rid, None)

                    # Skip if retry backoff not elapsed
                    if rid in self._retry_after and self._retry_after[rid] > now:
                        continue

                    # Provider-aware gate: resolve the backend for THIS
                    # request. A backend that is unavailable (e.g. Flow with
                    # no Chrome extension connected) leaves its requests
                    # PENDING while other providers keep working.
                    pname = _request_provider_name(req)
                    provider = registry.resolve(pname)
                    if not provider.is_available():
                        logger.debug("Request %s deferred: provider '%s' unavailable",
                                     rid[:8], provider.name)
                        continue
                    caps = provider.capabilities
                    if self._active_for_provider(provider.name) >= caps.max_concurrent:
                        continue
                    # Google asked us to slow down: leave Flow work queued until the pause ends.
                    if provider.name == "flow" and _flow_cooldown_s() > 0:
                        continue
                    # The user's daily credit cap: Flow work waits until tomorrow or a higher cap.
                    if provider.name == "flow" and await credits.cap_blocks(req.get("type", "")):
                        if rid not in self._cap_logged:
                            self._cap_logged.add(rid)
                            logger.warning("Request %s waits: daily credit cap reached", rid[:8])
                        continue

                    # Account rotation step 3: a film whose account is out of credit sends nothing more.
                    if provider.name == "flow" and await _account_held(req, held_cache):
                        continue

                    self._active_ids.add(rid)
                    self._active_provider[rid] = provider.name
                    spawn(self._run_one(req), name=f"request:{rid[:8]}")

                # Prune stale deferred/retry entries for requests no longer pending
                pending_ids = {r["id"] for r in pending}
                self._deferred = {k: v for k, v in self._deferred.items() if k in pending_ids}
                self._retry_after = {k: v for k, v in self._retry_after.items() if k in pending_ids}

            except Exception as e:
                logger.exception("Worker loop error: %s", e)

            await asyncio.sleep(POLL_INTERVAL)

    async def _run_one(self, req: dict):
        rid = req["id"]
        pname = _request_provider_name(req)
        registry = _get_registry()
        provider = registry.resolve(pname)
        caps = provider.capabilities
        limiter = self._limiter_for(provider.name, caps.max_concurrent, caps.cooldown_s)
        try:
            await limiter.acquire()
            try:
                await _process_one(req, self._deferred, self._retry_after)
            finally:
                limiter.release()
        finally:
            self._active_ids.discard(rid)
            self._active_provider.pop(rid, None)


async def _account_held(req: dict, cache: dict) -> bool:
    """True when the request's project belongs to an account marked EXHAUSTED (`cache` lives for one worker tick)."""
    if "exhausted" not in cache:
        cache["exhausted"] = await account_crud.exhausted()
    if not cache["exhausted"] or not req.get("project_id"):
        return False
    pid = req["project_id"]
    if pid not in cache:
        cache[pid] = ((await crud.get_project(pid)) or {}).get("flow_account")
    return cache[pid] in cache["exhausted"]


async def _prerequisites_met(req: dict, orientation: str) -> bool:
    """Check if prerequisites are ready. Returns False to defer (stay PENDING)."""
    req_type = req.get("type", "")
    prefix = "vertical" if orientation == "VERTICAL" else "horizontal"

    # Video gen needs scene image to be ready; upscale needs video to be ready
    if req_type in ("GENERATE_VIDEO", "REGENERATE_VIDEO", "GENERATE_VIDEO_REFS", "UPSCALE_VIDEO"):
        scene = await crud.get_scene(req.get("scene_id"))
        if not scene:
            return True  # let _dispatch handle "scene not found"
        # FK-LOCAL: r2v renders from entity references, not a scene keyframe
        if req_type in ("GENERATE_VIDEO", "REGENERATE_VIDEO"):
            if not scene.get(f"{prefix}_image_media_id"):
                logger.info("VIDEO prereq deferred: scene=%s no %s_image_media_id", req.get("scene_id","")[:12], prefix)
                return False
        elif req_type == "UPSCALE_VIDEO":
            if not scene.get(f"{prefix}_video_media_id"):
                logger.info("UPSCALE prereq deferred: scene=%s no %s_video_media_id", req.get("scene_id","")[:12], prefix)
                return False

    # Edit requests need source media (own image or parent's for INSERT scenes)
    if req_type in ("EDIT_IMAGE", "EDIT_CHARACTER_IMAGE"):
        if not req.get("source_media_id"):
            if req_type == "EDIT_CHARACTER_IMAGE":
                char = await crud.get_character(req.get("character_id"))
                if not char or not char.get("media_id"):
                    return False
            elif req_type == "EDIT_IMAGE":
                scene = await crud.get_scene(req.get("scene_id"))
                if not scene:
                    return True  # let _dispatch handle
                # CONTINUATION scenes always use parent's image as source
                src = None
                if scene.get("parent_scene_id"):
                    parent = await crud.get_scene(scene["parent_scene_id"])
                    src = parent.get(f"{prefix}_image_media_id") if parent else None
                if not src:
                    src = scene.get(f"{prefix}_image_media_id")
                logger.info("EDIT_IMAGE prereq: scene=%s src=%s parent=%s", req.get("scene_id","")[:12], src, scene.get("parent_scene_id","")[:12] if scene.get("parent_scene_id") else "none")
                if not src:
                    return False

    return True


async def _resolve_orientation(req: dict) -> str:
    """Resolve orientation from request, falling back to video table, then VERTICAL."""
    orient = req.get("orientation")
    if orient:
        return orient
    vid = req.get("video_id")
    if vid:
        video = await crud.get_video(vid)
        if video and video.get("orientation"):
            return video["orientation"]
    return "VERTICAL"


async def _process_one(req: dict, deferred: dict = None, retry_after: dict = None):
    """Every Flow call for this request goes to the Google account that holds its project (account rotation)."""
    project = await crud.get_project(req["project_id"]) if req.get("project_id") else None
    token = CURRENT_ACCOUNT.set((project or {}).get("flow_account"))
    try:
        return await _process_request(req, deferred, retry_after)
    finally:
        CURRENT_ACCOUNT.reset(token)


async def _process_request(req: dict, deferred: dict = None, retry_after: dict = None):
    rid, req_type = req["id"], req["type"]
    orientation = await _resolve_orientation(req)

    if await _is_already_completed(req, orientation):
        logger.info("Request %s skipped — already COMPLETED", rid[:8])
        # Copy existing result data from scene/character onto the request record
        skip_kwargs = {"status": "COMPLETED", "error_message": "skipped: already completed"}
        prefix = "vertical" if orientation == "VERTICAL" else "horizontal"
        if req_type in ("GENERATE_CHARACTER_IMAGE", "REGENERATE_CHARACTER_IMAGE", "EDIT_CHARACTER_IMAGE"):
            char = await crud.get_character(req.get("character_id"))
            if char:
                skip_kwargs["media_id"] = char.get("media_id")
                skip_kwargs["output_url"] = char.get("reference_image_url") or char.get("image_url")
        else:
            scene = await crud.get_scene(req.get("scene_id"))
            if scene:
                if req_type == "GENERATE_IMAGE":
                    skip_kwargs["media_id"] = scene.get(f"{prefix}_image_media_id")
                    skip_kwargs["output_url"] = scene.get(f"{prefix}_image_url")
                elif req_type in ("GENERATE_VIDEO", "REGENERATE_VIDEO", "GENERATE_VIDEO_REFS"):
                    skip_kwargs["media_id"] = scene.get(f"{prefix}_video_media_id")
                    skip_kwargs["output_url"] = scene.get(f"{prefix}_video_url")
                elif req_type == "UPSCALE_VIDEO":
                    skip_kwargs["media_id"] = scene.get(f"{prefix}_upscale_media_id")
                    skip_kwargs["output_url"] = scene.get(f"{prefix}_upscale_url")
        await crud.update_request(rid, **skip_kwargs)
        return

    # Check prerequisites before dispatching — don't burn retries on missing deps
    if not await _prerequisites_met(req, orientation):
        if deferred is not None:
            deferred[rid] = time.time() + 30  # defer 30s before rechecking
        return

    logger.info("Processing request %s type=%s", rid[:8], req_type)
    ev_ids = {  # FK-LOCAL: let the canvas refresh the right node
        "type": req_type, "scene_id": req.get("scene_id"), "character_id": req.get("character_id"),
        "video_id": req.get("video_id"), "project_id": req.get("project_id"),
    }
    await crud.update_request(rid, status="PROCESSING")
    await event_bus.emit("request_update", {"id": rid, "status": "PROCESSING", **ev_ids})

    try:
        result = await _dispatch(req, orientation)
        if _is_error(result):
            await _handle_failure(rid, req, result, retry_after)
        else:
            gen_result = parse_result(result, req_type)
            await crud.update_request(rid, status="COMPLETED", media_id=gen_result.media_id, output_url=gen_result.url)
            if req_type in ("GENERATE_CHARACTER_IMAGE", "REGENERATE_CHARACTER_IMAGE", "EDIT_CHARACTER_IMAGE"):
                char_id = req.get("character_id")
                if char_id:
                    await apply_character_result(char_id, gen_result)
            else:
                old_image = await _scene_image_media(req.get("scene_id"), orientation) \
                    if req_type in _SCENE_IMAGE_TYPES else None
                await apply_scene_result(req.get("scene_id"), req_type, orientation, gen_result)
                if old_image and gen_result.media_id and gen_result.media_id != old_image:
                    await _repin_end_frames(req, orientation, old_image, gen_result.media_id)
            await event_bus.emit("request_update", {"id": rid, "status": "COMPLETED", **ev_ids})
            logger.info("Request %s COMPLETED: media=%s", rid[:8], gen_result.media_id[:20] if gen_result.media_id else "?")
    except Exception as e:
        logger.exception("Request %s exception: %s", rid[:8], e)
        await event_bus.emit("request_update", {"id": rid, "status": "FAILED", "error": str(e), **ev_ids})
        await _handle_failure(rid, req, {"error": str(e)}, retry_after)


_SCENE_IMAGE_TYPES = ("GENERATE_IMAGE", "REGENERATE_IMAGE", "EDIT_IMAGE")


async def _scene_image_media(scene_id: str | None, orientation: str) -> str | None:
    scene = await crud.get_scene(scene_id) if scene_id else None
    return (scene or {}).get(f"{'vertical' if orientation == 'VERTICAL' else 'horizontal'}_image_media_id")


async def _repin_end_frames(req: dict, orientation: str, old: str, new: str) -> None:
    """Keyframe mode (B13, 22/10): a clip that ends on this scene's still was pinned to the old picture; a re-made
    still must carry the pin with it, or the next video of that clip would land on a frame that is no longer there."""
    prefix = "vertical" if orientation == "VERTICAL" else "horizontal"
    for sc in await crud.list_scenes(req.get("video_id")) if req.get("video_id") else []:
        if sc.get(f"{prefix}_end_scene_media_id") == old:
            await crud.update_scene(sc["id"], **{f"{prefix}_end_scene_media_id": new})
            logger.info("Scene %s now ends on the re-made still %s", sc["id"][:8], new[:12])


async def _dispatch(req: dict, orientation: str) -> dict:
    """Route request to the appropriate OperationService method."""
    from agent.sdk.services.operations import get_operations
    ops = get_operations()
    req_type, rid = req["type"], req["id"]
    pid = req.get("project_id", "0")
    # Per-request provider selection: persisted on the request row, falling
    # back to DEFAULT_PROVIDER when unset (handled by the registry).
    provider = req.get("provider")

    # Scene-based operations
    if req_type in ("GENERATE_IMAGE", "REGENERATE_IMAGE", "EDIT_IMAGE",
                    "GENERATE_VIDEO", "REGENERATE_VIDEO", "GENERATE_VIDEO_REFS", "UPSCALE_VIDEO"):
        scene = await crud.get_scene(req.get("scene_id"))
        if not scene:
            return {"error": "Scene not found"}
        scene["_project_id"] = pid

        if req_type in ("GENERATE_IMAGE", "REGENERATE_IMAGE"):
            return await ops.generate_scene_image(scene, orientation, job_id=rid, provider=provider)
        if req_type == "EDIT_IMAGE":
            return await ops.edit_scene_image(scene, orientation, source_media_id=req.get("source_media_id"), job_id=rid, provider=provider)
        if req_type in ("GENERATE_VIDEO", "REGENERATE_VIDEO"):
            return await ops.generate_scene_video(scene, orientation, request_id=rid, provider=provider)
        if req_type == "GENERATE_VIDEO_REFS":
            return await ops.generate_scene_video_refs(scene, orientation, request_id=rid, provider=provider)
        if req_type == "UPSCALE_VIDEO":
            return await ops.upscale_scene_video(scene, orientation, request_id=rid, provider=provider)

    # Character operations
    if req_type in ("GENERATE_CHARACTER_IMAGE", "REGENERATE_CHARACTER_IMAGE", "EDIT_CHARACTER_IMAGE"):
        char = await crud.get_character(req.get("character_id"))
        if not char:
            return {"error": "Character not found"}
        if req_type == "REGENERATE_CHARACTER_IMAGE":
            # Clear existing media so generate_reference_image takes the normal (not fast) path
            await crud.update_character(char["id"], media_id=None, reference_image_url=None)
            char["media_id"] = None
            char["reference_image_url"] = None
            return await ops.generate_reference_image(char, pid, job_id=rid, provider=provider,
                                                      orientation=req.get("orientation"))
        if req_type == "EDIT_CHARACTER_IMAGE":
            return await ops.edit_character_image(
                char, pid, source_media_id=req.get("source_media_id"), job_id=rid, provider=provider)
        return await ops.generate_reference_image(char, pid, job_id=rid, provider=provider,
                                                  orientation=req.get("orientation"))

    return {"error": f"Unknown request type: {req_type}"}


async def _reupload_media(url: str, project_id: str) -> str | None:
    """Download image from URL and re-upload to get a fresh media_id."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning("Re-upload: failed to download %s (status %d)", url[:60], resp.status)
                    return None
                image_bytes = await resp.read()
                content_type = resp.headers.get("Content-Type", "image/jpeg")

        if not content_type.startswith("image/"):
            logger.warning("Re-upload: unexpected content-type %s from %s", content_type, url[:60])
            return None
        image_b64 = base64.b64encode(image_bytes).decode()
        mime = content_type.split(";")[0].strip()

        client = get_flow_client()
        result = await client.upload_image(image_b64, mime_type=mime, project_id=project_id)
        new_mid = result.get("_mediaId")
        if new_mid:
            logger.info("Re-upload OK: fresh media_id=%s", new_mid[:20])
            return new_mid
        logger.warning("Re-upload: no media_id in response: %s", str(result)[:200])
    except Exception as e:
        logger.warning("Re-upload failed: %s", e)
    return None


async def _recover_entity_not_found(req: dict) -> bool:
    """When Google returns 'entity not found', re-upload the image to get a fresh media_id."""
    req_type = req.get("type", "")
    pid = req.get("project_id", "")
    orientation = await _resolve_orientation(req)
    prefix = "vertical" if orientation == "VERTICAL" else "horizontal"

    # Scene-based requests: re-upload scene image
    if req_type in ("GENERATE_VIDEO", "REGENERATE_VIDEO", "GENERATE_VIDEO_REFS", "UPSCALE_VIDEO"):
        scene = await crud.get_scene(req.get("scene_id"))
        if not scene:
            return False
        url = scene.get(f"{prefix}_image_url")
        if not url:
            return False
        new_mid = await _reupload_media(url, pid)
        if new_mid:
            await crud.update_scene(scene["id"], **{f"{prefix}_image_media_id": new_mid})
            logger.info("Recovered scene %s: new %s_image_media_id=%s", scene["id"][:12], prefix, new_mid[:12])
            return True

    # Character-based requests: re-upload ref image
    if req_type in ("EDIT_CHARACTER_IMAGE",):
        char = await crud.get_character(req.get("character_id"))
        if not char:
            return False
        url = char.get("reference_image_url")
        if not url:
            return False
        new_mid = await _reupload_media(url, pid)
        if new_mid:
            await crud.update_character(char["id"], media_id=new_mid)
            logger.info("Recovered character %s: new media_id=%s", char["id"][:12], new_mid[:12])
            return True

    return False


def _flow_cooldown_s() -> float:
    try:
        return get_flow_client().generation_cooldown_remaining()
    except Exception:
        return 0.0


async def _handle_failure(rid: str, req: dict, result: dict, retry_after: dict = None):
    error_msg = result.get("error")
    if not error_msg:
        data = result.get("data", {})
        if isinstance(data, dict):
            ef = data.get("error", "Unknown error")
            if isinstance(ef, dict):
                error_msg = ef.get("message", json.dumps(ef)[:200])
                # Extract detailed reason from error details (e.g. PUBLIC_ERROR_UNSAFE_GENERATION)
                details = ef.get("details", [])
                if details and isinstance(details, list):
                    for d in details:
                        reason = d.get("reason") if isinstance(d, dict) else None
                        if reason:
                            error_msg = f"{error_msg} [{reason}]"
                            break
            else:
                error_msg = str(ef)
        else:
            error_msg = "Unknown error"
    if isinstance(error_msg, dict):
        error_msg = json.dumps(error_msg)[:200]

    # Auto-recover expired media by re-uploading (only on real entity-not-found, never on polling timeout)
    if "not found" in str(error_msg).lower() and "polling timeout" not in str(error_msg).lower():
        recovered = await _recover_entity_not_found(req)
        if recovered:
            logger.info("Request %s: recovered expired media, retrying", rid[:8])
            await crud.update_request(rid, status="PENDING", request_id=None, error_message=f"recovered: {error_msg}")
            return

    error_lower = str(error_msg).lower()

    # FK-LOCAL account rotation step 3: the film's Google account is out of credit. Nothing a retry can fix: mark the
    # account EXHAUSTED, keep the request queued (no attempt counted) — the worker holds every request of that account
    # and the director stops at ACCOUNT_EXHAUSTED until the user moves the film or reactivates the account.
    account = CURRENT_ACCOUNT.get()
    if account and account_crud.is_quota_error(error_msg):
        await account_crud.mark_exhausted(account, str(error_msg))
        await crud.update_request(rid, status="PENDING", request_id=None,
                                  error_message=f"ACCOUNT_EXHAUSTED: tài khoản {account} hết credit ({error_msg})")
        await event_bus.emit("account_exhausted", {"account": account, "project_id": req.get("project_id")})
        logger.error("Request %s: account %s is out of credit — its queue is held", rid[:8], account)
        return
    # The film's account has no Chrome profile connected: wait for it, never count it as a failed attempt.
    if ACCOUNT_NOT_CONNECTED.lower() in error_lower:
        if retry_after is not None:
            retry_after[rid] = time.time() + 30
        await crud.update_request(rid, status="PENDING", error_message=str(error_msg))
        return

    # [HIJACK] extension_hijack_detected — the captcha bypass failed and the
    # token was poisoned by x2a. This is a system-level trap, NOT an account
    # issue. Don't burn retry count — the bypass may succeed on the next
    # attempt once the tab re-initializes.
    if "[hijack]" in error_lower or "extension_hijack" in error_lower:
        await crud.update_request(rid, status="PENDING", error_message=str(error_msg))
        logger.error(
            "Request %s [HIJACK] captcha bypass failed — will retry without "
            "counting (system error, not account error): %s",
            rid[:8], error_msg,
        )
        return

    # PUBLIC_ERROR_UNUSUAL_ACTIVITY is a Google anti-abuse/session trust block,
    # not an ordinary CAPTCHA mint failure. The flow client pauses every submit
    # (2, 5, then 10 min); the request waits in the queue for the pause to end.
    # Only a request Google itself blocked counts an attempt — one turned away by
    # the local pause never reached Google.
    if "public_error_unusual_activity" in error_lower or "unusual activity" in error_lower:
        local = "local cooldown active" in error_lower
        tries = req.get("retry_count", 0) + (0 if local else 1)
        if tries >= FLOW_UNUSUAL_ACTIVITY_MAX_ATTEMPTS:
            await crud.update_request(
                rid, status="FAILED",
                error_message=f"Google blocked this {tries} times (unusual activity); "
                              f"wait 15-30 min and resubmit. Last: {error_msg}")
            await _mark_scene_failed(req)
            logger.error("Request %s FAILED (unusual activity x%d): %s", rid[:8], tries, error_msg)
            return
        if retry_after is not None:
            retry_after[rid] = time.time() + _flow_cooldown_s() + 5
        await crud.update_request(rid, status="PENDING", retry_count=tries, error_message=str(error_msg))
        logger.warning("Request %s waits out Google unusual-activity pause (%.0fs, attempt %d/%d)",
                       rid[:8], _flow_cooldown_s(), tries, FLOW_UNUSUAL_ACTIVITY_MAX_ATTEMPTS)
        return

    # A capability the batch path does not have, or a missing Flow project, is
    # a configuration answer — not something a retry can reach. Fail it once.
    if ("unsupported_on_batch_api" in error_lower or "no_flow_project" in error_lower
            or "no_media_created" in error_lower):  # FK-LOCAL: policy-refused jobs never gain media
        await crud.update_request(rid, status="FAILED", error_message=str(error_msg))
        await _mark_scene_failed(req)
        logger.error("Request %s FAILED (not retryable): %s", rid[:8], error_msg)
        return

    # FK-LOCAL: Flow generated the clip and its output filter deleted it. The
    # filter is a coin flip on a fresh generation, so submit ONE new job (clear
    # the dead operation id, or the retry would just re-poll it); fail after that.
    if "media_removed" in error_lower:
        if req.get("retry_count", 0) < 1:
            await crud.update_request(rid, status="PENDING", retry_count=1, request_id=None,
                                      error_message=str(error_msg))
            logger.warning("Request %s media removed by Flow, resubmitting once: %s", rid[:8], error_msg)
        else:
            await crud.update_request(rid, status="FAILED", error_message=str(error_msg))
            await _mark_scene_failed(req)
            logger.error("Request %s FAILED (media removed twice): %s", rid[:8], error_msg)
        return

    # WS transient errors (extension disconnect/reconnect): retry without incrementing count
    if "extension reconnected" in error_lower or "extension disconnected" in error_lower or "extension not connected" in error_lower:
        await crud.update_request(rid, status="PENDING", error_message=str(error_msg))
        logger.info("Request %s transient WS error, will retry (no retry increment): %s", rid[:8], error_msg)
        return

    # FK-LOCAL: reCAPTCHA never loaded in the Flow tab ("Invalid site key or not loaded"). Every submit fails the
    # same way until flow.google.com is reloaded, and hammering Google risks the account. First time: reload the tab
    # ourselves and retry once after it settles. Still failing: fail this request and everything still queued
    # (nothing queued was sent), so the user reloads the tab by hand and presses resume once.
    if "invalid site key" in error_lower or "not loaded in api.js" in error_lower:
        if req.get("retry_count", 0) < 1 and await _reload_flow_tab():
            if retry_after is not None:
                retry_after[rid] = time.time() + PAGE_RELOAD_SETTLE_S
            await crud.update_request(rid, status="PENDING", retry_count=1,
                                      error_message=f"Đã tự tải lại tab Flow, thử lại sau {PAGE_RELOAD_SETTLE_S}s. ({error_msg})")
            logger.warning("Request %s: Flow page reCAPTCHA not loaded — reloaded the tab, retrying once", rid[:8])
            return
        msg = PAGE_CAPTCHA_MSG + f" ({error_msg})"
        await crud.update_request(rid, status="FAILED", error_message=msg)
        await _mark_scene_failed(req)
        for other in await crud.list_pending_requests():
            await crud.update_request(other["id"], status="FAILED", error_message=PAGE_CAPTCHA_MSG)
            await _mark_scene_failed(other)
        logger.error("Request %s: Flow page reCAPTCHA not loaded — queue stopped: %s", rid[:8], error_msg)
        return

    # reCAPTCHA errors: retry a few times — deferred dict in main loop handles delay
    if "captcha" in error_lower or "recaptcha" in error_lower or "unusual_activity" in error_lower:
        retry = req.get("retry_count", 0) + 1
        if retry < CAPTCHA_MAX_ATTEMPTS:
            await crud.update_request(rid, status="PENDING", retry_count=retry, error_message=str(error_msg))
            logger.warning("Request %s reCAPTCHA failed (retry %d/%d), will retry", rid[:8], retry, CAPTCHA_MAX_ATTEMPTS)
            return
        else:
            await crud.update_request(rid, status="FAILED", error_message=str(error_msg))
            await _mark_scene_failed(req)
            logger.error("Request %s FAILED after %d reCAPTCHA retries: %s", rid[:8], CAPTCHA_MAX_ATTEMPTS, error_msg)
            return

    retry = req.get("retry_count", 0) + 1
    if retry < MAX_RETRIES:
        now = time.time()
        if retry_after is not None:
            ra = retry_after.get(rid, 0.0)
            if ra > now:
                # Still in backoff — reset to PENDING so it's not stuck in PROCESSING
                await crud.update_request(rid, status="PENDING", error_message=str(error_msg))
                return
            retry_after[rid] = now + min(2 ** retry * 10, 300)
        await crud.update_request(rid, status="PENDING", retry_count=retry, error_message=str(error_msg))
        logger.warning("Request %s failed (retry %d/%d): %s", rid[:8], retry, MAX_RETRIES, error_msg)
    else:
        await crud.update_request(rid, status="FAILED", error_message=str(error_msg))
        await _mark_scene_failed(req)
        logger.error("Request %s FAILED permanently: %s", rid[:8], error_msg)


async def _mark_scene_failed(req: dict):
    scene_id = req.get("scene_id")
    if not scene_id:
        return
    orientation = await _resolve_orientation(req)
    prefix = "vertical" if orientation == "VERTICAL" else "horizontal"
    req_type = req["type"]
    updates = {}
    if req_type in ("GENERATE_IMAGE", "REGENERATE_IMAGE", "EDIT_IMAGE"):
        updates[f"{prefix}_image_status"] = "FAILED"
    elif req_type in ("GENERATE_VIDEO", "REGENERATE_VIDEO", "GENERATE_VIDEO_REFS"):
        updates[f"{prefix}_video_status"] = "FAILED"
    elif req_type == "UPSCALE_VIDEO":
        updates[f"{prefix}_upscale_status"] = "FAILED"
    if updates:
        await crud.update_scene(scene_id, **updates)


async def _is_already_completed(req: dict, orientation: str) -> bool:
    req_type = req.get("type", "")
    if req_type in ("EDIT_IMAGE", "REGENERATE_IMAGE", "REGENERATE_VIDEO", "REGENERATE_CHARACTER_IMAGE", "EDIT_CHARACTER_IMAGE"):
        return False  # Always run — explicitly requesting new generation

    if req_type == "GENERATE_CHARACTER_IMAGE":
        char_id = req.get("character_id")
        if not char_id:
            return False
        char = await crud.get_character(char_id)
        return bool(char and char.get("media_id"))

    scene_id = req.get("scene_id")
    if not scene_id:
        return False
    scene = await crud.get_scene(scene_id)
    if not scene:
        return False
    prefix = "vertical" if orientation == "VERTICAL" else "horizontal"
    if req_type == "GENERATE_IMAGE":
        return scene.get(f"{prefix}_image_status") == "COMPLETED"
    if req_type in ("GENERATE_VIDEO", "GENERATE_VIDEO_REFS"):
        return scene.get(f"{prefix}_video_status") == "COMPLETED"
    if req_type == "UPSCALE_VIDEO":
        return scene.get(f"{prefix}_upscale_status") == "COMPLETED"
    return False


# ─── Module-level controller ──────────────────────────────────

_controller: WorkerController | None = None


def get_worker_controller() -> WorkerController:
    global _controller
    if _controller is None:
        _controller = WorkerController()
    return _controller
