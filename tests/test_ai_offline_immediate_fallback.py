"""Offline Ollama must never monopolize Announcement Hub's durable queue."""
from __future__ import annotations

import ast
import asyncio
from collections import deque
from datetime import UTC, datetime, timedelta
import logging
from pathlib import Path
from types import SimpleNamespace

MANAGER = Path(__file__).resolve().parents[1] / "custom_components/announcement_hub/manager.py"
SOURCE = MANAGER.read_text(encoding="utf-8")


def isolated_manager(rewriter=None):
    tree = ast.parse(SOURCE)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == "AnnouncementManager")
    names = {
        "_ai_provider_cooling", "_ai_provider_unavailable",
        "_finish_unavailable_ai", "_fill_ai_slots",
        "_schedule_ai_rewrite", "_async_rewrite_job",
    }
    methods = [n for n in cls.body if isinstance(
        n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    assert {n.name for n in methods} == names
    selected = ast.ClassDef(name="TestManager", bases=[], keywords=[],
                            body=methods, decorator_list=[])
    ns = {"asyncio": asyncio, "datetime": datetime, "UTC": UTC,
          "timedelta": timedelta, "STATE_UNAVAILABLE": "unavailable",
          "DEFAULT_AI_AGENT": "default",
          "_LOGGER": logging.getLogger(__name__),
          "async_filter_announcement": rewriter}
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=[selected], type_ignores=[])), str(MANAGER), "exec"), ns)
    return ns["TestManager"]


def pending_job(index, *, mode="rewrite", agent="conversation.ollama"):
    text = f"Window {index} is open."
    return SimpleNamespace(
        job_id=f"offline-{index}", created_at="2026-11-07T00:00:00+00:00",
        ai={"status": "pending", "pending_preprocessing": True,
            "source_tts": text, "source_notify": text,
            "source": "explicit", "mode": mode,
            "requested_mode": mode, "requested_agent_id": agent,
            "requested_fallback_agent_id": None,
            "requested_generate_title": False},
        routing_mode="normal", text_tts=text, text_notify=text,
        tts_text=None, notify_text=None, title="Alert",
    )


def harness(rewriter=None, *, state="unavailable", service=True):
    manager = isolated_manager(rewriter)()
    manager.hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda entity: (
            SimpleNamespace(state=state) if state is not None else None
        )),
        services=SimpleNamespace(has_service=lambda domain, name: service),
    )
    manager.settings = {"ai_provider_timeout": 0.025}
    manager._ai_tasks = {}
    manager._ai_provider_cooldowns = {}
    manager._ai_provider_orphans = {}
    manager._queue = deque()
    manager._ai_history = deque(maxlen=20)
    manager._running = True
    manager._max_parallel_ai = 2
    manager._wake = SimpleNamespace(set=lambda: None)
    manager._schedule_prefetch = lambda job: None
    manager._fill_prefetch_slots = lambda: None
    manager._schedule_save = lambda: None
    manager._notify_update = lambda: None
    manager._room_lane_keys = lambda job: {job.job_id}
    return manager


def test_unavailable_ollama_releases_entire_queue_despite_full_ai_slots():
    async def check():
        manager = harness(state="unavailable")
        holders = [asyncio.create_task(asyncio.Event().wait())
                   for _ in range(2)]
        manager._ai_tasks.update({f"busy-{i}": task for i, task
                                  in enumerate(holders)})
        jobs = [pending_job(i, mode="generate" if i % 2 else "rewrite")
                for i in range(60)]
        manager._queue.extend(jobs)
        manager._fill_ai_slots()
        assert all(not job.ai["pending_preprocessing"] for job in jobs)
        assert all(job.ai["status"] == "fallback_original" for job in jobs)
        assert all(job.ai["failure_reason"] == "provider_unavailable"
                   for job in jobs)
        assert all(job.notify_text == job.text_notify for job in jobs)
        assert all(job.tts_text == job.text_tts for job in jobs)
        assert all("source_notify" not in job.ai for job in jobs)
        assert len(manager._ai_tasks) == 2  # no additional Ollama calls
        assert len(manager._queue) == 60  # no dropped announcements
        for task in holders:
            task.cancel()
        await asyncio.gather(*holders, return_exceptions=True)

    asyncio.run(check())


def test_missing_entity_or_missing_ai_service_fails_open():
    for state, service in ((None, True), ("unknown", False)):
        manager = harness(state=state, service=service)
        job = pending_job(1)
        manager._queue.append(job)
        manager._schedule_ai_rewrite(job)
        assert job.ai["status"] == "fallback_original"
        assert job.ai["pending_preprocessing"] is False


def test_available_entity_is_not_mistaken_for_offline_ollama():
    manager = harness(state="unknown", service=True)
    assert not manager._ai_provider_unavailable("conversation.ollama")


def test_connection_refused_trips_breaker_for_subsequent_messages():
    calls = 0

    async def failed(_hass, **kwargs):
        nonlocal calls
        calls += 1
        kwargs["diagnostics"].update({
            "status": "fallback_original", "failure_reason": "agent_error",
            "attempts": [{"agent": "conversation.ollama",
                          "outcome": "agent_error"}],
        })
        return kwargs["text_tts"], kwargs["text_notify"]

    async def check():
        manager = harness(failed, state="unknown")
        first = pending_job(1)
        manager._queue.append(first)
        await manager._async_rewrite_job(first)
        assert first.ai["status"] == "fallback_original"
        assert first.ai["failure_reason"] == "agent_error"
        assert calls == 1
        assert manager._ai_provider_cooling("conversation.ollama")
        rest = [pending_job(i) for i in range(2, 30)]
        manager._queue.extend(rest)
        manager._fill_ai_slots()
        assert calls == 1
        assert all(not job.ai["pending_preprocessing"] for job in rest)
        assert all(job.notify_text == job.text_notify for job in rest)

    asyncio.run(check())


def test_hard_deadline_works_even_if_provider_ignores_cancellation():
    async def stuck(_hass, **kwargs):
        try:
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            # Provider takes time to tear down a socket despite cancellation.
            await asyncio.sleep(0.15)
        return "too late", "too late"

    async def check():
        manager = harness(stuck, state="unknown")
        job = pending_job(1)
        manager._queue.append(job)
        started = asyncio.get_running_loop().time()
        await manager._async_rewrite_job(job)
        elapsed = asyncio.get_running_loop().time() - started
        assert elapsed < 0.12, elapsed
        assert job.ai["status"] == "fallback_original"
        assert job.ai["failure_reason"] == "provider_timeout"
        assert job.ai["pending_preprocessing"] is False
        assert job.notify_text == "Window 1 is open."
        assert manager._ai_provider_unavailable("conversation.ollama")
        assert manager._ai_provider_orphans["conversation.ollama"]
        await asyncio.sleep(0.18)
        assert not manager._ai_provider_orphans["conversation.ollama"]

    asyncio.run(check())
