"""Every asynchronous provider wait has a configurable finite deadline."""
from __future__ import annotations
import ast
import asyncio
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/announcement_hub"
MANAGER = (COMPONENT / "manager.py").read_text()
AI = (COMPONENT / "ai_filter.py").read_text()
FLOW = (COMPONENT / "config_flow.py").read_text()
CONST = (COMPONENT / "const.py").read_text()


def test_all_home_assistant_provider_calls_are_bounded():
    tree = ast.parse(MANAGER)
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    provider_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"async_call", "async_add_executor_job"}
        and (node.func.attr == "async_add_executor_job" or
             isinstance(node.func.value, ast.Attribute) and
             node.func.value.attr == "services")
    ]
    assert len(provider_calls) == 11
    for node in provider_calls:
        outer = parents.get(node)
        assert isinstance(outer, ast.Call), ast.unparse(node)[:120]
        assert isinstance(outer.func, ast.Attribute), ast.unparse(node)[:120]
        assert outer.func.attr == "wait_for"
        assert any(kw.arg == "timeout" for kw in outer.keywords)


def test_end_to_end_delivery_render_and_ai_have_bounded_waits():
    assert "await asyncio.wait_for(\n                self._async_process_job(job)," in MANAGER
    assert "CONF_DELIVERY_ATTEMPT_TIMEOUT" in MANAGER
    assert "tts.async_get_media_source_audio(self.hass, media_source_id)" in MANAGER
    assert '"tts_render_timeout", 120.0' in MANAGER
    assert "provider_timeout_seconds=float(" in MANAGER
    assert "provider_timeout = float(" in AI
    assert AI.count("timeout=provider_timeout") == 3
    for value in (
        "CONF_AI_PROVIDER_TIMEOUT", "CONF_SERVICE_CALL_TIMEOUT",
        "CONF_TTS_RENDER_TIMEOUT", "CONF_DELIVERY_ATTEMPT_TIMEOUT",
        "CONF_SLEEP_ENTRY_GRACE_SECONDS",
    ):
        assert value in CONST
        assert value in FLOW


def test_failed_rewrite_without_ai_delivers_untouched_original():
    spec = importlib.util.spec_from_file_location("bounded_ai_test", COMPONENT / "ai_filter.py")
    assert spec and spec.loader
    ai = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ai)

    class OfflineServices:
        async def async_call(self, *args, **kwargs):
            await asyncio.sleep(0.2)
            return {}

    class Hass:
        services = OfflineServices()

    async def check():
        original = ("Door open", "🚪 Door open")
        diagnostic = {}
        result = await ai.async_filter_announcement(
            Hass(),
            text_tts=original[0],
            text_notify=original[1],
            agent_id="conversation.offline",
            diagnostics=diagnostic,
            provider_timeout_seconds=0.01,
        )
        assert result == original
        assert diagnostic["status"] == "fallback_original"
        assert diagnostic["failure_reason"] == "provider_timeout"

    asyncio.run(check())


def test_failed_generation_never_becomes_spoken_instructions():
    src = MANAGER
    assert 'ai.get("requested_mode") == "generate" and ai.get("status") == "fallback_original"' in src
    assert 'ai["pending_preprocessing"] = True' in src
    assert 'ai["status"] = "waiting_for_ai"' in src


def test_fallback_keeps_undelivered_jobs_and_respects_allowed_routes():
    assert "def _requeue_undelivered_job(" in MANAGER
    assert "if job.routing_mode == \"room_fallback\":" in MANAGER
    assert "self._requeue_undelivered_stage(job, reason)" in MANAGER
    assert '"selected outputs did not deliver"' in MANAGER
    assert 'job.status = "completed_with_errors"' in MANAGER
