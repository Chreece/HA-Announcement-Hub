"""Regression: cancellation of producer tasks must free bounded AI/TTS slots."""

from __future__ import annotations

import ast
import asyncio
from collections import deque
from pathlib import Path
from types import SimpleNamespace

SOURCE = (Path(__file__).resolve().parents[1] / "custom_components"
          / "announcement_hub" / "manager.py").read_text(encoding="utf-8")
KLASS = next(item for item in ast.parse(SOURCE).body
             if isinstance(item, ast.ClassDef) and item.name == "AnnouncementManager")


def bind_method(cls, name):
    node = next(item for item in KLASS.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == name)
    scope = {"DOMAIN": "announcement_hub"}
    exec(compile("from __future__ import annotations\n" + ast.unparse(node),
                 f"manager::{name}", "exec"), scope)
    setattr(cls, name, scope[name])


def make_job(number, room):
    return SimpleNamespace(
        job_id=f"j{number}", preferred_areas=(room,), outputs=(room,),
        ai={"pending_preprocessing": True}, tts_text="Hi",
        tts_engines=("tts.piper",), server_tts_enabled=True,
        room_tts_players=("media_player.hello",),
    )


class Producers:
    def __init__(self, jobs):
        self._queue = deque(jobs)
        self._running = True
        self._max_parallel_ai = 2
        self._max_parallel_prefetch = 2
        self._ai_tasks = {}
        self._prefetch_tasks = {}
        self._wake = asyncio.Event()
        self._ai_started = []
        self._tts_started = []
        self._gates = {item.job_id: asyncio.Event() for item in jobs}
        self.entry = SimpleNamespace(async_create_background_task=self._spawn)
        self.hass = SimpleNamespace()

    @staticmethod
    def _spawn(hass, coroutine, label):
        return asyncio.create_task(coroutine, name=label)

    @staticmethod
    def _room_lane_keys(item):
        return {f"room:{x}" for x in (item.preferred_areas or item.outputs)}

    def _schedule_save(self):
        pass

    def _notify_update(self):
        pass

    async def _async_rewrite_job(self, item):
        self._ai_started.append(item.job_id)
        await self._gates[item.job_id].wait()

    async def _async_prefetch(self, item):
        self._tts_started.append(item.job_id)
        await self._gates[item.job_id].wait()


for NAME in ("_fill_ai_slots", "_schedule_ai_rewrite",
             "_fill_prefetch_slots", "_schedule_prefetch"):
    bind_method(Producers, NAME)


async def wait_for(predicate):
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Producer slot was stranded")


def test_cancelled_ai_job_releases_slot_for_different_room():
    async def scenario():
        jobs = [make_job(1, "kitchen"), make_job(2, "bedroom"),
                make_job(3, "office")]
        h = Producers(jobs)
        h._fill_ai_slots()
        await wait_for(lambda: len(h._ai_started) == 2)
        h._queue.remove(jobs[0])
        h._ai_tasks[jobs[0].job_id].cancel()
        await wait_for(lambda: len(h._ai_started) == 3)
        assert h._ai_started == ["j1", "j2", "j3"]
        for task in h._ai_tasks.values():
            task.cancel()
        await asyncio.gather(*h._ai_tasks.values(), return_exceptions=True)
        h._running = False
    asyncio.run(scenario())


def test_cancelled_tts_prefetch_releases_slot_without_new_enqueue():
    async def scenario():
        jobs = [make_job(1, "kitchen"), make_job(2, "bedroom"),
                make_job(3, "office")]
        h = Producers(jobs)
        h._fill_prefetch_slots()
        await wait_for(lambda: len(h._tts_started) == 2)
        h._queue.remove(jobs[0])
        h._prefetch_tasks.pop(jobs[0].job_id).cancel()
        await wait_for(lambda: len(h._tts_started) == 3)
        assert h._tts_started == ["j1", "j2", "j3"]
        h._running = False
        for task in h._prefetch_tasks.values():
            task.cancel()
        await asyncio.gather(*h._prefetch_tasks.values(), return_exceptions=True)
    asyncio.run(scenario())
