"""Executable regressions for durable room-based fallback transitions."""

from __future__ import annotations

import ast
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
SOURCE = (COMPONENT / "manager.py").read_text(encoding="utf-8")


def _real_methods(*names: str):
    tree = ast.parse(SOURCE)
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AnnouncementManager"
    )
    methods = [
        node for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert len(methods) == len(names), "Expected manager methods are missing"
    module = ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[]))
    namespace = {
        "datetime": datetime, "UTC": UTC,
        "utcnow_iso": lambda: datetime.now(UTC).isoformat(),
        "_LOGGER": SimpleNamespace(info=lambda *args: None),
    }
    exec(compile(module, "production-manager-methods", "exec"), namespace)
    return namespace


def _job(*, since=None, fallback=None):
    return SimpleNamespace(
        job_id="kitchen-alert",
        created_at=(datetime.now(UTC) - timedelta(minutes=2)).isoformat(),
        route_since=since or datetime.now(UTC).isoformat(),
        route_tier="requested_rooms",
        fallback_routes=list(fallback or []),
        outputs=("kouzina",),
        tts_engines=(),
        notify_outputs=("entity:notify.kitchen",),
        room_tts_players=(),
        snapcast_clients=(),
        companion_tts_entries=(),
        tts_text=None,
        notify_text="Fenster in Küche öffnen",
        text_tts="Fenster in Küche öffnen",
        text_notify="Fenster in Küche öffnen",
        media_source_ids={},
        room_tts_player_areas={},
        notify_output_areas={"entity:notify.kitchen": "kouzina"},
        notify_output_profiles={},
        snapcast_client_areas={},
        companion_tts_entry_areas={},
        server_tts_enabled=False,
        channel_errors={},
        successful_channels=[],
        started_at=None,
        finished_at=None,
        error=None,
    )


def _fallback(name, target):
    return {
        "tier": name,
        "outputs": [name],
        "tts_engines": [],
        "notify_outputs": [target],
        "room_tts_players": [],
        "snapcast_clients": [],
        "companion_tts_entries": [],
        "server_tts_enabled": False,
        "tts_text": None,
        "notify_text": "Fenster in Küche öffnen",
        "notify_output_areas": {target: name},
        "notify_output_profiles": {},
        "room_tts_player_areas": {},
        "snapcast_client_areas": {},
        "companion_tts_entry_areas": {},
    }


def _manager(jobs, *, ready_tiers=(), timeout=8):
    functions = _real_methods("_next_runnable_job", "_advance_route_tier")
    class Manager:
        _next_runnable_job = functions["_next_runnable_job"]
        _advance_route_tier = functions["_advance_route_tier"]
        _availability_timeout = timeout
        def __init__(self):
            self._queue = deque(jobs)
            self._prefetch_tasks = {}
            self.saved = 0
        def _job_runnable_now(self, job):
            return job.route_tier in ready_tiers
        def _try_last_resort_available_device(self, job):
            return False
        def _schedule_prefetch(self, job):
            pass
        def _schedule_save(self):
            self.saved += 1
        def _notify_update(self):
            pass
        def _pending_age_seconds(self, job):
            return 999
        def _expire_waiting_job(self, job):
            raise AssertionError("Room announcement must NEVER be discarded")
    return Manager()


def test_room_grace_period_does_not_fallback_early():
    j = _job(fallback=[_fallback("occupied_rooms", "entity:notify.bathroom")])
    m = _manager([j], ready_tiers={"occupied_rooms"}, timeout=8)
    assert m._next_runnable_job() is None
    assert j.route_tier == "requested_rooms"
    assert len(m._queue) == 1


def test_expired_kitchen_moves_to_occupied_room_without_broadcast():
    old = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    j = _job(
        since=old,
        fallback=[
            _fallback("occupied_rooms", "entity:notify.bathroom"),
            _fallback("door_fallback", "entity:notify.hall"),
            _fallback("general_devices", "entity:notify.phone"),
        ],
    )
    m = _manager([j], ready_tiers={"occupied_rooms"})
    assert m._next_runnable_job() is j
    assert j.route_tier == "occupied_rooms"
    assert j.notify_outputs == ("entity:notify.bathroom",)
    assert j.outputs == ("occupied_rooms",)
    assert len(j.fallback_routes) == 2
    assert m.saved > 0


def test_multiple_timeouts_advance_to_general_and_preserve_message():
    old = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    j = _job(
        since=old,
        fallback=[
            _fallback("occupied_rooms", "entity:notify.bathroom"),
            _fallback("general_devices", "entity:notify.phone"),
        ],
    )
    m = _manager([j], ready_tiers={"general_devices"})
    assert m._next_runnable_job() is None
    assert j.route_tier == "occupied_rooms"
    j.route_since = old
    assert m._next_runnable_job() is j
    assert j.route_tier == "general_devices"
    assert j.notify_text == "Fenster in Küche öffnen"
    assert j.notify_outputs == ("entity:notify.phone",)


def test_final_offline_tier_stays_queued_indefinitely():
    old = (datetime.now(UTC) - timedelta(days=4)).isoformat()
    j = _job(since=old)
    j.route_tier = "general_devices"
    m = _manager([j], ready_tiers=set())
    assert m._next_runnable_job() is None
    assert j in m._queue
    assert j.finished_at is None
    assert j.error is None


def test_strict_provider_selection_cannot_use_room_fallback():
    source = SOURCE[SOURCE.index("        explicit_targeting = bool(requested)"): ]
    assert "strict_service_targeting = bool(requested)" in source
    assert "staged_room_routing = explicit_area_routing and not strict_service_targeting" in source
    assert "if strict_service_targeting:" in source


def test_room_tiers_are_ordered_and_general_is_non_room_only():
    manager = SOURCE[
        SOURCE.index("        routing_stages:"):
        SOURCE.index("        notify_output_areas = {")
    ]
    assert manager.index('"requested_rooms"') < manager.index('"occupied_rooms"')
    assert manager.index('"occupied_rooms"') < manager.index('"door_fallback"')
    assert manager.index('"door_fallback"') < manager.index('"general_devices"')
    assert "only_general=True" in manager
    assert "self._fallback_door_allows(requested_output_area_ids)" in manager
    assert "if plan.has_output:" in manager


def test_unavailable_room_and_no_configured_device_does_not_reject_or_expire():
    assert "not staged_room_routing:" in SOURCE
    block = SOURCE[
        SOURCE.index("    def _next_runnable_job("):
        SOURCE.index("    async def _async_process_job(")
    ]
    assert "job.route_tier != \"default\"" in block
    assert "self._try_last_resort_available_device(job)" in block
    assert "self._expire_waiting_job(job)" in block
    assert "continue" in block
