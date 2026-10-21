"""Concurrent room delivery: executable FIFO, isolation and burst-safety tests."""

from __future__ import annotations

import ast
import asyncio
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

SOURCE = (Path(__file__).resolve().parents[1] / "custom_components"
          / "announcement_hub" / "manager.py").read_text(encoding="utf-8")
klass = next(n for n in ast.parse(SOURCE).body
             if isinstance(n, ast.ClassDef) and n.name == "AnnouncementManager")


def install(cls, name):
    node = next(n for n in klass.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == name)
    ns = {"asyncio": asyncio, "UTC": UTC, "datetime": datetime,
          "TimeoutError": TimeoutError, "DOMAIN": "announcement_hub"}
    exec(compile("from __future__ import annotations\n" + ast.unparse(node),
                 "room FIFO test", "exec"), ns)
    setattr(cls, name, ns[name])


def job(job_id, room, *, ready=True, ai=False, notify=None, snapcast=False):
    return SimpleNamespace(
        job_id=job_id, created_at=f"2026-10-21T00:00:{int(job_id[1:]):02d}+00:00",
        preferred_areas=(room,) if room else (), outputs=(room,) if room else (),
        notify_outputs=(notify,) if notify else (),
        notify_output_areas={notify: room} if notify else {},
        room_tts_players=(), room_tts_player_areas={},
        companion_tts_entries=(), companion_tts_entry_areas={},
        snapcast_clients=("snapcast",) if snapcast else (),
        server_tts_enabled=snapcast, tts_text="Speak" if snapcast else None,
        notify_text="Message" if notify else None,
        routing_mode="normal", routing_retry_after=None,
        ai={"pending_preprocessing": ai}, ready=ready,
    )


class Scheduler:
    def __init__(self, jobs=(), active=()):
        self._queue = deque(jobs)
        self._active_jobs = {j.job_id: j for j in active}

    def _job_runnable_now(self, item):
        return item.ready

    def _staged_route_ready(self, item):
        return item.ready


for name in ("_room_lane_keys", "_delivery_lane_keys", "_next_runnable_job"):
    install(Scheduler, name)


def test_ai_head_reserves_own_room_without_blocking_another_room():
    first = job("j1", "kitchen", ai=True)
    second = job("j2", "kitchen")
    third = job("j3", "bedroom")
    h = Scheduler((first, second, third))
    assert h._next_runnable_job() is third
    first.ai["pending_preprocessing"] = False
    assert h._next_runnable_job() is first


def test_busy_room_does_not_block_ready_other_room():
    busy = job("j1", "kitchen")
    duplicate = job("j2", "kitchen")
    independent = job("j3", "bathroom")
    h = Scheduler((duplicate, independent), (busy,))
    assert h._next_runnable_job() is independent
    h._active_jobs.clear()
    assert h._next_runnable_job() is duplicate


def test_unavailable_old_room_head_blocks_overtake_only_in_that_room():
    first = job("j1", "bedroom", ready=False)
    duplicate = job("j2", "bedroom")
    unrelated = job("j3", "office")
    h = Scheduler((first, duplicate, unrelated))
    assert h._next_runnable_job() is unrelated
    first.ready = True
    assert h._next_runnable_job() is first


def test_shared_output_is_not_used_concurrently_by_different_rooms():
    first = job("j1", "kitchen", notify="entity:notify.shared")
    duplicate = job("j2", "bathroom", notify="entity:notify.shared")
    separate = job("j3", "office", notify="entity:notify.other")
    h = Scheduler((duplicate, separate), (first,))
    assert h._next_runnable_job() is separate


def test_global_snapcast_source_is_exclusive_even_across_rooms():
    first = job("j1", "kitchen", snapcast=True)
    second = job("j2", "bedroom", snapcast=True)
    third = job("j3", "office")
    h = Scheduler((second, third), (first,))
    assert h._next_runnable_job() is third


class WorkerHarness(Scheduler):
    def __init__(self, jobs):
        super().__init__(jobs)
        self._running = True
        self._wake = asyncio.Event()
        self._current = None
        self._delivery_tasks = {}
        self._held_snapcast_snapshot = None
        self._max_parallel_deliveries = 4
        self._started = []
        self._completed = []
        self._gates = {j.job_id: asyncio.Event() for j in jobs}
        self.entry = SimpleNamespace(async_create_background_task=self._spawn)
        self.hass = SimpleNamespace()

    def _spawn(self, hass, coro, name):
        return asyncio.create_task(coro, name=name)

    def _notify_update(self):
        pass

    async def _async_restore_held_snapcast_route(self):
        pass

    async def _async_deliver_job(self, item):
        self._started.append(item.job_id)
        try:
            await self._gates[item.job_id].wait()
            self._completed.append(item.job_id)
        finally:
            self._active_jobs.pop(item.job_id, None)
            self._current = next(iter(self._active_jobs.values()), None)
            self._wake.set()


install(WorkerHarness, "_async_worker")


async def _wait_until(predicate):
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Scheduler did not make progress")


def test_actual_worker_runs_independent_rooms_without_fifo_overtake():
    async def scenario():
        h = WorkerHarness((job("j1", "kitchen"), job("j2", "kitchen"),
                           job("j3", "bedroom")))
        worker = asyncio.create_task(h._async_worker())
        try:
            await _wait_until(lambda: len(h._started) >= 2)
            assert h._started == ["j1", "j3"]
            h._gates["j3"].set()
            await _wait_until(lambda: "j3" in h._completed)
            assert "j2" not in h._started
            h._gates["j1"].set()
            await _wait_until(lambda: "j2" in h._started)
            h._gates["j2"].set()
            await _wait_until(lambda: len(h._completed) == 3)
            assert h._started.index("j1") < h._started.index("j2")
        finally:
            h._running = False
            h._wake.set()
            await worker
    asyncio.run(scenario())


def test_burst_limits_are_finite_and_preprocessing_is_independent():
    assert "self._max_parallel_deliveries = 4" in SOURCE
    assert "self._max_parallel_ai = 2" in SOURCE
    assert "self._max_parallel_prefetch = 2" in SOURCE
    assert "self._fill_ai_slots()" in SOURCE
    assert "self._fill_prefetch_slots()" in SOURCE
    assert 'getattr(self, "_players_by_job", {}).get(job_id' in SOURCE


def test_pending_ai_on_shared_visual_output_does_not_block_other_rooms():
    shared = "entity:notify.mobile"
    pending = job("j1", "kitchen", ai=True, notify=shared)
    other = job("j2", "bedroom", notify=shared)
    h = Scheduler((pending, other))
    assert h._next_runnable_job() is other
    h._active_jobs[other.job_id] = other
    assert h._next_runnable_job() is None


def test_different_exact_devices_without_areas_are_independent():
    first = job("j1", None, ai=True, notify="entity:notify.phone")
    second = job("j2", None, notify="entity:notify.tablet")
    h = Scheduler((first, second))
    assert h._room_lane_keys(first) == set()
    assert h._next_runnable_job() is second

