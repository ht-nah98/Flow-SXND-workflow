"""
Flow Client — communicates with Google Flow via the Chrome extension bridge.

Agent runs a WS server. Extension connects as client. Agent sends requests,
extension executes them in browser context (residential IP, cookies, reCAPTCHA).

One transport: Flow's ``batchexecute`` endpoint on flow.google.com, whose calls
only a signed-in page can sign — the agent builds the envelope, the extension
runs it in the tab (see :mod:`agent.services.flow_batch`).

The REST path against ``aisandbox-pa.googleapis.com`` that preceded it is gone.
It needed a ``Bearer ya29.…`` that Flow stopped minting in the September 2026
migration, so it could not run; keeping it only gave the next contributor a
second place to implement things. Git history has it if a payload is ever needed.

Answers are shaped like the old REST ones, so everything downstream — the
worker's parsers, the operation poller, the scene/character updaters — reads one
shape and never learns where it came from.
"""
import asyncio
import contextvars
import json
import logging
import time
import uuid

from agent.config import (
    VIDEO_MODELS,
    FLOW_PROJECT_ID, FLOW_ALLOW_DEGRADED,
    DEFAULT_PAYGATE_TIER,
    FLOW_GENERATION_MIN_INTERVAL_S, FLOW_GENERATION_MAX_CONCURRENT,
    FLOW_UNUSUAL_ACTIVITY_COOLDOWN_S,
)
from agent import config as _config
from agent.services import flow_batch as fb
from agent.utils.tasks import spawn

# Account rotation, step 2 (19/10): the Google account the current work belongs to (a film's project lives in one
# account; its media ids are useless anywhere else). Set by the worker / director per project; None = unbound.
CURRENT_ACCOUNT: contextvars.ContextVar[str | None] = contextvars.ContextVar("flow_account", default=None)
# A media id Flow answered NOT_FOUND for (deleted, or held by another account) is not asked again for this long:
# 23/10 logs had 3767 refresh warnings for 246 such ids, every refresh walking them all, one call each.
DEAD_MEDIA_TTL_S = 6 * 3600
ACCOUNT_NOT_CONNECTED = "ACCOUNT_NOT_CONNECTED"
# Account rotation, step 4 (22/10): a film moved to another account keeps its local project id; Flow knows it under a
# new project id there. {local id: Flow project id in the film's current account}, applied to every call in `_send`.
PROJECT_ALIASES: dict[str, str] = {}

logger = logging.getLogger(__name__)

# Captured from the current Flow image composer. x4 launches independent
# ogiZ0b requests at roughly 0.0s, 0.5s, 1.5s and 2.5s rather than bursting
# all variants at once. The generation work still overlaps after submission.
IMAGE_UI_SUBMIT_OFFSETS_S = (0.0, 0.5, 1.5, 2.5)

# RPC [8] is a transient Flow-side generation rejection seen under image load.
# A short 6s retry was still rejected in live testing, so use one bounded
# cooldown retry rather than hot-looping or multiplying duplicate generations.
# This is FlowKit resilience policy; the current UI was not observed to retry
# automatically after the same failure.
IMAGE_TRANSIENT_RETRY_DELAY_S = 34.0
IMAGE_TRANSIENT_MAX_ATTEMPTS = 2


class FlowClient:
    """Sends commands to Chrome extension via WebSocket."""

    def __init__(self):
        self._dead_media: dict[str, float] = {}   # media id -> when Flow said NOT_FOUND (monotonic)
        self._extension_ws = None  # Active authenticated extension connection
        self._extensions: dict[object, dict] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._pending_ws: dict[str, object] = {}
        self.last_account: str | None = None   # the account of the profile that answered the last request
        self._flow_key: str | None = None
        # Per-operation poll state. `_operation_projects` says which project
        # listing to look a finished media up in; `_operation_media` caches the
        # id once the listing has it, so later rounds skip the listing entirely;
        # `_operation_polls` counts rounds, to keep the listing off most of them.
        self._operation_projects: dict[str, str] = {}
        self._operation_media: dict[str, str] = {}
        self._operation_polls: dict[str, int] = {}
        # FK-LOCAL: NOT_FOUND answers for a media id the listing already gave us.
        # Flow deletes a finished clip its output filter rejects; two in a row
        # mean the job is gone, not slow.
        self._media_not_found: dict[str, int] = {}
        self._generation_slots = asyncio.Semaphore(FLOW_GENERATION_MAX_CONCURRENT)
        self._generation_rate_gate = asyncio.Lock()
        self._generation_last_submit_at = 0.0
        # Google's unusual-activity block is per account (22/10: Hoang blocked must not hold Olya): keyed by the
        # film's account, "" for unbound work. The two attributes below read/write the current account's entry.
        self._unusual_until: dict[str, float] = {}
        self._unusual_streak: dict[str, int] = {}
        self._generation_last_unusual_at: float | None = None
        self._generation_last_unusual_rpc: str | None = None
        # WS stats
        self._ws_connect_count = 0
        self._ws_disconnect_count = 0
        self._ws_connected_at: float | None = None
        self._ws_last_disconnect_at: float | None = None

    def set_extension(self, ws):
        """Called when extension connects via WS."""
        self._extensions[ws] = {
            "connected_at": time.time(),
            "flow_key": None,
            "token_captured_at": None,
            "extension_version": None,
            "flow_url_supported": None,
            "unavailable_until": 0,
        }
        # A new unauthenticated profile must not displace an already
        # authenticated extension. It becomes active after token_captured.
        if self._extension_ws is None:
            self._extension_ws = ws
        self._ws_connect_count += 1
        self._ws_connected_at = time.time()
        logger.info(
            "Extension connected #%d (%d active connection(s)); "
            "waiting for extension_ready/token_captured to sync",
            self._ws_connect_count,
            len(self._extensions),
        )

    def clear_extension(self, ws=None):
        """Called when extension disconnects."""
        disconnected_ws = ws or self._extension_ws
        if disconnected_ws is None:
            return

        self._extensions.pop(disconnected_ws, None)
        self._ws_disconnect_count += 1
        self._ws_last_disconnect_at = time.time()

        # Only cancel requests that were sent through the disconnected socket.
        # Requests owned by other Chrome profiles are still valid.
        disconnected_pending = [
            (req_id, self._pending.get(req_id))
            for req_id, pending_ws in list(self._pending_ws.items())
            if pending_ws is disconnected_ws
        ]
        for req_id, future in disconnected_pending:
            if future is not None and not future.done():
                future.set_exception(ConnectionError("Extension disconnected"))
            self._pending_ws.pop(req_id, None)

        if self._extension_ws is disconnected_ws:
            self._extension_ws = self._select_extension(require_token=True)
            if self._extension_ws is None:
                self._extension_ws = self._select_extension(require_token=False)

        active_session = self._extensions.get(self._extension_ws, {})
        self._flow_key = active_session.get("flow_key")
        logger.warning(
            "Extension disconnected, cancelled %d owned request(s); "
            "%d extension connection(s) remain",
            len(disconnected_pending),
            len(self._extensions),
        )

    def _extension_candidates(self, require_token: bool):
        """Return usable extensions in preferred routing order."""
        now = time.time()
        candidates = []
        for ws, session in self._extensions.items():
            if require_token and not session.get("flow_key"):
                continue
            recency = (
                session.get("token_captured_at")
                if require_token
                else session.get("connected_at")
            )
            candidates.append({
                "ws": ws,
                "available": session.get("unavailable_until", 0) <= now,
                "active": ws is self._extension_ws,
                "recency": recency or 0,
            })

        # Prefer an available active session, then the most recently
        # authenticated alternatives. Temporarily unavailable sessions remain
        # last-resort candidates so a single-profile setup can still recover.
        candidates.sort(
            key=lambda item: (
                item["available"],
                item["active"] and item["available"],
                item["recency"],
            ),
            reverse=True,
        )
        return [item["ws"] for item in candidates]

    def _select_extension(self, require_token: bool):
        """Choose the preferred authenticated or connected extension."""
        candidates = self._extension_candidates(require_token)
        return candidates[0] if candidates else None

    @staticmethod
    def _should_failover(result: dict) -> bool:
        """Return true for profile-local failures that another tab can solve."""
        message = str(result.get("error") or result.get("data") or "").lower()
        return any(marker in message for marker in (
            "no_flow_key",
            "no_flow_tab",
            # Batch path: this profile's Flow tab cannot sign a request — it is
            # signed out, still booting, or Chrome discarded it. Another
            # profile's tab may be perfectly able to.
            "no_at_token",
            "flow_tab_discarded",
            "no current window",
            "extension not connected",
            "extension disconnected",
            "extension_switched",
            # Not quota errors: quota belongs to the account, so another tab of it cannot help, and another
            # account does not hold the film's media (account rotation step 3 marks the account EXHAUSTED instead).
        ))

    def set_flow_key(self, key: str):
        self._flow_key = key
        if self._extension_ws in self._extensions:
            self._extensions[self._extension_ws]["flow_key"] = key
            self._extensions[self._extension_ws]["token_captured_at"] = time.time()

    @property
    def connected(self) -> bool:
        return bool(self._extensions)

    @property
    def _generation_unusual_until(self) -> float:
        return self._unusual_until.get(CURRENT_ACCOUNT.get() or "", 0.0)

    @_generation_unusual_until.setter
    def _generation_unusual_until(self, value: float) -> None:
        self._unusual_until[CURRENT_ACCOUNT.get() or ""] = value

    @property
    def _generation_unusual_streak(self) -> int:
        return self._unusual_streak.get(CURRENT_ACCOUNT.get() or "", 0)

    @_generation_unusual_streak.setter
    def _generation_unusual_streak(self, value: int) -> None:
        self._unusual_streak[CURRENT_ACCOUNT.get() or ""] = value

    def clear_generation_cooldowns(self) -> None:
        self._unusual_until.clear()

    @property
    def generation_guard_status(self) -> dict:
        now = time.monotonic()
        by_account = {a or "(chưa gắn)": round(u - now) for a, u in self._unusual_until.items() if u > now}
        remaining = max(0.0, max(self._unusual_until.values(), default=0.0) - now)
        return {
            "cooldown_active": remaining > 0,
            "cooldown_remaining_s": round(remaining, 3),
            "cooldown_by_account": by_account,
            "last_unusual_activity_at": self._generation_last_unusual_at,
            "last_unusual_activity_rpc": self._generation_last_unusual_rpc,
        }

    @property
    def ws_stats(self) -> dict:
        uptime = None
        if self._ws_connected_at and self.connected:
            uptime = int(time.time() - self._ws_connected_at)
        versions = sorted({
            str(session["extension_version"])
            for session in self._extensions.values()
            if session.get("extension_version")
        })
        flow_url_support = [
            session.get("flow_url_supported")
            for session in self._extensions.values()
            if session.get("flow_url_supported") is not None
        ]
        return {
            "connected": self.connected,
            "active_connections": len(self._extensions),
            "authenticated_connections": sum(
                1 for session in self._extensions.values()
                if session.get("flow_key")
            ),
            "extension_versions": versions,
            "flow_url_supported": all(flow_url_support) if flow_url_support else None,
            "connects": self._ws_connect_count,
            "disconnects": self._ws_disconnect_count,
            "uptime_s": uptime,
        }

    async def handle_message(self, data: dict, websocket=None):
        """Handle incoming message from extension."""
        if data.get("type") == "token_captured":
            key = data.get("flowKey")
            source_ws = websocket or self._extension_ws
            if source_ws is not None and source_ws in self._extensions:
                self._extensions[source_ws]["flow_key"] = key
                self._extensions[source_ws]["token_captured_at"] = time.time()
                self._extension_ws = source_ws
            self._flow_key = key
            logger.info("Flow key captured from extension")
            spawn(self._sync_tier(), name="sync-tier")
            return

        if data.get("type") == "extension_ready":
            source_ws = websocket or self._extension_ws
            version = data.get("extensionVersion")
            flow_supported = data.get("flowUrlSupported")
            if source_ws is not None and source_ws in self._extensions:
                self._extensions[source_ws]["extension_version"] = version
                self._extensions[source_ws]["flow_url_supported"] = flow_supported
            logger.info(
                "Extension ready, flowKey=%s version=%s flow.google.com=%s",
                "yes" if data.get("flowKeyPresent") else "no",
                version or "unknown",
                "yes" if flow_supported is True else "no" if flow_supported is False else "unknown",
            )
            spawn(self._sync_tier(), name="sync-tier")
            if source_ws is not None:
                spawn(self.identify(source_ws), name="identify-profile")
            return

        if data.get("type") == "media_urls_refresh":
            spawn(self._refresh_media_urls(data.get("urls", [])), name="refresh-urls")
            return

        if data.get("type") == "pong":
            return

        if data.get("type") == "ping":
            # Respond to keepalive
            target_ws = websocket or self._extension_ws
            if target_ws:
                await target_ws.send(json.dumps({"type": "pong"}))
            return

        # Response to a pending request
        req_id = data.get("id")
        if req_id and req_id in self._pending:
            if not self._pending[req_id].done():
                self._pending[req_id].set_result(data)
            return

    async def _sync_tier(self):
        """Detect current tier from credits API and update all active projects."""
        if getattr(self, '_sync_in_progress', False):
            return
        self._sync_in_progress = True
        try:
            result = await self.get_credits()
            data = result.get("data", result)
            tier = data.get("userPaygateTier", "PAYGATE_TIER_ONE")
            logger.info("Syncing tier: %s", tier)

            from agent.db import crud
            projects = await crud.list_projects(status="ACTIVE")
            for p in projects:
                if p.get("user_paygate_tier") != tier:
                    await crud.update_project(p["id"], user_paygate_tier=tier)
                    logger.info("Updated project %s tier: %s -> %s",
                                p["id"][:12], p.get("user_paygate_tier"), tier)
        except Exception as e:
            logger.warning("Failed to sync tier: %s", e)
        finally:
            self._sync_in_progress = False

    _UUID_RE = __import__("re").compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    # flow-content.google is where the rewritten frontend serves media from;
    # the other two are the pre-migration hosts, still seen on older media.
    _SAFE_URL_RE = __import__("re").compile(
        r'^https://(storage\.googleapis\.com|lh3\.googleusercontent\.com|flow-content\.google)/')

    async def _refresh_media_urls(self, urls: list[dict]):
        """Update scene/character URLs in DB from fresh TRPC-captured signed URLs.

        Each entry: {mediaId: str, mediaType: 'image'|'video', url: str}
        """
        from agent.db import crud
        from agent.services.event_bus import event_bus

        updated = 0
        for entry in urls:
            media_id = entry.get("mediaId", "")
            media_type = entry.get("mediaType", "")
            url = entry.get("url", "")
            if not media_id or not url:
                continue
            # Validate media_id is UUID and url is from trusted domains
            if not self._UUID_RE.match(media_id):
                logger.warning("Rejected invalid media_id: %s", media_id[:20])
                continue
            if not self._SAFE_URL_RE.match(url):
                logger.warning("Rejected untrusted URL domain for media %s", media_id[:12])
                continue
            if media_type not in ("image", "video"):
                continue

            # Try matching against scenes (check both orientations)
            scenes = await crud.list_scenes_by_media_id(media_id)
            for scene in scenes:
                updates = {}
                if media_type == "image":
                    # Update whichever orientation matches
                    if scene.get("vertical_image_media_id") == media_id:
                        updates["vertical_image_url"] = url
                    if scene.get("horizontal_image_media_id") == media_id:
                        updates["horizontal_image_url"] = url
                elif media_type == "video":
                    if scene.get("vertical_video_media_id") == media_id:
                        updates["vertical_video_url"] = url
                    if scene.get("horizontal_video_media_id") == media_id:
                        updates["horizontal_video_url"] = url
                    if scene.get("vertical_upscale_media_id") == media_id:
                        updates["vertical_upscale_url"] = url
                    if scene.get("horizontal_upscale_media_id") == media_id:
                        updates["horizontal_upscale_url"] = url
                if updates:
                    await crud.update_scene(scene["id"], **updates)
                    updated += 1

            # Try matching against characters
            chars = await crud.list_characters_by_media_id(media_id)
            for char in chars:
                if media_type == "image" and char.get("media_id") == media_id:
                    await crud.update_character(char["id"], reference_image_url=url)
                    updated += 1

        if updated:
            logger.info("Refreshed %d media URLs from TRPC intercept", updated)
            await event_bus.emit("urls_refreshed", {"count": updated})

    async def refresh_project_urls(self, project_id: str) -> dict:
        """Re-sign every stored media url for a project.

        The batch path can do this properly: the media rpc answers a media id
        with a freshly signed url, so we walk the project's scenes and entities
        and refresh each id we hold.
        """
        from agent.db import crud

        # (media_id, kind) -> the scene/character fields it should land in
        targets: dict[tuple[str, str], list[tuple[str, str, str]]] = {}

        def want(media_id, kind, table, row_id, field):
            if media_id and self._UUID_RE.match(media_id):
                targets.setdefault((media_id, kind), []).append((table, row_id, field))

        scenes = []
        for video in await crud.list_videos(project_id):
            scenes.extend(await crud.list_scenes(video["id"]))

        for scene in scenes:
            for prefix in ("vertical", "horizontal"):
                want(scene.get(f"{prefix}_image_media_id"), "image",
                     "scene", scene["id"], f"{prefix}_image_url")
                want(scene.get(f"{prefix}_video_media_id"), "video",
                     "scene", scene["id"], f"{prefix}_video_url")
                want(scene.get(f"{prefix}_upscale_media_id"), "video",
                     "scene", scene["id"], f"{prefix}_upscale_url")
        for char in await crud.get_project_characters(project_id):
            want(char.get("media_id"), "image", "character", char["id"], "reference_image_url")
        # FK-LOCAL: older versions (canvas version strip) show request.output_url
        from agent.services.versions import VIDEO_TYPES
        for req in await crud.list_requests(project_id=project_id, status="COMPLETED"):
            want(req.get("media_id"), "video" if req.get("type") in VIDEO_TYPES else "image",
                 "request", req["id"], "output_url")

        refreshed, dead, now = 0, [], time.monotonic()
        for (media_id, kind), fields in targets.items():
            if now - self._dead_media.get(media_id, -DEAD_MEDIA_TTL_S) < DEAD_MEDIA_TTL_S:
                dead.append(media_id)
                continue
            try:
                urls = await self._batch_media_urls(media_id)
            except Exception as e:
                if _is_not_found(e):
                    self._dead_media[media_id] = now
                    dead.append(media_id)
                else:
                    logger.warning("Refresh failed for media %s: %s", media_id[:12], e)
                continue
            url = urls.video if kind == "video" else urls.image
            if not url:
                continue
            for table, row_id, field in fields:
                if table == "scene":
                    await crud.update_scene(row_id, **{field: url})
                elif table == "request":
                    await crud.set_request_output_url(row_id, url)
                else:
                    await crud.update_character(row_id, **{field: url})
                refreshed += 1

        logger.info("Refreshed %d/%d media urls for project %s (%d gone from Flow, skipped)",
                    refreshed, len(targets), project_id[:12], len(dead))
        return {"refreshed": refreshed, "found": len(targets), "skipped_dead": len(dead)}

    async def _send_to(self, ws, method: str, params: dict, timeout: float = 30) -> dict:
        """One request to one extension connection (no failover): used to ask a profile who it is."""
        if ws not in self._extensions:
            return {"error": "Extension not connected"}
        req_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self._pending[req_id] = future
        self._pending_ws[req_id] = ws
        try:
            await ws.send(json.dumps({"id": req_id, "method": method, "params": params}))
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError:
            return {"error": f"Timeout ({timeout}s) waiting for {method}"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            self._pending.pop(req_id, None)
            self._pending_ws.pop(req_id, None)

    async def identify(self, ws) -> str | None:
        """Ask a connection which Google account its Flow tab uses, and remember it (account rotation, 19/10).
        An extension older than 0.6.0 has no get_account: the connection stays unidentified."""
        from agent.db import account_crud
        if ws in self._extensions:
            self._extensions[ws]["account_checked_at"] = time.monotonic()
        res = await self._send_to(ws, "get_account", {}, timeout=5)
        data = res.get("result", res) if isinstance(res, dict) else {}
        email = (data or {}).get("email")
        if not email or ws not in self._extensions:
            if ws in self._extensions:
                self._extensions[ws]["account"] = None
                self._extensions[ws]["account_error"] = str((data or {}).get("error") or res.get("error") or "no email")
            return None
        self._extensions[ws]["account_error"] = None
        self._extensions[ws]["account"] = email.lower()
        self._extensions[ws]["account_name"] = data.get("name")
        await account_crud.seen(email, data.get("name"))
        return email.lower()

    async def identify_all(self, max_age_s: float = 60) -> None:
        """Ask again the connections not checked in the last max_age_s (a profile may have switched account)."""
        now = time.monotonic()
        stale = [ws for ws, s in self._extensions.items() if now - (s.get("account_checked_at") or -1e9) > max_age_s]
        await asyncio.gather(*(self.identify(ws) for ws in stale), return_exceptions=True)

    def unidentified_reasons(self) -> list[str]:
        return [s.get("account_error") or "chưa hỏi" for s in self._extensions.values() if not s.get("account")]

    def home_account(self) -> str | None:
        """The account a new film belongs to: the one that answered last, else the only identified account connected.
        20/10: a film created right after a restart (nothing answered yet) was left unbound."""
        if self.last_account:
            return self.last_account
        known = [a for a in self.connected_accounts() if a != "?"]
        return known[0] if len(known) == 1 else None

    def connected_accounts(self) -> dict[str, int]:
        """email → number of connected profiles/tabs signed in to it ("?" = an old extension that cannot say)."""
        out: dict[str, int] = {}
        for session in self._extensions.values():
            key = session.get("account") or "?"
            out[key] = out.get(key, 0) + 1
        return out

    async def _send(self, method: str, params: dict, timeout: float = 300) -> dict:
        """Send request to extension and wait for response.

        Always returns a dict. On error, returns {"error": "<reason>"} — callers
        must check result.get("error") or use _is_ws_error() before reading data.
        Never raises; exceptions are caught and returned as error dicts.
        """
        if not self.connected:
            return {"error": "Extension not connected"}

        # No profile needs a bearer any more: batchexecute authenticates in the
        # page with the session cookie. Demanding a flow key here would reject
        # every profile, because none on this path ever captures one.
        extension_candidates = self._extension_candidates(require_token=False)
        account = CURRENT_ACCOUNT.get()
        if account:   # only the profiles signed in to the film's account; failover stays inside that account
            extension_candidates = [ws for ws in extension_candidates
                                    if (self._extensions.get(ws) or {}).get("account") == account]
            if not extension_candidates:
                return {"error": f"{ACCOUNT_NOT_CONNECTED}: tài khoản {account} chưa kết nối — mở Chrome profile "
                                 "đăng nhập tài khoản này (tab Flow + extension FlowKit)."}
        if not extension_candidates:
            return {"error": "Extension not connected"}
        for local, remote in PROJECT_ALIASES.items():
            params = {k: v.replace(local, remote) if isinstance(v, str) else v for k, v in params.items()}

        last_result = {"error": "Extension not connected"}
        for index, extension_ws in enumerate(extension_candidates):
            if extension_ws not in self._extensions:
                continue

            self._extension_ws = extension_ws
            self._flow_key = self._extensions[extension_ws].get("flow_key")
            req_id = str(uuid.uuid4())
            future = asyncio.get_running_loop().create_future()
            self._pending[req_id] = future
            self._pending_ws[req_id] = extension_ws

            try:
                await extension_ws.send(json.dumps({
                    "id": req_id,
                    "method": method,
                    "params": params,
                }))
                last_result = await asyncio.wait_for(future, timeout=timeout)
            except TimeoutError:
                last_result = {"error": f"Timeout ({timeout}s) waiting for {method}"}
            except Exception as e:
                last_result = {"error": str(e)}
            finally:
                self._pending.pop(req_id, None)
                self._pending_ws.pop(req_id, None)

            has_alternative = index + 1 < len(extension_candidates)
            if self._should_failover(last_result) and has_alternative:
                if extension_ws in self._extensions:
                    self._extensions[extension_ws]["unavailable_until"] = (
                        time.time() + 60
                    )
                logger.warning(
                    "Extension profile unavailable for %s; retrying through "
                    "another authenticated profile",
                    method,
                )
                continue

            self.last_account = (self._extensions.get(extension_ws) or {}).get("account")
            return last_result

        return last_result

    # ─── batchexecute transport ──────────────────────────────
    #
    # Flow's rewritten frontend signs every call with the session cookie plus a
    # per-page `at` token, and a generate also carries a single-use reCAPTCHA.
    # None of that can be replayed from here, so the agent builds the envelope
    # and the extension runs it inside a signed-in flow.google.com tab.

    async def batch_rpc(self, rpcid: str, freq: str,
                        captcha_action: str | None = None,
                        match: str | None = None,
                        custom_path: str | None = None,
                        timeout: float = 300) -> dict:
        """Run one batchexecute RPC in the Flow page. Returns the raw body.

        CAPTCHA-bearing image/video submits pass through one process-wide guard
        so direct API callers cannot accidentally bypass the worker limiter.
        Non-generation RPCs (polling/media/project metadata) remain unthrottled.
        """
        params: dict = {"rpcid": rpcid, "freq": freq}
        if captcha_action:
            params["captchaAction"] = captcha_action
        if match:
            params["match"] = match
        if custom_path:
            params["customPath"] = custom_path

        is_generation = captcha_action in {fb.CAPTCHA_IMAGE, fb.CAPTCHA_VIDEO}
        if not is_generation:
            return await self._send("batch_rpc", params, timeout=timeout)

        now = time.monotonic()
        if now < self._generation_unusual_until:
            remaining = max(1, int(self._generation_unusual_until - now + 0.999))
            return {
                "status": 429,
                "error": (
                    "PUBLIC_ERROR_UNUSUAL_ACTIVITY local cooldown active; "
                    f"retry in about {remaining}s"
                ),
            }

        await self._generation_slots.acquire()
        try:
            async with self._generation_rate_gate:
                now = time.monotonic()
                if now < self._generation_unusual_until:
                    remaining = max(1, int(self._generation_unusual_until - now + 0.999))
                    return {
                        "status": 429,
                        "error": (
                            "PUBLIC_ERROR_UNUSUAL_ACTIVITY local cooldown active; "
                            f"retry in about {remaining}s"
                        ),
                    }
                delay = FLOW_GENERATION_MIN_INTERVAL_S - (
                    now - self._generation_last_submit_at
                )
                if delay > 0:
                    await asyncio.sleep(delay)
                self._generation_last_submit_at = time.monotonic()

            result = await self._send("batch_rpc", params, timeout=timeout)
            blob = f"{result.get('error', '')} {result.get('data', '')}"
            is_hijack = "extension_hijack" in blob.lower()
            is_unusual = (
                "PUBLIC_ERROR_UNUSUAL_ACTIVITY" in blob
                or "unusual activity" in blob.lower()
            )
            if is_hijack:
                # x2a trap: the token was poisoned with action
                # "extension_hijack_detected". This is a system-level trap,
                # NOT an account issue — don't apply the long cooldown.
                # Short pause lets the bypass re-initialise on next tab.
                self._generation_unusual_until = max(
                    self._generation_unusual_until,
                    time.monotonic() + 30.0,
                )
                self._generation_last_unusual_at = time.time()
                self._generation_last_unusual_rpc = rpcid
                logger.error(
                    "[HIJACK] extension_hijack_detected — captcha bypass may "
                    "have failed; pausing generation submits for 30s"
                )
                # Tag the result so processor can distinguish it
                if isinstance(result.get("error"), str):
                    result["error"] = f"[HIJACK] {result['error']}"
                else:
                    result["error"] = "[HIJACK] extension_hijack_detected"
            elif is_unusual:
                self._generation_unusual_streak += 1
                pause = FLOW_UNUSUAL_ACTIVITY_COOLDOWN_S * (1.0, 2.5, 5.0)[
                    min(self._generation_unusual_streak, 3) - 1]
                self._generation_unusual_until = max(
                    self._generation_unusual_until, time.monotonic() + pause,
                )
                self._generation_last_unusual_at = time.time()
                self._generation_last_unusual_rpc = rpcid
                logger.warning(
                    "Google unusual-activity block #%d; pausing generation submits for %.0fs",
                    self._generation_unusual_streak, pause,
                )
            elif not result.get("error"):
                self._generation_unusual_streak = 0
            return result
        finally:
            self._generation_slots.release()

    def generation_cooldown_remaining(self) -> float:
        """Seconds until generation submits are allowed again (0 when open)."""
        return max(0.0, self._generation_unusual_until - time.monotonic())

    async def stream_chat(self, prompt: str, project_id: str | None = None, timeout: float = 120) -> dict:
        """Submit a prompt via FlowCreationAgentService/StreamChat."""
        pid = self._batch_project_id(project_id)
        freq = fb.stream_chat_request(prompt, pid)
        return await self.batch_rpc(
            "StreamChat",
            freq,
            captcha_action="CHAT_GENERATION",
            custom_path=fb.STREAM_CHAT_PATH,
            timeout=timeout,
        )

    async def _batch_payload(self, rpcid: str, freq: str,
                             captcha_action: str | None = None,
                             timeout: float = 300):
        """One RPC, unwrapped to its inner payload. Raises on anything else."""
        result = await self.batch_rpc(rpcid, freq, captcha_action, timeout=timeout)
        if result.get("error"):
            raise fb.FlowBatchError(f"{rpcid}: {result['error']}")
        return fb.first_payload(result.get("data") or "", rpcid)

    def _batch_project_id(self, project_id: str) -> str:
        """The Flow project an RPC is scoped to.

        Flow Kit stores the Flow project uuid as the local project id. Public
        direct endpoints resolve project-less work through the persistent
        session-project lease before reaching this lower-level helper. The
        legacy FLOW_PROJECT_ID fallback remains for older internal callers.
        """
        if project_id and self._UUID_RE.match(str(project_id)):
            return str(project_id)
        if FLOW_PROJECT_ID:
            return FLOW_PROJECT_ID
        raise fb.FlowBatchError(
            "NO_FLOW_PROJECT: every batchexecute call is scoped to a Flow project. "
            "Create one in the Flow UI and pin its uuid as FLOW_PROJECT_ID."
        )

    def _batch_image_model(self, override: str | None = None) -> str:
        # Read through the module: PATCH /api/models hot-reloads both of these.
        nickname = _config.DEFAULT_IMAGE_MODEL
        return fb.resolve_image_model(
            override or _config.IMAGE_MODELS.get(nickname) or nickname
        )

    def _batch_video_model(self, tier: str, gen_type: str, aspect_ratio: str) -> str:
        legacy = VIDEO_MODELS.get(tier, {}).get(gen_type, {}).get(aspect_ratio)
        return fb.resolve_video_model(legacy)

    def _remember_operation(self, operation_id: str, project_id: str):
        """Which project an operation belongs to — the listing lookup needs it.

        A poll record usually carries the project id, but old operations decay
        to a bare id, so keep our own note. Bounded: this is a cache, and the
        pinned project is always a workable fallback.
        """
        if not operation_id:
            return
        if len(self._operation_projects) > 512:
            self._operation_projects.clear()
        self._operation_projects[operation_id] = project_id

    # ─── High-Level Batch Methods ────────────────────────────────

    def flow_project_id(self, requested: str | None = None) -> str | None:
        """Validate an explicitly requested Flow project id."""
        if requested and self._UUID_RE.match(requested):
            return requested
        return None

    async def create_project(self, project_title: str, tool_name: str = "PINHOLE") -> dict:
        try:
            result = await self.batch_rpc(
                fb.RPC_CREATE_PROJECT,
                fb.create_project_request(project_title),
                timeout=60,
            )
            if result.get("error"):
                return {"status": result.get("status", 502), "error": result["error"]}
            payload = fb.first_payload(result.get("data") or "", fb.RPC_CREATE_PROJECT)
            pid, title = fb.read_created_project(payload)
            if not self._UUID_RE.match(pid):
                raise fb.FlowBatchError(f"invalid project id returned by Flow: {pid!r}")
            logger.info("Flow project created: %s title=%r", pid, title or project_title)
            return {"status": 200, "data": {"projectId": pid, "title": title or project_title}}
        except Exception as exc:
            return _batch_error(exc)

    async def generate_images(self, prompt: str, project_id: str = None,
                                character_media_ids: list[str] = None,
                                aspect_ratio: str = "IMAGE_ASPECT_RATIO_PORTRAIT",
                                user_paygate_tier: str = "PAYGATE_TIER_TWO",
                                image_model: str = None,
                                count: int = 1,
                                seed: int | None = None,
                                base_media_id: str | None = None) -> dict:
        """Generate image(s).

        ``character_media_ids`` are attached as reference images, which is what
        keeps an entity the same across scenes. Response is shaped like the
        old REST one so the parsers downstream do not have to care which
        transport produced it.
        """

        try:
            if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 4:
                raise ValueError("image count must be an integer from 1 to 4")
            pid = self._batch_project_id(project_id)
            model = self._batch_image_model(image_model)
            refs = list(character_media_ids or []) or None

            async def submit_once(index: int, launch_offset: float = 0.0):
                if launch_offset:
                    await asyncio.sleep(launch_offset)
                request_seed = seed + index * 9973 if seed is not None else None
                freq = fb.image_request(
                    prompt, pid, count=1, aspect=aspect_ratio, seed=request_seed,
                    model=model, ref_media_ids=refs, base_media_id=base_media_id,
                )
                payload = await self._batch_payload(
                    fb.RPC_GEN_IMAGE, freq, fb.CAPTCHA_IMAGE
                )
                generated = fb.read_images(payload)
                if not generated:
                    raise fb.FlowBatchError("Image generation returned no media url")
                return generated[0]

            async def run_wave(indices: list[int]) -> dict[int, object]:
                # Flow's UI starts variants as separate single-image RPCs with a
                # short cadence instead of a burst. Apply the cadence relative
                # to each wave, while Google still performs the generation work
                # concurrently after each request has been accepted.
                tasks = [
                    submit_once(index, IMAGE_UI_SUBMIT_OFFSETS_S[position])
                    for position, index in enumerate(indices)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return dict(zip(indices, results))

            results = await run_wave(list(range(count)))
            retry_indices = [
                index for index, result in results.items()
                if isinstance(result, fb.RpcError)
                and result.rpcid == fb.RPC_GEN_IMAGE
                and result.detail == [8]
            ]
            if retry_indices:
                logger.warning(
                    "Flow image wave had transient [8] for variant(s) %s; "
                    "retrying after %.0fs cooldown once the first wave is fully settled",
                    ",".join(str(i + 1) for i in retry_indices),
                    IMAGE_TRANSIENT_RETRY_DELAY_S,
                )
                await asyncio.sleep(IMAGE_TRANSIENT_RETRY_DELAY_S)
                retried = await run_wave(retry_indices)
                results.update(retried)

            images_by_index = {
                index: result
                for index, result in results.items()
                if not isinstance(result, BaseException)
            }
            failures = {
                index: result
                for index, result in results.items()
                if isinstance(result, BaseException)
            }
            if not images_by_index:
                first_error = failures[min(failures)] if failures else fb.FlowBatchError(
                    "Image generation returned no media url"
                )
                raise first_error

            images = [images_by_index[index] for index in sorted(images_by_index)]

        except Exception as e:
            return _batch_error(e)

        data = {
            "media": [_as_media_record(i) for i in images],
            "requested_count": count,
            "generated_count": len(images),
            "complete": len(images) == count,
        }
        if failures:
            data["failed_variants"] = [
                {"index": index + 1, "error": str(error)}
                for index, error in sorted(failures.items())
            ]
        return {"status": 200, "data": data}

    async def edit_image(self, prompt: str, source_media_id: str,
                          project_id: str,
                          aspect_ratio: str = "IMAGE_ASPECT_RATIO_PORTRAIT",
                          user_paygate_tier: str = "PAYGATE_TIER_ONE",
                          character_media_ids: list[str] = None,
                          image_model: str = None,
                          count: int = 1,
                          seed: int | None = None) -> dict:
        """Edit an image with the source encoded as Flow's BASE_IMAGE input.

        Additional references remain REFERENCE inputs. Sending the source as a
        generic reference conditions a fresh generation; BASE_IMAGE is the wire
        shape the current Flow editor uses for an actual image edit/refine.
        """

        refs = [mid for mid in (character_media_ids or []) if mid != source_media_id]
        return await self.generate_images(
            prompt=prompt,
            project_id=project_id,
            aspect_ratio=aspect_ratio,
            user_paygate_tier=user_paygate_tier,
            character_media_ids=refs,
            image_model=image_model,
            count=count,
            seed=seed,
            base_media_id=source_media_id,
        )

    async def upscale_image(self, media_id: str, project_id: str,
                            resolution: str = "2K") -> dict:
        """Return Flow's synchronous 2K/4K image upscale as base64 JPEG data."""
        try:
            pid = self._batch_project_id(project_id)
            freq = fb.image_upscale_request(media_id, resolution)
            payload = await self._batch_payload(
                fb.RPC_UPSCALE_IMAGE,
                freq,
                fb.CAPTCHA_IMAGE,
                timeout=150,
            )
            encoded = fb.read_upscaled_image(payload)
        except Exception as e:
            return _batch_error(e)
        return {
            "status": 200,
            "data": {
                "media_id": media_id,
                "project_id": pid,
                "resolution": str(resolution).upper(),
                "encodedImage": encoded,
                "contentType": "image/jpeg",
            },
        }

    async def generate_video(self, start_image_media_id: str, prompt: str,
                              project_id: str, scene_id: str,
                              aspect_ratio: str = "VIDEO_ASPECT_RATIO_PORTRAIT",
                              end_image_media_id: str = None,
                              user_paygate_tier: str = "PAYGATE_TIER_TWO") -> dict:
        """Submit an i2v generation. Returns operations for the poller."""

        if end_image_media_id:
            if not FLOW_ALLOW_DEGRADED:
                return {"error": _unsupported(
                    "start+end frame chaining",
                    "the new payload's end-image slot was never captured",
                )}
            logger.warning(
                "Scene %s: dropping end frame %s — chaining is not on the batch path, "
                "running plain i2v because FLOW_ALLOW_DEGRADED=1",
                str(scene_id)[:12], end_image_media_id[:12])

        gen_type = "start_end_frame_2_video" if end_image_media_id else "frame_2_video"
        try:
            pid = self._batch_project_id(project_id)
            freq = fb.video_request(
                prompt, pid, start_image_media_id, aspect=aspect_ratio,
                model=self._batch_video_model(user_paygate_tier, gen_type, aspect_ratio),
            )
            payload = await self._batch_payload(
                fb.RPC_GEN_VIDEO, freq, fb.CAPTCHA_VIDEO, timeout=120)
            operation = fb.read_operation(payload)
        except Exception as e:
            return _batch_error(e)

        self._remember_operation(operation.operation_id, pid)
        return {"status": 200, "data": {"operations": [_as_pending_operation(operation.operation_id)]}}

    async def generate_video_from_references(self, reference_media_ids: list[str],
                                              prompt: str, project_id: str, scene_id: str,
                                              aspect_ratio: str = "VIDEO_ASPECT_RATIO_PORTRAIT",
                                              user_paygate_tier: str = "PAYGATE_TIER_TWO") -> dict:
        """Generate video from multiple reference images (r2v)."""

        if not FLOW_ALLOW_DEGRADED:
            return {"error": _unsupported(
                "reference-to-video (r2v)",
                "its payload was never captured off the new UI",
            )}
        if not reference_media_ids:
            return {"error": "No reference media_ids for r2v"}
        logger.warning(
            "Scene %s: r2v is not on the batch path — running i2v off the first "
            "reference %s because FLOW_ALLOW_DEGRADED=1",
            str(scene_id)[:12], reference_media_ids[0][:12])
        return await self.generate_video(
            start_image_media_id=reference_media_ids[0], prompt=prompt,
            project_id=project_id, scene_id=scene_id, aspect_ratio=aspect_ratio,
            user_paygate_tier=user_paygate_tier,
        )

    async def upscale_video(self, media_id: str, scene_id: str,
                             aspect_ratio: str = "VIDEO_ASPECT_RATIO_PORTRAIT",
                             resolution: str = "VIDEO_RESOLUTION_4K") -> dict:
        """Upscale a video."""
        return {"error": _unsupported(
            "video upscale",
            "no upsampler rpc appears in the new frontend's captures",
        )}

    async def check_video_status(self, operations: list[dict]) -> dict:
        """One poll round for each submitted operation.

        Three signals have to agree before a clip can be downloaded, and they
        arrive out of order:

        * the operation poll says how the job is going — but it can sit at no
          status at all on a job that finished, and a "Media not found."
          complaint on it is survivable rather than fatal;
        * the project listing is what actually gains a media id;
        * the media record serves the poster image first and grows the
          ``/video/`` url in later.

        So an operation only reports SUCCESSFUL once there is a video url.
        Everything short of that is PENDING, and the caller's own poll loop
        owns the timeout.
        """

        out = []
        for entry in operations or []:
            op_id = (entry.get("operation") or {}).get("name") or entry.get("name") or ""
            if not op_id:
                out.append({"operation": {}, "status": "MEDIA_GENERATION_STATUS_FAILED",
                            "error": "operation carried no name"})
                continue
            try:
                out.append(await self._poll_batch_operation(op_id))
            except Exception as e:
                # A hiccup on one poll round costs a round, not the job.
                logger.warning("Operation %s poll failed: %s", op_id[:20], e)
                out.append(_as_pending_operation(op_id, error=str(e)))
        return {"status": 200, "data": {"operations": out}}

    async def _poll_batch_operation(self, operation_id: str) -> dict:
        media_id = self._operation_media.get(operation_id)
        complaint = None

        if not media_id:
            media_id, complaint = await self._find_operation_media(operation_id)
            if not media_id:
                return _as_pending_operation(operation_id, error=complaint)
            logger.info("Matched media_id=%s for op=%s", media_id, operation_id)
            self._operation_media[operation_id] = media_id

        try:
            urls = await self._batch_media_urls(media_id)
        except Exception as e:
            if _is_not_found(e):
                misses = self._media_not_found.get(operation_id, 0) + 1
                self._media_not_found[operation_id] = misses
                if misses >= MEDIA_REMOVED_AFTER:
                    self._operation_media.pop(operation_id, None)
                    self._media_not_found.pop(operation_id, None)
                    return {
                        "operation": {"name": operation_id},
                        "status": "MEDIA_GENERATION_STATUS_FAILED",
                        "error": f"MEDIA_REMOVED: Flow created media {media_id} and then deleted it "
                                 "(usually its output safety filter)",
                    }
                raise
            self._operation_media.pop(operation_id, None)
            raise
        self._media_not_found.pop(operation_id, None)
        if not urls.video:
            # The id landed but the clip is still being written; downloading
            # now would save the poster still instead of the video.
            return _as_pending_operation(operation_id, error=complaint, media_id=media_id)

        # The media id stays cached rather than being cleared here: a batch
        # with several operations re-polls the finished ones alongside the
        # pending ones, and a cleared entry would report them PENDING again.
        # Growth is bounded by _remember_operation.
        return {
            "operation": {
                "name": operation_id,
                "metadata": {"video": {"mediaId": media_id, "fifeUrl": urls.video}},
            },
            "status": "MEDIA_GENERATION_STATUS_SUCCESSFUL",
        }

    async def _find_operation_media(self, operation_id: str) -> tuple[str | None, str | None]:
        """Ask the operation how it is going, then the listing where its media is.

        The listing is the authority — the poll has been seen to never report a
        finished job the listing already knows about — but it is also the
        expensive call, so it is only consulted when the poll says something
        happened, when the poll is unreadable, or every third round regardless.
        """
        rounds = self._operation_polls.get(operation_id, 0) + 1
        self._operation_polls[operation_id] = rounds

        project_id = self._operation_projects.get(operation_id) or FLOW_PROJECT_ID
        if not project_id:
            try:
                from agent.db import crud
                req = await crud.get_request_by_operation_id(operation_id)
                if req and req.get("project_id"):
                    project_id = req["project_id"]
                    self._remember_operation(operation_id, project_id)
            except Exception:
                pass
        complaint = None
        worth_looking = rounds % 3 == 0
        try:
            operation = fb.read_operation(
                await self._batch_payload(
                    fb.RPC_OPERATION, fb.operation_request(operation_id), timeout=60)
            )
            complaint = operation.error
            project_id = operation.project_id or project_id
            if project_id:
                self._remember_operation(operation_id, project_id)
            worth_looking = worth_looking or operation.done or operation.complained
        except Exception as e:
            # An operation that has decayed to a bare id still shows up in the
            # listing, so a failed poll is a reason to look there, not to stop.
            logger.debug("Operation %s poll unreadable (%s), trying the listing",
                         operation_id[:20], e)
            worth_looking = True

        if not worth_looking:
            return None, complaint
        if not project_id:
            return None, "no project id for the listing lookup"
        return await self._media_id_for(operation_id, project_id), complaint

    async def _media_id_for(self, operation_id: str, project_id: str) -> str | None:
        """Find an operation's media id in the project listing.

        Asks the extension for an 800-byte window around the operation id
        rather than the whole listing — that payload is past 17 MB and grows
        with every generation, so anything that ships it whole gets truncated
        and loses roughly half of all lookups.
        """
        result = await self.batch_rpc(
            fb.RPC_PROJECT_MEDIA, fb.project_media_request(project_id),
            match=operation_id, timeout=120,
        )
        if result.get("error"):
            raise fb.FlowBatchError(f"{fb.RPC_PROJECT_MEDIA}: {result['error']}")
        raw = result.get("data") or ""
        media_id = fb.find_media_id_in_text(raw, operation_id)
        if not media_id and raw.lstrip().startswith(")]}"):
            # an extension that cannot filter hands back the whole envelope
            try:
                media_id = fb.find_media_id(
                    fb.first_payload(raw, fb.RPC_PROJECT_MEDIA), operation_id)
            except (fb.FlowBatchError, fb.RpcError, json.JSONDecodeError):
                media_id = None
        return media_id

    async def _batch_media_urls(self, media_id: str) -> "fb.MediaUrls":
        payload = await self._batch_payload(
            fb.RPC_MEDIA, fb.media_request(media_id), timeout=60)
        return fb.read_media_urls(payload, media_id)

    async def get_credits(self) -> dict:
        """Get user credits and tier.

        The new frontend has no captured credits rpc, and the tier no longer
        selects a model — aspect is its own slot and the model names are
        fixed — so on the batch path this answers with the configured default
        rather than pretending to know.
        """
        return {"status": 200, "data": {
            "userPaygateTier": DEFAULT_PAYGATE_TIER,
            "note": "batchexecute path: tier is configured (DEFAULT_PAYGATE_TIER), not fetched",
        }}

    async def validate_media_id(self, media_id: str) -> bool:
        """Check if a mediaId is still valid."""
        result = await self.get_media(media_id)
        status = result.get("status", 500)
        return isinstance(status, int) and status == 200

    async def get_media(self, media_id: str) -> dict:
        """Fetch a media record, which is where a fresh signed url lives."""
        try:
            urls = await self._batch_media_urls(media_id)
        except Exception as e:
            return _batch_error(e)
        if not urls.video and not urls.image:
            return {"status": 404, "error": f"No urls for media {media_id}"}
        data: dict = {}
        if urls.video:
            data["video"] = {"fifeUrl": urls.video}
        if urls.image:
            data["image"] = {"fifeUrl": urls.image}
        return {"status": 200, "data": data}

    async def upload_image(self, image_base64: str, mime_type: str = "image/jpeg",
                            project_id: str = "", file_name: str = "image.jpg") -> dict:
        """Upload an image into the project so it can be used as a reference."""
        try:
            pid = self._batch_project_id(project_id)
            payload = await self._batch_payload(
                fb.RPC_UPLOAD_IMAGE,
                fb.upload_request(image_base64, pid, mime_type, file_name),
                fb.CAPTCHA_IMAGE, timeout=120,
            )
            media_id = fb.read_uploaded_media_id(payload)
        except Exception as e:
            return _batch_error(e)
        return {"status": 200, "data": {"media": {"name": media_id}}, "_mediaId": media_id}

# ─── Response shaping ────────────────────────────────────────
#
# The batch path answers in Flow's positional arrays; everything downstream
# reads the old REST shapes. These put one back on the other so the parsers,
# the poller and the DB writers never learn which transport ran.

_CAPTURE_HINT = "see docs/CAPTURE.md to record its payload off the new UI"

def _unsupported(feature: str, why: str) -> str:
    return f"UNSUPPORTED_ON_BATCH_API: {feature} — {why}; {_CAPTURE_HINT}."


def _batch_error(exc: Exception) -> dict:
    """An exception from the batch path, in the error shape callers expect."""
    return {"status": 502, "error": f"{type(exc).__name__}: {exc}"}


def _as_media_record(image: "fb.GeneratedImage") -> dict:
    """One generated image, in the REST response's `media[]` shape."""
    return {
        "name": image.media_id,
        "image": {"generatedImage": {"mediaId": image.media_id, "fifeUrl": image.url}},
    }


MEDIA_REMOVED_AFTER = 2


def _is_not_found(error: Exception) -> bool:
    """A batchexecute rpc answering gRPC status 5 (NOT_FOUND), e.g. "as29s failed: [5]"."""
    return "failed: [5]" in str(error)


def _as_pending_operation(operation_id: str, error: str | None = None,
                          media_id: str | None = None) -> dict:
    """An operation that has not produced a fetchable clip yet.

    ``error`` is carried, not acted on: a poll complaint is a diagnostic that
    finished jobs also report, so it exists to make a timeout message useful.
    """
    entry: dict = {
        "operation": {"name": operation_id},
        "status": "MEDIA_GENERATION_STATUS_PENDING",
    }
    if media_id:
        entry["operation"]["metadata"] = {"video": {"mediaId": media_id}}
    if error:
        entry["complaint"] = error
    return entry



def _is_ws_error(result: dict) -> bool:
    return bool(result.get("error")) or (isinstance(result.get("status"), int) and result["status"] >= 400)


# Singleton
_client: FlowClient | None = None


def get_flow_client() -> FlowClient:
    global _client
    if _client is None:
        _client = FlowClient()
    return _client
