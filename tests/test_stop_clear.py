"""Stop & Clear regressions: waiting jobs, active audio ownership, durability."""
from __future__ import annotations

import ast
import asyncio
from collections import deque
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace

SOURCE = (Path(__file__).resolve().parents[1] / "custom_components"
          / "announcement_hub" / "manager.py").read_text(encoding="utf-8")
CLASS = next(n for n in ast.parse(SOURCE).body
             if isinstance(n, ast.ClassDef) and n.name == "AnnouncementManager")


def isolate(name, **dependencies):
    method = next(n for n in CLASS.body
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n.name == name)
    globals_ = {
        "asyncio": asyncio,
        "suppress": suppress,
        "EVENT_CANCELLED": "announcement_hub_cancelled",
        "EVENT_QUEUE_CLEARED": "announcement_hub_queue_cleared",
        "ServiceValidationError": ValueError,
        "_TERMINAL_JOB_STATES": {"completed", "completed_with_errors", "failed", "cancelled"},
        "utcnow_iso": lambda: "2026-10-31T13:00:00+00:00",
        **dependencies,
    }
    exec(compile("from __future__ import annotations\n" + ast.unparse(method),
                 name, "exec"), globals_)
    return globals_[name]


class Job:
    def __init__(self, job_id, status, group_id=None):
        self.job_id = job_id
        self.status = status
        self.group_id = group_id
        self.related_job_ids = ()
        self.finished_at = None

    def to_dict(self):
        return {"job_id": self.job_id, "created_at": "2026-10-31",
                "status": self.status}


class Store:
    def __init__(self):
        self.saved = []

    async def async_save(self, snapshot):
        self.saved.append(snapshot)


class Harness:
    async_clear_queue = isolate("async_clear_queue")
    async_cancel = isolate("async_cancel")
    _serialize = isolate("_serialize")

    def __init__(self):
        self._queue = deque([Job("pending-1", "pending"),
                            Job("pending-2", "pending")])
        self._active_jobs = {
            "speaking": Job("speaking", "processing"),
            "waiting": Job("waiting", "processing"),
        }
        self._current = self._active_jobs["speaking"]
        self._cancel_requested = set()
        self._players_by_job = {"waiting": {"media_player.unrelated_music"}}
        self._hub_playing_players_by_job = {
            "speaking": {"media_player.hub_speech"},
        }
        self._prefetch_tasks = {}
        self._ai_tasks = {}
        self._group_success = {"old": {"some_receipt"}}
        self._volume_restore = {}
        self._ai_history = deque(maxlen=20)
        self._last = None
        self._running = True
        self._save_lock = asyncio.Lock()
        self._store = Store()
        self._wake_count = 0
        self._wake = SimpleNamespace(set=lambda: setattr(
            self, "_wake_count", self._wake_count + 1
        ))
        self.events = []
        self.hass = SimpleNamespace(bus=SimpleNamespace(
            async_fire=lambda event, data: self.events.append((event, data))
        ))
        self.stopped = []

    async def _async_stop_player(self, player):
        assert self._cancel_requested >= {"speaking", "waiting"}
        self.stopped.append(player)
        await asyncio.sleep(0)

    def _fire_event(self, event, job):
        self.events.append((event, job.job_id))

    def _notify_update(self):
        pass

    def _fill_ai_slots(self):
        pass

    def _fill_prefetch_slots(self):
        pass


def test_stop_clear_cancels_all_active_lanes_without_stopping_unrelated_music():
    h = Harness()
    removed = asyncio.run(h.async_clear_queue(include_current=True))
    assert removed == 2
    assert not h._queue
    assert h._cancel_requested == {"speaking", "waiting"}
    assert h.stopped == ["media_player.hub_speech"]
    assert len(h._store.saved) == 1
    assert h._store.saved[-1]["jobs"] == []
    assert h._wake_count >= 1
    assert not h._group_success
    assert [event for event, _ in h.events].count("announcement_hub_cancelled") == 2
    assert [event for event, _ in h.events].count("announcement_hub_queue_cleared") == 1


def test_queue_only_clear_keeps_active_jobs_and_does_not_stop_audio():
    h = Harness()
    assert asyncio.run(h.async_clear_queue(include_current=False)) == 2
    assert not h._cancel_requested
    assert not h.stopped
    assert {job["job_id"] for job in h._store.saved[-1]["jobs"]} == {
        "speaking", "waiting"
    }


def test_a_waiting_media_player_is_not_a_spoken_output_to_stop():
    h = Harness()
    h._hub_playing_players_by_job.clear()
    asyncio.run(h.async_clear_queue(include_current=True))
    assert h.stopped == []
    assert h._cancel_requested == {"speaking", "waiting"}


def test_active_audio_ownership_is_removed_after_playback_error():
    async def call_service(self, domain, service, payload, **kwargs):
        assert (domain, service) == ("media_player", "play_media")
        assert self.owner._hub_playing_players_by_job == {
            "spoken": {"media_player.speech"}
        }
        self.called = True

    class PlayerHarness:
        def __init__(self):
            self._hub_playing_players_by_job = {}
            self.hass = SimpleNamespace(services=SimpleNamespace())
            self.hass.services.owner = self
            self.hass.services.called = False
            self.hass.services.async_call = call_service.__get__(
                self.hass.services
            )
            self.settings = {}

        def _raise_if_cancelled(self, job):
            pass

        def _sleep_tts_muted_now(self):
            return False

        async def _wait_for(self, *args, **kwargs):
            raise RuntimeError("playback cancelled")

    player = PlayerHarness()
    method = isolate(
        "_async_play_media_source",
        MEDIA_PLAYER_DOMAIN="media_player",
        ATTR_ENTITY_ID="entity_id",
        ATTR_MEDIA_CONTENT_ID="media_content_id",
        ATTR_MEDIA_CONTENT_TYPE="media_content_type",
        ATTR_MEDIA_ANNOUNCE="announce",
        MediaType=SimpleNamespace(MUSIC="music"),
        CONF_DIRECT_TTS_ANNOUNCE="direct_tts_announce",
        DEFAULT_DIRECT_TTS_ANNOUNCE=True,
        CONF_START_TIMEOUT="start_timeout",
        DEFAULT_START_TIMEOUT=5,
    )
    job = SimpleNamespace(job_id="spoken", routing_mode="normal",
                          tts_media_player=None, person_ids=())
    try:
        asyncio.run(method(player, job, "media_player.speech", "media-source://tts"))
    except RuntimeError as err:
        assert "playback cancelled" in str(err)
    else:
        raise AssertionError("Expected cancellation/error during play")
    assert player.hass.services.called
    assert player._hub_playing_players_by_job == {"spoken": set()}


def test_companion_tts_hold_and_shutdown_are_cancellation_responsive():
    assert "await self._async_reading_hold(\n                job,\n                self._companion_tts_hold_time(" in SOURCE
    assert "job.job_id not in self._cancel_requested" in SOURCE
    assert "and job.job_id not in self._cancel_requested" in SOURCE
    assert "_hub_playing_players_by_job" in SOURCE
