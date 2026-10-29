import time
"""Unit tests for agent/worker/processor.py — heavy mocking of crud, flow_client, operations."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.worker.processor import (
    _is_already_completed,
    _mark_scene_failed,
    _handle_failure,
)
from agent.config import MAX_RETRIES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_req(
    req_type="GENERATE_IMAGE",
    scene_id="scene-001",
    orientation="VERTICAL",
    retry_count=0,
    rid="aaaaaaaa-bbbb-cccc-dddd-000000000001",
    character_id=None,
    **extra,
):
    d = {
        "id": rid,
        "type": req_type,
        "scene_id": scene_id,
        "character_id": character_id,
        "orientation": orientation,
        "retry_count": retry_count,
        "project_id": "proj-001",
        "video_id": "video-001",
    }
    d.update(extra)
    return d


# ---------------------------------------------------------------------------
# _is_already_completed
# ---------------------------------------------------------------------------

class TestIsAlreadyCompleted:
    @pytest.mark.asyncio
    async def test_returns_true_when_vertical_image_completed(self, sample_scene_row):
        """Should return True when vertical_image_status is COMPLETED."""
        req = make_req(req_type="GENERATE_IMAGE", scene_id="scene-001")
        # sample_scene_row has vertical_image_status = "COMPLETED"
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.get_scene = AsyncMock(return_value=sample_scene_row)
            result = await _is_already_completed(req, "VERTICAL")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_vertical_image_pending(self, sample_scene_row):
        """Should return False when vertical_image_status is PENDING."""
        pending_scene = {**sample_scene_row, "vertical_image_status": "PENDING"}
        req = make_req(req_type="GENERATE_IMAGE", scene_id="scene-001")
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.get_scene = AsyncMock(return_value=pending_scene)
            result = await _is_already_completed(req, "VERTICAL")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_generate_character_image_without_media_id(self):
        """GENERATE_CHARACTER_IMAGE should return False if character has no media_id."""
        req = make_req(req_type="GENERATE_CHARACTER_IMAGE", character_id="char-001")
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.get_character = AsyncMock(return_value={"id": "char-001", "media_id": None})
            result = await _is_already_completed(req, "VERTICAL")
        assert result is False
        mock_crud.get_character.assert_called_once_with("char-001")

    @pytest.mark.asyncio
    async def test_returns_true_for_generate_character_image_with_media_id(self):
        """GENERATE_CHARACTER_IMAGE should return True if character already has media_id."""
        req = make_req(req_type="GENERATE_CHARACTER_IMAGE", character_id="char-001")
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.get_character = AsyncMock(return_value={"id": "char-001", "media_id": "uuid-1234"})
            result = await _is_already_completed(req, "VERTICAL")
        assert result is True
        mock_crud.get_character.assert_called_once_with("char-001")

    @pytest.mark.asyncio
    async def test_returns_false_when_no_scene_id(self):
        """If scene_id is missing, should return False without querying DB."""
        req = make_req(req_type="GENERATE_IMAGE", scene_id=None)
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.get_scene = AsyncMock()
            result = await _is_already_completed(req, "VERTICAL")
        assert result is False
        mock_crud.get_scene.assert_not_called()

    @pytest.mark.asyncio
    async def test_edit_image_never_skipped_even_when_image_completed(self, sample_scene_row):
        """EDIT_IMAGE should always run — it replaces the existing image."""
        req = make_req(req_type="EDIT_IMAGE", scene_id="scene-001")
        # sample_scene_row has vertical_image_status = "COMPLETED"
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.get_scene = AsyncMock(return_value=sample_scene_row)
            result = await _is_already_completed(req, "VERTICAL")
        assert result is False


# ---------------------------------------------------------------------------
# _mark_scene_failed
# ---------------------------------------------------------------------------

class TestMarkSceneFailed:
    @pytest.mark.asyncio
    async def test_sets_vertical_image_status_failed_for_generate_image(self):
        req = make_req(req_type="GENERATE_IMAGE", scene_id="scene-001", orientation="VERTICAL")
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.update_scene = AsyncMock()
            await _mark_scene_failed(req)
        mock_crud.update_scene.assert_awaited_once_with("scene-001", vertical_image_status="FAILED")

    @pytest.mark.asyncio
    async def test_sets_vertical_video_status_failed_for_generate_video(self):
        req = make_req(req_type="GENERATE_VIDEO", scene_id="scene-001", orientation="VERTICAL")
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.update_scene = AsyncMock()
            await _mark_scene_failed(req)
        mock_crud.update_scene.assert_awaited_once_with("scene-001", vertical_video_status="FAILED")

    @pytest.mark.asyncio
    async def test_sets_vertical_upscale_status_failed_for_upscale_video(self):
        req = make_req(req_type="UPSCALE_VIDEO", scene_id="scene-001", orientation="VERTICAL")
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.update_scene = AsyncMock()
            await _mark_scene_failed(req)
        mock_crud.update_scene.assert_awaited_once_with("scene-001", vertical_upscale_status="FAILED")

    @pytest.mark.asyncio
    async def test_no_update_when_no_scene_id(self):
        req = make_req(req_type="GENERATE_IMAGE", scene_id=None)
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.update_scene = AsyncMock()
            await _mark_scene_failed(req)
        mock_crud.update_scene.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_failure
# ---------------------------------------------------------------------------

class TestHandleFailure:
    @pytest.mark.asyncio
    async def test_retries_when_under_max_retries(self):
        """When retry_count+1 < MAX_RETRIES, request should go back to PENDING."""
        req = make_req(retry_count=0)
        rid = req["id"]
        result = {"error": "timeout"}

        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.update_request = AsyncMock()
            mock_crud.update_scene = AsyncMock()
            await _handle_failure(rid, req, result)

        mock_crud.update_request.assert_awaited_once()
        call_kwargs = mock_crud.update_request.call_args
        assert call_kwargs[0][0] == rid
        assert call_kwargs[1]["status"] == "PENDING"
        assert call_kwargs[1]["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_marks_failed_when_at_max_retries(self):
        """When retry_count+1 >= MAX_RETRIES, request + scene should be marked FAILED."""
        req = make_req(req_type="GENERATE_IMAGE", scene_id="scene-001", retry_count=MAX_RETRIES - 1)
        rid = req["id"]
        result = {"error": "permanent failure"}

        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.update_request = AsyncMock()
            mock_crud.update_scene = AsyncMock()
            await _handle_failure(rid, req, result)

        mock_crud.update_request.assert_awaited_once()
        call_kwargs = mock_crud.update_request.call_args
        assert call_kwargs[0][0] == rid
        assert call_kwargs[1]["status"] == "FAILED"
        # Scene should also be marked failed
        mock_crud.update_scene.assert_awaited_once_with("scene-001", vertical_image_status="FAILED")

    @pytest.mark.asyncio
    async def test_unusual_activity_waits_out_the_pause(self):
        """A Google block puts the request back in the queue behind the pause, counting one attempt."""
        req = make_req(req_type="GENERATE_VIDEO", scene_id="scene-001", retry_count=0)
        rid = req["id"]
        result = {"error": "reCAPTCHA evaluation failed [PUBLIC_ERROR_UNUSUAL_ACTIVITY]"}
        retry_after = {}

        with patch("agent.worker.processor.crud") as mock_crud, \
             patch("agent.worker.processor._flow_cooldown_s", return_value=120.0):
            mock_crud.update_request = AsyncMock()
            mock_crud.update_scene = AsyncMock()
            await _handle_failure(rid, req, result, retry_after)

        kw = mock_crud.update_request.call_args[1]
        assert kw["status"] == "PENDING" and kw["retry_count"] == 1
        assert retry_after[rid] >= time.time() + 120
        mock_crud.update_scene.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_local_pause_does_not_count_an_attempt(self):
        req = make_req(req_type="GENERATE_CHARACTER_IMAGE", retry_count=1)
        result = {"error": "FlowBatchError: ogiZ0b: PUBLIC_ERROR_UNUSUAL_ACTIVITY local cooldown active; retry in about 90s"}
        with patch("agent.worker.processor.crud") as mock_crud, \
             patch("agent.worker.processor._flow_cooldown_s", return_value=90.0):
            mock_crud.update_request = AsyncMock()
            await _handle_failure(req["id"], req, result, {})
        kw = mock_crud.update_request.call_args[1]
        assert kw["status"] == "PENDING" and kw["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_page_captcha_not_loaded_stops_the_whole_queue(self):
        """'Invalid site key or not loaded' only clears when the user reloads Flow: fail now, and fail the queue."""
        req = make_req(req_type="GENERATE_CHARACTER_IMAGE", scene_id=None, character_id="c1", retry_count=1)
        result = {"error": "FlowBatchError: ogiZ0b: CAPTCHA_FAILED: Invalid site key or not loaded in api.js: 6Lc"}
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.update_request = AsyncMock()
            mock_crud.update_scene = AsyncMock()
            mock_crud.list_pending_requests = AsyncMock(return_value=[make_req(rid="q1"), make_req(rid="q2")])
            await _handle_failure(req["id"], req, result, {})
        calls = {c[0][0]: c[1] for c in mock_crud.update_request.call_args_list}
        assert set(calls) == {req["id"], "q1", "q2"}
        assert all(kw["status"] == "FAILED" and "Tải lại tab flow.google.com" in kw["error_message"]
                   for kw in calls.values())

    @pytest.mark.asyncio
    async def test_page_captcha_first_reloads_the_flow_tab_and_retries_once(self):
        req = make_req(req_type="GENERATE_CHARACTER_IMAGE", scene_id=None, character_id="c1", retry_count=0)
        result = {"error": "CAPTCHA_FAILED: Invalid site key or not loaded in api.js: 6Lc"}
        retry_after = {}
        with patch("agent.worker.processor.crud") as mock_crud, \
             patch("agent.worker.processor._reload_flow_tab", AsyncMock(return_value=True)) as reload:
            mock_crud.update_request = AsyncMock()
            mock_crud.list_pending_requests = AsyncMock(return_value=[make_req(rid="q1")])
            await _handle_failure(req["id"], req, result, retry_after)
        reload.assert_awaited_once()
        kw = mock_crud.update_request.call_args[1]
        assert kw["status"] == "PENDING" and kw["retry_count"] == 1
        assert retry_after[req["id"]] > time.time() + 20
        mock_crud.list_pending_requests.assert_not_awaited()   # the queue keeps waiting

    @pytest.mark.asyncio
    async def test_page_captcha_stops_the_queue_when_the_tab_cannot_be_reloaded(self):
        req = make_req(req_type="GENERATE_CHARACTER_IMAGE", scene_id=None, character_id="c1", retry_count=0)
        result = {"error": "CAPTCHA_FAILED: Invalid site key or not loaded in api.js: 6Lc"}
        with patch("agent.worker.processor.crud") as mock_crud, \
             patch("agent.worker.processor._reload_flow_tab", AsyncMock(return_value=False)):
            mock_crud.update_request = AsyncMock()
            mock_crud.update_scene = AsyncMock()
            mock_crud.list_pending_requests = AsyncMock(return_value=[])
            await _handle_failure(req["id"], req, result, {})
        assert mock_crud.update_request.call_args[1]["status"] == "FAILED"

    @pytest.mark.asyncio
    async def test_ordinary_captcha_gives_up_after_three_tries(self):
        req = make_req(retry_count=2)
        result = {"error": "CAPTCHA_FAILED: token expired"}
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.update_request = AsyncMock()
            mock_crud.update_scene = AsyncMock()
            await _handle_failure(req["id"], req, result, {})
        assert mock_crud.update_request.call_args[1]["status"] == "FAILED"

    @pytest.mark.asyncio
    async def test_unusual_activity_fails_after_max_attempts(self):
        req = make_req(req_type="GENERATE_VIDEO", scene_id="scene-001", retry_count=2)
        result = {"error": "reCAPTCHA evaluation failed [PUBLIC_ERROR_UNUSUAL_ACTIVITY]"}
        with patch("agent.worker.processor.crud") as mock_crud, \
             patch("agent.worker.processor._flow_cooldown_s", return_value=600.0):
            mock_crud.update_request = AsyncMock()
            mock_crud.update_scene = AsyncMock()
            await _handle_failure(req["id"], req, result, {})
        kw = mock_crud.update_request.call_args[1]
        assert kw["status"] == "FAILED" and "3 times" in kw["error_message"]
        mock_crud.update_scene.assert_awaited_once_with("scene-001", vertical_video_status="FAILED")

    @pytest.mark.asyncio
    async def test_extracts_error_message_from_nested_data(self):
        """Error message extraction from data.error.message should work."""
        req = make_req(retry_count=MAX_RETRIES - 1)
        rid = req["id"]
        result = {
            "data": {
                "error": {
                    "code": 403,
                    "message": "caller does not have permission",
                }
            }
        }

        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.update_request = AsyncMock()
            mock_crud.update_scene = AsyncMock()
            await _handle_failure(rid, req, result)

        call_kwargs = mock_crud.update_request.call_args
        assert "caller does not have permission" in call_kwargs[1]["error_message"]


class TestNoMediaCreated:
    """Flow accepted the job but never created media (policy block) — re-polling cannot help."""

    @pytest.mark.asyncio
    async def test_no_media_created_fails_once_without_retry(self):
        req = make_req(req_type="GENERATE_VIDEO_REFS", scene_id="scene-001", retry_count=0)
        result = {"error": "NO_MEDIA_CREATED: Flow accepted the job but created no media in 420s"}
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.update_request = AsyncMock()
            mock_crud.update_scene = AsyncMock()
            mock_crud.get_scene = AsyncMock(return_value={"id": "scene-001"})
            await _handle_failure(req["id"], req, result)
        kw = mock_crud.update_request.call_args[1]
        assert kw["status"] == "FAILED"


@pytest.mark.asyncio
async def test_poll_timeout_with_media_never_found_reports_no_media_created(monkeypatch):
    from agent.sdk.services import flow_provider

    class Client:
        async def check_video_status(self, ops):
            return {"data": {"operations": [{"operation": {"name": "op1"},
                                             "status": "MEDIA_GENERATION_STATUS_PENDING",
                                             "complaint": "Media not found."}]}}

    async def no_sleep(_):
        return None
    monkeypatch.setattr(flow_provider.asyncio, "sleep", no_sleep)
    out = await flow_provider._poll_operations(Client(), [{"operation": {"name": "op1"}}], timeout=30)
    assert out["error"].startswith("NO_MEDIA_CREATED")
    assert "policy" in out["error"]


class TestMediaRemoved:
    """Flow deleted the finished clip (output filter): resubmit once as a NEW job, then fail."""

    async def _fail(self, retry_count):
        req = make_req(req_type="GENERATE_VIDEO_REFS", scene_id="scene-001", retry_count=retry_count)
        result = {"error": "MEDIA_REMOVED: Flow created media m1 and then deleted it"}
        with patch("agent.worker.processor.crud") as mock_crud:
            mock_crud.update_request = AsyncMock()
            mock_crud.update_scene = AsyncMock()
            mock_crud.get_scene = AsyncMock(return_value={"id": "scene-001"})
            await _handle_failure(req["id"], req, result)
        return mock_crud.update_request.call_args[1]

    @pytest.mark.asyncio
    async def test_first_removal_resubmits_with_the_dead_operation_cleared(self):
        kw = await self._fail(0)
        assert kw["status"] == "PENDING"
        assert kw["request_id"] is None
        assert kw["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_second_removal_fails(self):
        kw = await self._fail(1)
        assert kw["status"] == "FAILED"


@pytest.mark.asyncio
async def test_a_failed_operation_reports_its_own_error(monkeypatch):
    from agent.sdk.services import flow_provider

    class Client:
        async def check_video_status(self, ops):
            return {"data": {"operations": [{"operation": {"name": "op1"},
                                             "status": "MEDIA_GENERATION_STATUS_FAILED",
                                             "error": "MEDIA_REMOVED: gone"}]}}

    async def no_sleep(_):
        return None
    monkeypatch.setattr(flow_provider.asyncio, "sleep", no_sleep)
    out = await flow_provider._poll_operations(Client(), [{"operation": {"name": "op1"}}], timeout=30)
    assert out["error"] == "MEDIA_REMOVED: gone"
