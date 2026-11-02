"""Sleep transition grace: only pre-sleep queued jobs may speak briefly."""
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
        "datetime": datetime, "UTC": UTC,
        "CONF_SLEEP_ROOMS_ENTITY": "sleep_rooms_entity",
        "CONF_SLEEP_ENTRY_GRACE_SECONDS": "sleep_entry_grace_seconds",
        "DEFAULT_SLEEP_ENTRY_GRACE_SECONDS": 60.0,
        "CONF_SLEEP_MUTE_TTS": "sleep_mute_tts",
        "DEFAULT_SLEEP_MUTE_TTS": True,
    }
    exec(compile("from __future__ import annotations\n" + ast.unparse(method), name, "exec"), namespace)
    return namespace[name]


class Harness:
    _sleep_area_ids = _method("_sleep_area_ids")
    _sleep_grace_areas = _method("_sleep_grace_areas")
    _sleep_tts_muted_now = _method("_sleep_tts_muted_now")
    _all_occupied_rooms_sleeping = _method("_all_occupied_rooms_sleeping")

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
        self._running = True
        self.events = []
        self._wake = SimpleNamespace(set=lambda: self.events.append("woke"))

    def _raw_sleep_area_ids(self):
        return self.sleep

    def _sleep_rooms_source_unavailable(self):
        return getattr(self, "offline", False)

    def _occupied_area_ids(self):
        return ("kitchen",)

    def _schedule_save(self):
        self.events.append("saved")


def _job(created):
    return SimpleNamespace(created_at=created.isoformat())


def test_sleep_entry_grace_only_applies_to_preexisting_jobs():
    h = Harness()
    assert h._sleep_area_ids() == frozenset()  # Initialize awake baseline.
    before = _job(h.now - timedelta(seconds=20))
    after = _job(h.now)
    h.sleep = frozenset({"kitchen"})
    assert h._sleep_area_ids() == frozenset({"kitchen"})
    assert "saved" in h.events
    assert h._sleep_grace_areas(before) == frozenset({"kitchen"})
    assert h._sleep_tts_muted_now(before) is False
    assert h._sleep_grace_areas(after) == frozenset()
    assert h._sleep_tts_muted_now(after) is True
    h.settings["sleep_entry_grace_seconds"] = 0
    assert h._sleep_tts_muted_now(before) is True


def test_sleep_grace_expires_and_unavailable_source_fails_closed():
    h = Harness()
    h._sleep_area_ids()
    h.sleep = frozenset({"kitchen"})
    old = _job(h.now - timedelta(seconds=20))
    h._sleep_area_ids()
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
    assert h._sleep_area_ids() == h.sleep
    assert h._sleep_tts_muted_now(before) is True
    assert h._sleep_entered_at == {}


def test_room_policy_keeps_sleeping_rooms_blocked_for_new_jobs():
    assert "self._sleep_area_ids() - self._sleep_grace_areas(job)" in MANAGER
    assert "self._sleep_tts_muted_now(job)" in MANAGER
    assert '"sleep_last_observed"' in MANAGER and '"sleep_entered_at"' in MANAGER
    assert 'CONF_SLEEP_ENTRY_GRACE_SECONDS: Final = "sleep_entry_grace_seconds"' in CONST
    assert "DEFAULT_SLEEP_ENTRY_GRACE_SECONDS: Final = 60.0" in CONST
    assert "CONF_SLEEP_ENTRY_GRACE_SECONDS" in FLOW
