"""Sleep transition grace for pre-sleep and freshly triggered announcements."""
from __future__ import annotations
import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "custom_components/announcement_hub/manager.py").read_text()
CONST = (ROOT / "custom_components/announcement_hub/const.py").read_text()
FLOW = (ROOT / "custom_components/announcement_hub/config_flow.py").read_text()


def _method(name):
    tree = ast.parse(MANAGER)
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "AnnouncementManager")
    method = next(x for x in cls.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x.name == name)
    namespace = {
        "datetime": datetime, "UTC": UTC, "timedelta": timedelta,
        "CONF_SLEEP_ROOMS_ENTITY": "sleep_rooms_entity",
        "CONF_SLEEP_ENTRY_GRACE_SECONDS": "sleep_entry_grace_seconds",
        "DEFAULT_SLEEP_ENTRY_GRACE_SECONDS": 60.0,
        "CONF_SLEEP_MUTE_TTS": "sleep_mute_tts",
        "DEFAULT_SLEEP_MUTE_TTS": True,
        "STATE_UNKNOWN": "unknown", "STATE_UNAVAILABLE": "unavailable",
        "callback": lambda fn: fn,
        "async_track_state_change_event": lambda *args: (lambda: None),
    }
    exec(compile("from __future__ import annotations\n" + ast.unparse(method), name, "exec"), namespace)
    return namespace[name]


class Harness:
    _observe_sleep_areas = _method("_observe_sleep_areas")
    _sleep_grace_areas = _method("_sleep_grace_areas")
    _sleep_tts_muted_now = _method("_sleep_tts_muted_now")
    _all_occupied_rooms_sleeping = _method("_all_occupied_rooms_sleeping")
    _bind_sleep_source = _method("_bind_sleep_source")
    _on_sleep_source_changed = _method("_on_sleep_source_changed")

    def __init__(self):
        self.settings = {"sleep_rooms_entity": "sensor.sleep_rooms",
                         "sleep_entry_grace_seconds": 60,
                         "sleep_mute_tts": True}
        self.now = datetime.now(UTC)
        self.hass = SimpleNamespace(states=SimpleNamespace(get=lambda _e: SimpleNamespace(
            last_updated=self.now - timedelta(seconds=5)
        )))
        self.sleep = frozenset()
        self._sleep_last_observed = None
        self._sleep_entered_at = {}
        self._sleep_source_entity = "sensor.sleep_rooms"
        self._sleep_source_attribute = ""
        self._sleep_source_unsubscribe = None
        self._running = True
        self.events = []
        self._wake = SimpleNamespace(set=lambda: self.events.append("woke"))

    def _sleep_area_ids(self):
        return self.sleep

    def _sleep_rooms_source_unavailable(self):
        return getattr(self, "offline", False)

    def _occupied_area_ids(self):
        return ("kitchen",)

    def _schedule_save(self):
        self.events.append("saved")


def _job(created):
    return SimpleNamespace(created_at=created.isoformat())


def test_sleep_entry_grace_includes_automations_triggered_by_new_sleep_rooms():
    h = Harness()
    assert h._observe_sleep_areas() == frozenset()  # Initialize awake baseline.
    before = _job(h.now - timedelta(seconds=20))
    after = _job(h.now)
    h.sleep = frozenset({"kitchen"})
    assert h._observe_sleep_areas() == frozenset({"kitchen"})
    assert "saved" in h.events
    assert h._sleep_grace_areas(before) == frozenset({"kitchen"})
    assert h._sleep_tts_muted_now(before) is False
    # The automation begins AFTER the room enters sleep. It must speak
    # during the same room-level grace window as already queued messages.
    assert h._sleep_grace_areas(after) == frozenset({"kitchen"})
    assert h._sleep_tts_muted_now(after) is False
    h.settings["sleep_entry_grace_seconds"] = 0
    assert h._sleep_tts_muted_now(before) is True


def test_sleep_grace_expires_and_unavailable_source_fails_closed():
    h = Harness()
    h._observe_sleep_areas()
    h.sleep = frozenset({"kitchen"})
    old = _job(h.now - timedelta(seconds=20))
    h._observe_sleep_areas()
    h._sleep_entered_at["kitchen"] = (h.now - timedelta(seconds=75)).isoformat()
    assert h._sleep_tts_muted_now(old) is True
    h._sleep_entered_at["kitchen"] = (h.now - timedelta(seconds=5)).isoformat()
    assert h._sleep_tts_muted_now(old) is False
    h.offline = True
    assert h._sleep_tts_muted_now(old) is True


def test_existing_sleep_state_on_first_read_does_not_create_new_grace():
    h = Harness()
    h.sleep = frozenset({"kitchen"})
    before = _job(h.now - timedelta(minutes=5))
    assert h._observe_sleep_areas() == h.sleep
    assert h._sleep_tts_muted_now(before) is True
    assert h._sleep_entered_at == {}


def test_entry_triggered_job_speaks_only_until_grace_expires():
    h = Harness()
    h._observe_sleep_areas()  # baseline awake
    h.sleep = frozenset({"kitchen"})
    h._observe_sleep_areas()
    after_entry = _job(h.now - timedelta(seconds=1))
    assert h._sleep_tts_muted_now(after_entry) is False
    h._sleep_entered_at["kitchen"] = (h.now - timedelta(seconds=61)).isoformat()
    assert h._sleep_tts_muted_now(after_entry) is True
    # A later/newer announcement cannot revive an expired room grace.
    new_job = _job(h.now)
    assert h._sleep_grace_areas(new_job) == frozenset()


def test_sleep_tracking_is_initialized_before_queue_and_handles_live_updates():
    h = Harness()
    h._bind_sleep_source(initial=True)
    assert h._sleep_last_observed == frozenset()
    assert h._sleep_source_unsubscribe is not None
    h.sleep = frozenset({"kitchen"})
    # The event listener observes the sleep list independently of queue work.
    h._on_sleep_source_changed(SimpleNamespace(data={
        "old_state": SimpleNamespace(state="awake"),
        "new_state": SimpleNamespace(state="kitchen"),
    }))
    assert h._sleep_last_observed == frozenset({"kitchen"})
    assert "kitchen" in h._sleep_entered_at
    trigger_job = _job(datetime.now(UTC))
    assert h._sleep_grace_areas(trigger_job) == frozenset({"kitchen"})

    # Source outages must not produce an artificial new grace when they
    # recover and still report the same sleeping room.
    h._on_sleep_source_changed(SimpleNamespace(data={
        "old_state": SimpleNamespace(state="unavailable"),
        "new_state": SimpleNamespace(state="kitchen"),
    }))
    assert h._sleep_last_observed == frozenset({"kitchen"})
    assert h._sleep_entered_at == {}
    assert h._sleep_tts_muted_now(trigger_job) is True


def test_startup_restore_keeps_existing_sleep_timestamps_without_renewal():
    h = Harness()
    h.sleep = frozenset({"kitchen"})
    old_stamp = (h.now - timedelta(seconds=35)).isoformat()
    h._sleep_entered_at["kitchen"] = old_stamp
    h._sleep_last_observed = frozenset({"kitchen"})
    h._bind_sleep_source(initial=True)
    assert h._sleep_entered_at == {"kitchen": old_stamp}
    assert h._sleep_grace_areas(_job(h.now)) == frozenset({"kitchen"})
    h._sleep_entered_at["kitchen"] = (h.now - timedelta(seconds=90)).isoformat()
    h._bind_sleep_source(initial=True)
    assert h._sleep_grace_areas(_job(h.now)) == frozenset()


def test_sleep_list_source_reconfiguration_rebaselines_without_fake_entry():
    h = Harness()
    h._bind_sleep_source(initial=True)
    h.sleep = frozenset({"kitchen"})
    h._on_sleep_source_changed(SimpleNamespace(data={
        "old_state": SimpleNamespace(state="awake"),
        "new_state": SimpleNamespace(state="kitchen"),
    }))
    assert h._sleep_entered_at
    h.settings["sleep_rooms_attribute"] = "active_rooms"
    h._bind_sleep_source()
    assert h._sleep_entered_at == {}
    assert h._sleep_last_observed == frozenset({"kitchen"})


def test_room_policy_keeps_sleeping_rooms_blocked_for_new_jobs():
    assert "self._sleep_area_ids() - self._sleep_grace_areas(job)" in MANAGER
    assert "self._sleep_tts_muted_now(job)" in MANAGER
    assert '"sleep_last_observed"' in MANAGER and '"sleep_entered_at"' in MANAGER
    assert "self._bind_sleep_source(initial=True)" in MANAGER
    assert "async_track_state_change_event(" in MANAGER
    assert 'CONF_SLEEP_ENTRY_GRACE_SECONDS: Final = "sleep_entry_grace_seconds"' in CONST
    assert "DEFAULT_SLEEP_ENTRY_GRACE_SECONDS: Final = 60.0" in CONST
    assert "CONF_SLEEP_ENTRY_GRACE_SECONDS" in FLOW
