"""23/10 code check (ruff F821): FlowProvider named KIND_AUDIO without importing it — an audio job sent to Flow
crashed with NameError instead of the clear "not supported" answer."""
from agent.sdk.services.flow_provider import FlowProvider
from agent.sdk.services.provider_base import KIND_AUDIO, ProviderJob


async def test_an_audio_job_gets_a_clear_answer_not_a_crash():
    out = await FlowProvider(client=None).run(ProviderJob(job_id="j1", kind=KIND_AUDIO, prompt="hello"))
    assert "not supported" in out["error"]


def test_the_worker_edit_call_reaches_the_real_edit_not_the_queue_helper():
    """23/10 code check (ruff F811): a second edit_character_image (a queue helper) silently replaced the real one,
    so the worker's EDIT_CHARACTER_IMAGE call raised TypeError on job_id."""
    import inspect

    from agent.sdk.services.operations import OperationService
    params = inspect.signature(OperationService.edit_character_image).parameters
    assert {"char", "job_id", "provider"} <= set(params)
