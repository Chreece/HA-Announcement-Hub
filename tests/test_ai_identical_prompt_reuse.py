"""Exact-input, bounded AI reuse: 86-job burst regression without HA services."""

from __future__ import annotations

import ast
import asyncio
from collections import deque
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub"
REUSE = ROOT / "ai_reuse.py"
spec = importlib.util.spec_from_file_location("announcement_hub_ai_reuse_test", REUSE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

SOURCE = (ROOT / "manager.py").read_text(encoding="utf-8")
klass = next(node for node in ast.parse(SOURCE).body
             if isinstance(node, ast.ClassDef) and node.name == "AnnouncementManager")
method = next(node for node in klass.body
              if isinstance(node, ast.AsyncFunctionDef)
              and node.name == "_async_rewrite_job")


def test_exact_fingerprints_invalidate_on_any_generation_context_change():
    base = dict(
        original_tts="Γράψε καλωσόρισμα",
        original_notify="Γράψε καλωσόρισμα",
        requested_agent="ai_task.local",
        fallback_agent=None,
        mode="generate", language="el",
        generate_title=True, prompt_templates={},
        ha_language="el",
    )
    reference = mod.fingerprint(**base)
    assert reference == mod.fingerprint(**base)
    assert "Γράψε" not in reference
    assert len(reference) == 64
    for key, val in (
        ("requested_agent", "ai_task.other"),
        ("fallback_agent", "ai_task.backup"),
        ("mode", "rewrite"),
        ("language", "de"),
        ("generate_title", False),
        ("prompt_templates", {"generate": "more concise"}),
        ("original_notify", "Άλλαξε την ανακοίνωση"),
        ("ha_language", "de"),
    ):
        alternative = dict(base, **{key: val})
        assert mod.fingerprint(**alternative) != reference, key


def test_lru_and_ttl_never_perpetually_store_generated_text(monkeypatch):
    clock = [0.]
    monkeypatch.setattr(mod.time, "monotonic", lambda: clock[0])
    cache = mod.AIResultCache(max_entries=2, ttl_seconds=40)
    result = mod.CachedAIResult("Speech", "Written", "Title", "ai_task.a")
    cache.put("a", result)
    clock[0] += 1
    cache.put("b", result)
    assert cache.get("a") == result
    clock[0] += 1
    cache.put("c", result)
    assert cache.get("b") is None
    assert cache.get("a") == result
    clock[0] += 41
    assert cache.get("a") is None
    cache.clear()
    assert cache.get("c") is None


class Harness:
    def __init__(self):
        self.hass = SimpleNamespace(config=SimpleNamespace(language="el"))
        self.settings = {"ai_prompt_templates": {}}
        self._running = True
        self._queue = deque()
        self._ai_history = deque(maxlen=20)
        self._ai_result_cache = mod.AIResultCache(max_entries=16)
        self.generations = 0
        self.scheduled = []
    def _prepare_staged_route(self, job):
        # Reroute is still per-job and must never inherit a cached recipient.
        job.outputs = job.preferred_areas
        job.notify_text = job.text_notify
    def _schedule_prefetch(self, job):
        self.scheduled.append(job.job_id)
    def _fill_prefetch_slots(self): pass
    def _schedule_save(self): pass
    def _notify_update(self): pass


def announcement(index, *, room="kueche", title_needed=True, prompt="Γράψε καλωσόρισμα"):
    return SimpleNamespace(
        job_id=f"j{index}", created_at="2026-10-31T06:00:00+00:00",
        title="Notification",
        routing_mode="room_fallback", outputs=(), preferred_areas=(room,),
        ai={
            "pending_preprocessing": True,
            "source_tts": prompt,
            "source_notify": prompt,
            "requested_agent_id": "ai_task.local",
            "requested_fallback_agent_id": None,
            "requested_mode": "generate",
            "requested_target_language": "el",
            "requested_generate_title": title_needed,
            "status": "pending",
        },
        text_tts=prompt, text_notify=prompt,
        notify_text=None, tts_text=None,
    )


async def generate(hass, **kwargs):
    h.generations += 1
    kwargs["diagnostics"].update({
        "status": "rewritten", "agent_used": "ai_task.local",
        "attempted": True, "attempts": [],
        "failure_reason": None,
    })
    if kwargs["title_result"] is not None:
        kwargs["title_result"]["title"] = "Θερμό καλωσόρισμα"
    return "Χαίρετε!", "Καλώς ήρθατε!"


scope = {
    "asyncio": asyncio,
    "async_filter_announcement": generate,
    "ai_request_fingerprint": mod.fingerprint,
    "CachedAIResult": mod.CachedAIResult,
    "_LOGGER": SimpleNamespace(exception=lambda *args, **kwargs: None),
}
exec(compile("from __future__ import annotations\n" + ast.unparse(method),
             "isolated AI cache worker", "exec"), scope)
Harness._async_rewrite_job = scope["_async_rewrite_job"]


def test_86_identical_prompts_use_one_generation_but_remain_separate_jobs():
    global h
    h = Harness()
    batch = [
        announcement(i, room="kueche" if i % 2 else "wohnzimmer")
        for i in range(86)
    ]
    h._queue.extend(batch)
    async def go():
        for job in batch:
            await h._async_rewrite_job(job)
    asyncio.run(go())
    assert h.generations == 1
    assert len(h.scheduled) == 86
    assert len(h._ai_history) == 20
    assert all(not j.ai["pending_preprocessing"] for j in batch)
    assert all(j.text_tts == "Χαίρετε!" for j in batch)
    assert all(j.text_notify == "Καλώς ήρθατε!" for j in batch)
    assert all(j.title == "Θερμό καλωσόρισμα" for j in batch)
    assert {tuple(j.outputs) for j in batch} == {("kueche",), ("wohnzimmer",)}
    assert batch[0].ai["status"] == "rewritten"
    assert batch[1].ai["status"] == "reused_cached_generation"
    assert batch[-1].ai["attempts"] == [{"outcome": "cache_reuse"}]


def test_failed_generation_is_not_reused_or_marked_success():
    global h
    h = Harness()
    async def no_provider(hass, **kwargs):
        h.generations += 1
        kwargs["diagnostics"].update({
            "status": "fallback_original",
            "agent_used": None,
            "failure_reason": "agent_error",
            "attempts": [],
        })
        return kwargs["text_tts"], kwargs["text_notify"]
    scope["async_filter_announcement"] = no_provider
    try:
        jobs = [announcement(1), announcement(2)]
        h._queue.extend(jobs)
        async def go():
            for item in jobs:
                await h._async_rewrite_job(item)
        asyncio.run(go())
        assert h.generations == 2
        assert all(j.ai["status"] == "fallback_original" for j in jobs)
        assert all(j.text_notify == "Γράψε καλωσόρισμα" for j in jobs)
    finally:
        scope["async_filter_announcement"] = generate


def test_title_option_and_style_change_never_share_cached_result():
    global h
    h = Harness()
    a, b, c = [announcement(i) for i in range(3)]
    b.ai["requested_generate_title"] = False
    h._queue.extend((a, b, c))
    async def go():
        await h._async_rewrite_job(a)
        await h._async_rewrite_job(b)
        h.settings["ai_prompt_templates"] = {"generate": "different"}
        await h._async_rewrite_job(c)
    asyncio.run(go())
    assert h.generations == 3
