from agent.services import flow_batch as fb

LISTING = ('[\\"0de164ec-9806-45fb-b7f6-1784c16436fb\\",null,null,[\\"Woman placing terracotta pot on …\\",'
           '[1792117431,302993000],null,null,\\"097a4b96-94c7-4532-8773-caa2e3d53120\\",'
           '\\"A6E8E74F-2BB2-44B4-B9DD-CF5DD82F7193\\",[1792117441,339058000]],'
           '\\"4217d08b-477f-4943-a09c-e2d08c739ad1\\"]')


def test_client_ids_are_stable_per_request_and_uppercase():
    a, b = fb.submit_client_ids("req-1"), fb.submit_client_ids("req-1")
    assert a == b and len(set(a)) == 3 and all(x == x.upper() for x in a)
    assert fb.submit_client_ids("req-2") != a


def test_find_media_by_client_id_reads_op_and_media():
    assert fb.find_media_by_client_id(LISTING, "a6e8e74f-2bb2-44b4-b9dd-cf5dd82f7193") == (
        "0de164ec-9806-45fb-b7f6-1784c16436fb", "097a4b96-94c7-4532-8773-caa2e3d53120")
    assert fb.find_media_by_client_id(LISTING, "FFFFFFFF-2BB2-44B4-B9DD-CF5DD82F7193") is None


def test_r2v_payload_carries_the_given_client_ids():
    ids = fb.submit_client_ids("req-1")
    freq = fb.omni_reference_video_request("p", "proj", ["m1"], duration_s=10, client_ids=ids)
    assert all(i in freq for i in ids)


from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402

from agent.sdk.services import flow_provider as fp  # noqa: E402
from agent.sdk.services.provider_base import KIND_VIDEO, ProviderJob  # noqa: E402


def _refs_job(rid):
    return ProviderJob(job_id="j", kind=KIND_VIDEO, prompt="p", orientation="VERTICAL",
                       extra={"project_id": "p1", "scene_id": "s1", "request_id": rid, "ref_media_ids": ["m1"],
                              "model_family": "omni_flash", "aspect": "VIDEO_ASPECT_RATIO_PORTRAIT"})


def _client(listing):
    c = MagicMock()
    c._batch_project_id = lambda pid: pid
    c.batch_rpc = AsyncMock(return_value={"data": listing})
    return c


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_count", [1])
async def test_retry_adopts_clip_flow_already_made(retry_count):
    rid = "req-dup"
    cid = fb.submit_client_ids(rid)[0]
    listing = LISTING.replace("A6E8E74F-2BB2-44B4-B9DD-CF5DD82F7193", cid)
    submit = AsyncMock()
    with patch.object(fp.crud, "get_request", AsyncMock(return_value={"request_id": None, "retry_count": retry_count})), \
         patch.object(fp.crud, "update_request", AsyncMock()) as upd, \
         patch.object(fp, "generate_omni_flash_video", submit), \
         patch.object(fp, "_remember_op", AsyncMock()), \
         patch.object(fp, "_poll_operations", AsyncMock(return_value={"ok": 1})):
        assert await fp.FlowProvider(_client(listing))._run_video_refs(_refs_job(rid)) == {"ok": 1}
    submit.assert_not_called()
    upd.assert_awaited_with(rid, request_id="0de164ec-9806-45fb-b7f6-1784c16436fb")


@pytest.mark.asyncio
async def test_first_submit_skips_the_lookup_and_sends_stable_ids():
    rid = "req-new"
    client = _client("")
    ok = {"data": {"operations": [{"operation": {"name": "op1"}, "status": "MEDIA_GENERATION_STATUS_PENDING"}]}}
    with patch.object(fp.crud, "get_request", AsyncMock(return_value={"request_id": None, "retry_count": 0})), \
         patch.object(fp.crud, "update_request", AsyncMock()), \
         patch.object(fp, "generate_omni_flash_video", AsyncMock(return_value=ok)) as submit, \
         patch.object(fp, "_remember_op", AsyncMock()), \
         patch.object(fp, "_poll_operations", AsyncMock(return_value={"ok": 1})):
        await fp.FlowProvider(client)._run_video_refs(_refs_job(rid))
    client.batch_rpc.assert_not_called()
    assert submit.await_args.kwargs["client_ids"] == fb.submit_client_ids(rid)
    fp._attempted.discard(rid)


@pytest.mark.asyncio
async def test_lookup_failure_never_resubmits():
    rid = "req-err"
    client = _client("")
    client.batch_rpc = AsyncMock(return_value={"error": "bridge down"})
    with patch.object(fp.crud, "get_request", AsyncMock(return_value={"request_id": None, "retry_count": 2})), \
         patch.object(fp, "generate_omni_flash_video", AsyncMock()) as submit:
        out = await fp.FlowProvider(client)._run_video_refs(_refs_job(rid))
    assert "error" in out and not submit.called
