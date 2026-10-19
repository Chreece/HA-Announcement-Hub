"""AI submissions are durable before preprocessing and never block other jobs."""

from __future__ import annotations

import ast
import asyncio
from collections import deque
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "custom_components" / "announcement_hub" / "manager.py"
).read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
MANAGER = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "AnnouncementManager")


def _method(name, **bindings):
    node = next(n for n in MANAGER.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    namespace = {"asyncio": asyncio, **bindings}
    exec(compile("from __future__ import annotations\n" + ast.unparse(node), name, "exec"), namespace)
    return namespace[name]


class Harness:
    def __init__(self, rewriter):
        self._queue = deque()
        self._running = True
        self.hass = object()
        self._prefetched = []
        self._saved = 0
        self._wake = SimpleNamespace(set=lambda: None)
        self._rewrite = rewriter

    def _prepare_staged_route(self, job):
        job.notify_text = job.text_notify

    def _schedule_prefetch(self, job):
        self._prefetched.append(job.job_id)

    def _schedule_save(self):
        self._saved += 1

    def _notify_update(self):
        pass


def _job(*, mode="normal", raw="Window open"):
    return SimpleNamespace(
        job_id="kitchen-1",
        ai={
            "enabled": True,
            "status": "pending",
            "pending_preprocessing": True,
            "source_tts": None,
            "source_notify": raw,
            "requested_agent_id": "conversation.local",
            "requested_fallback_agent_id": None,
        },
        text_tts=None, text_notify=raw,
        tts_text=None, notify_text=raw,
        routing_mode=mode,
    )


def _run(harness, job):
    handler = _method(
        "_async_rewrite_job",
        async_filter_announcement=harness._rewrite,
        _LOGGER=SimpleNamespace(exception=lambda *_args, **_kw: None),
    )
    return asyncio.run(handler(harness, job))


def test_failed_ai_preserves_original_and_wakes_delivery():
    async def failed(_hass, **_kwargs):
        raise RuntimeError("provider failed")
    h = Harness(failed)
    job = _job()
    h._queue.append(job)
    _run(h, job)
    assert job.notify_text == "Window open"
    assert job.ai["status"] == "fallback_original"
    assert job.ai["failure_reason"] == "internal_error"
    assert job.ai["pending_preprocessing"] is False
    assert h._prefetched == ["kitchen-1"]
    assert h._saved > 0


def test_provider_fallback_result_is_applied_after_queuing():
    async def provider(_hass, **kwargs):
        kwargs["diagnostics"]["status"] = "fallback_original"
        return kwargs["text_tts"], kwargs["text_notify"]
    h = Harness(provider)
    job = _job(mode="room_fallback", raw="Door is open")
    h._queue.append(job)
    _run(h, job)
    assert job.notify_text == "Door is open"
    assert job.text_notify == "Door is open"
    assert job.ai["status"] == "fallback_original"
    assert job.ai["pending_preprocessing"] is False
    assert "source_notify" not in job.ai


def test_successful_ai_rewrite_changes_only_selected_channel():
    async def provider(_hass, **_kwargs):
        return None, "✅ Window open."
    h = Harness(provider)
    job = _job()
    h._queue.append(job)
    _run(h, job)
    assert job.tts_text is None
    assert job.notify_text == "✅ Window open."
    assert job.text_notify == "✅ Window open."


def test_cancelled_ai_request_remains_retryable():
    async def interrupted(_hass, **_kwargs):
        raise asyncio.CancelledError
    h = Harness(interrupted)
    job = _job()
    h._queue.append(job)
    try:
        _run(h, job)
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("Cancellation was swallowed")
    assert job.ai["pending_preprocessing"] is True
    assert job.ai["status"] == "pending"
    assert h._prefetched == []


def test_queue_is_created_before_any_ai_request():
    block = SOURCE[
        SOURCE.index("    async def async_enqueue("):
        SOURCE.index("    async def async_clear_queue(")
    ]
    assert "job = AnnouncementJob.create(" in block
    assert "self._queue.append(job)" in block
    assert "self._schedule_ai_rewrite(job)" in block
    assert "await self._store.async_save(self._serialize())" in block
    assert "await async_filter_announcement(" not in block
    assert block.index("self._queue.append(job)") < block.index("self._schedule_ai_rewrite(job)")
    assert block.index("self._schedule_ai_rewrite(job)") < block.index("await self._store.async_save(self._serialize())")
