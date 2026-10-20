"""Executable regression tests for Air Quality Advisor room-priority delivery.

The real AnnouncementManager staging methods run using fake HA registries,
policies, clock ages, TTS thresholds and output availability. Tests are pure
Python: no actual devices are needed and no announcements are played.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from collections import deque
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "custom_components" / "announcement_hub"
SRC = (C / "manager.py").read_text(encoding="utf-8")

spec = importlib.util.spec_from_file_location(
    "announcement_hub_room_fallback_policy",
    C / "routing_fallback.py",
)
assert spec is not None and spec.loader is not None
routing = importlib.util.module_from_spec(spec)
targeting_spec = importlib.util.spec_from_file_location(
    "announcement_hub_targeting_routing_test", C / "targeting.py"
)
assert targeting_spec is not None and targeting_spec.loader is not None
targeting = importlib.util.module_from_spec(targeting_spec)
targeting_spec.loader.exec_module(targeting)
import sys
sys.modules[spec.name] = routing
spec.loader.exec_module(routing)


@pytest.mark.parametrize(
    "stage,areas,expected",
    [
        ("primary", ("kueche",), ("entity:notify.kitchen",)),
        ("occupied", ("wohnzimmer",), ("entity:notify.living",)),
        ("fallback", ("eingang",), ("entity:notify.entrance",)),
        ("general", (), ("entity:notify.phone",)),
    ],
)
def test_policy_filters_exact_room_or_general_scope(stage, areas, expected):
    selected = routing.select_stage_targets(
        stage=stage, areas=areas, level_priority=1,
        notifications=[
            ("entity:notify.kitchen", "kueche", "room", 1),
            ("entity:notify.living", "wohnzimmer", "room", 1),
            ("entity:notify.entrance", "eingang", "room", 1),
            ("entity:notify.phone", None, "general", 1),
            ("entity:notify.warning", "kueche", "room", 2),
        ],
        room_tts=[("media_player.kitchen", "kueche", "room")],
        snapcast=[("media_player.kitchen_snapcast", "kueche")],
        companion_tts=[],
        speech_allowed=False,
    )
    assert selected.notify == expected
    assert not selected.room_tts
    assert not selected.snapcast
    assert not selected.companion_tts


def test_room_tts_and_snapcast_are_speech_eligible_only_at_or_above_minimum():
    args = dict(
        stage="primary", areas=("kueche",), level_priority=2,
        notifications=[],
        room_tts=[("media_player.kitchen", "kueche", "room")],
        snapcast=[("media_player.kitchen_snapcast", "kueche")],
        companion_tts=[],
    )
    muted = routing.select_stage_targets(**args, speech_allowed=False)
    assert not muted.has_output
    speaking = routing.select_stage_targets(**args, speech_allowed=True)
    assert speaking.has_output
    assert speaking.room_tts == ("media_player.kitchen",)
    assert speaking.snapcast == ("media_player.kitchen_snapcast",)


class FakeManager:
    def __init__(
        self,
        *,
        kitchen_min="info",
        living_min="info",
        fallback_min="info",
        door_open=True,
        timeout=10,
        occupied=("wohnzimmer",),
        available=None,
        kitchen_snapcast=False,
        living_snapcast=False,
        entrance_snapcast=False,
    ):
        self.hass = SimpleNamespace()
        self.settings = {
            "tts_min_level": "warning",
            "notify_profiles": {},
            "channel_fallback_mode": "both",
        }
        self._availability_timeout = timeout
        self.occupied = tuple(occupied)
        self.door_open = door_open
        self.available = available or {}
        self._queue = deque()
        self.snapcast_outputs = tuple(
            name for name, included in (
                ("media_player.kitchen_snapcast", kitchen_snapcast),
                ("media_player.living_snapcast", living_snapcast),
                ("media_player.entrance_snapcast", entrance_snapcast),
            ) if included
        )
        self.notifications = {
            "entity:notify.kitchen": SimpleNamespace(
                ref="entity:notify.kitchen", area_id="kueche",
                integration="nfandroidtv", scope="room", minimum=kitchen_min,
            ),
            "entity:notify.living": SimpleNamespace(
                ref="entity:notify.living", area_id="wohnzimmer",
                integration="nfandroidtv", scope="room", minimum=living_min,
            ),
            "entity:notify.entrance": SimpleNamespace(
                ref="entity:notify.entrance", area_id="eingang",
                integration="nfandroidtv", scope="room", minimum=fallback_min,
            ),
            "entity:notify.phone": SimpleNamespace(
                ref="entity:notify.phone", area_id=None,
                integration="mobile_app", scope="general", minimum="info",
            ),
        }
        self.configured_notifies = tuple(self.notifications)
        self.writes = 0

    def _occupied_area_ids(self):
        return self.occupied

    def _fallback_area_id(self):
        return "eingang"

    def _fallback_door_allows(self, source):
        return bool(source) and self.door_open

    def _configured_outputs(self):
        return (
            ("tts.piper",),
            self.configured_notifies,
            (),
            self.snapcast_outputs,
            (),
        )

    def _select_requested_outputs(
        self, requested, *, level, tts_engines, notify_outputs,
        room_tts_players, snapcast_clients, companion_entries, companion_tts,
    ):
        # A real explicit integration/device restriction cannot expand on
        # fallback. Only the permitted Companion App can remain selected.
        if requested == ("mobile_app",) or list(requested) == ["mobile_app"]:
            return ((), ("entity:notify.phone",), (), (), ())
        return (
            tuple(tts_engines), tuple(notify_outputs),
            tuple(room_tts_players), tuple(snapcast_clients),
            tuple(companion_entries),
        )

    @staticmethod
    def _tts_player_scope(entity_id):
        return "room"

    @staticmethod
    def _notify_policy(output):
        return output.scope, output.minimum

    def _job_runnable_now(self, job):
        return bool(
            (
                job.notify_text
                and any(self.available.get(ref, False) for ref in job.notify_outputs)
            )
            or (
                job.tts_text
                and any(self.available.get(ref, False) for ref in job.snapcast_clients)
            )
        )

    @staticmethod
    def _group_already_delivered(job, physical):
        return False

    def _staged_audio_ready(self, *, targets, engines, shared_player, companion_records, job=None):
        return bool(
            shared_player and engines
            and any(self.available.get(ref, False) for ref in targets.snapcast)
        )

    def _schedule_prefetch(self, job):
        pass

    def _schedule_save(self):
        self.writes += 1

    def _notify_update(self):
        pass


METHODS = (
    "_staged_areas",
    "_prepare_staged_route",
    "_advance_staged_route",
    "_staged_route_ready",
    "_routing_stage_age",
    "_requeue_undelivered_stage",
)
tree = ast.parse(SRC)
klass = next(
    node for node in tree.body
    if isinstance(node, ast.ClassDef) and node.name == "AnnouncementManager"
)
namespace = {
    "_LOGGER": SimpleNamespace(debug=lambda *args, **kwargs: None),
    "STAGES": routing.STAGES,
    "next_stage": routing.next_stage,
    "select_stage_targets": routing.select_stage_targets,
    "prioritize_stage_targets": routing.prioritize_stage_targets,
    "StageTargets": routing.StageTargets,
    "filter_selected_outputs": targeting.filter_selected_outputs,
    "restrict_physical_keys": targeting.restrict_physical_keys,
    "LEVEL_INFO": "info",
    "LEVEL_PRIORITY": {
        "debug": 0, "info": 1, "success": 1, "warning": 2,
        "error": 3, "critical": 4,
    },
    "DEFAULT_NOTIFY_MIN_LEVEL": "info",
    "TTS_LEVEL_NEVER": "never",
    "CONF_TTS_MIN_LEVEL": "tts_min_level",
    "DEFAULT_TTS_MIN_LEVEL": "debug",
    "CONF_CHANNEL_FALLBACK_MODE": "channel_fallback_mode",
    "DEFAULT_CHANNEL_FALLBACK_MODE": "both",
    "CHANNEL_VISUAL_THEN_TTS": "visual_then_tts",
    "CHANNEL_TTS_THEN_VISUAL": "tts_then_visual",
    "LEVEL_CRITICAL": "critical",
    "CONF_NOTIFY_PROFILES": "notify_profiles",
    "NOTIFY_SCOPE_GENERAL": "general",
    "UTC": UTC,
    "datetime": datetime,
    "utcnow_iso": lambda: datetime.now(UTC).isoformat(),
    "Mapping": __import__("collections.abc", fromlist=["Mapping"]).Mapping,
    "ServiceValidationError": ValueError,
    "resolve_notify_outputs": lambda hass, refs: tuple(
        manager.notifications[ref]
        for ref in refs if ref in manager.notifications
    ),
    "resolve_companion_tts_outputs": lambda hass, ids: (),
    "entity_area_id": lambda hass, entity_id: (
        "kueche" if "kitchen" in entity_id else
        "wohnzimmer" if "living" in entity_id else
        "eingang" if "entrance" in entity_id else None
    ),
    "resolve_notify_profile": lambda profiles, integration: {},
    "tts_allowed_for_level": lambda level, minimum: (
        level == "critical" or (
            minimum != "never"
            and namespace["LEVEL_PRIORITY"][level]
            >= namespace["LEVEL_PRIORITY"][minimum]
        )
    ),
    "timedelta": timedelta,
}
for method in klass.body:
    if isinstance(method, ast.FunctionDef) and method.name in METHODS:
        sub = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
        exec(compile(sub, "AnnouncementManager staged router", "exec"), namespace)
        setattr(FakeManager, method.name, namespace[method.name])


def job(*, preferred=("kueche",), services=(), level="info", age=0):
    start = (datetime.now(UTC) - timedelta(seconds=age)).isoformat()
    return SimpleNamespace(
        job_id="test", created_at=start,
        routing_mode="room_fallback", routing_stage="primary",
        routing_stage_started_at=start, routing_history=[],
        routing_retry_after=None,
        routing_audio_retry=False,
        routing_channel_retry=None,
        status="pending", started_at=None, finished_at=None,
        error=None, channel_errors={},
        preferred_areas=tuple(preferred),
        requested_services=tuple(services),
        channel_services=(),
        excluded_physical=(),
        companion_tts_requested=False,
        occupancy_requested=True,
        level=level, text_tts="Παρακαλώ ανοίξτε το παράθυρο",
        text_notify="Ανοίξτε το παράθυρο στην Κουζίνα",
        tts_media_player="media_player.mpd", outputs=(),
        notify_outputs=(), room_tts_players=(), snapcast_clients=(),
        companion_tts_entries=(), server_tts_enabled=False,
        tts_engines=(), tts_text=None, notify_text=None,
        notify_output_areas={}, notify_output_profiles={},
        room_tts_player_areas={}, snapcast_client_areas={},
        companion_tts_entry_areas={}, tts_suppressed_by_level=False,
    )


def configure_manager(monkeypatch, manager):
    # _prepare_staged_route imports output helpers by name; supply this fake
    # exclusively in the extracted live production methods' global scope.
    namespace["resolve_notify_outputs"] = lambda _hass, refs: tuple(
        manager.notifications[ref]
        for ref in refs if ref in manager.notifications
    )
    namespace["notify_output_available"] = lambda hass, output: manager.available.get(output.ref, False)


def test_kueche_info_tts_muted_advances_to_available_occupied_room(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_min="warning", available={"entity:notify.living": True},
    )
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j) is True
    assert j.routing_stage == "occupied"
    assert j.outputs == ("wohnzimmer",)
    assert j.notify_outputs == ("entity:notify.living",)
    assert j.notify_text
    assert j.tts_text is None
    assert not j.snapcast_clients
    assert "primary: no severity-eligible output" in j.routing_history


def test_unavailable_kueche_waits_full_grace_before_occupied_fallback(monkeypatch):
    global manager
    manager = FakeManager(
        available={"entity:notify.kitchen": False, "entity:notify.living": True},
        timeout=10,
    )
    configure_manager(monkeypatch, manager)
    j = job(age=2)
    assert not manager._staged_route_ready(j)
    assert j.routing_stage == "primary"
    assert j.notify_outputs == ("entity:notify.kitchen",)
    j.routing_stage_started_at = (
        datetime.now(UTC) - timedelta(seconds=11)
    ).isoformat()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "occupied"
    assert j.notify_outputs == ("entity:notify.living",)


def test_fallback_room_only_when_original_room_door_open(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_min="warning",
        available={"entity:notify.entrance": True, "entity:notify.phone": True},
        door_open=True, occupied=(),
    )
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "fallback"
    assert j.outputs == ("eingang",)
    assert j.notify_outputs == ("entity:notify.entrance",)
    manager.door_open = False
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "general"
    assert j.notify_outputs == ("entity:notify.phone",)
    assert j.outputs == ()


def test_fallback_room_unavailable_waits_before_general_phone(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_min="warning", occupied=(),
        available={"entity:notify.entrance": False, "entity:notify.phone": True},
        timeout=5,
    )
    configure_manager(monkeypatch, manager)
    j = job()
    assert not manager._staged_route_ready(j)
    assert j.routing_stage == "fallback"
    j.routing_stage_started_at = (
        datetime.now(UTC) - timedelta(seconds=6)
    ).isoformat()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "general"
    assert j.notify_outputs == ("entity:notify.phone",)


def test_no_outputs_keeps_job_pending_until_general_phone_returns(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_min="warning", occupied=(), door_open=False,
        available={},
    )
    configure_manager(monkeypatch, manager)
    j = job()
    assert not manager._staged_route_ready(j)
    assert j.routing_stage == "general"
    assert j.notify_outputs == ("entity:notify.phone",)
    assert not manager._job_runnable_now(j)
    manager.available["entity:notify.phone"] = True
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "general"
    assert j.notify_outputs == ("entity:notify.phone",)


def test_newly_configured_general_device_unblocks_persisted_job(monkeypatch):
    global manager
    manager = FakeManager(kitchen_min="warning", occupied=(), door_open=False)
    manager.configured_notifies = ("entity:notify.kitchen",)
    configure_manager(monkeypatch, manager)
    j = job()
    assert not manager._staged_route_ready(j)
    assert j.routing_stage == "general"
    assert j.notify_outputs == ()
    manager.configured_notifies = ("entity:notify.kitchen", "entity:notify.phone")
    manager.available["entity:notify.phone"] = True
    assert manager._staged_route_ready(j)
    assert j.notify_outputs == ("entity:notify.phone",)


def test_explicit_mobile_app_service_never_expands_to_other_providers(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_min="warning",
        available={"entity:notify.phone": True, "entity:notify.living": True},
    )
    configure_manager(monkeypatch, manager)
    j = job(services=("mobile_app",))
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "general"
    assert j.notify_outputs == ("entity:notify.phone",)
    assert not j.tts_text
    assert not j.snapcast_clients


def test_preferred_room_remains_first_when_it_has_ready_info_output(monkeypatch):
    global manager
    manager = FakeManager(
        available={"entity:notify.kitchen": True, "entity:notify.living": True},
    )
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "primary"
    assert j.outputs == ("kueche",)
    assert j.notify_outputs == ("entity:notify.kitchen",)
    assert "entity:notify.living" not in j.notify_outputs


def test_occupied_only_false_skips_occupied_room_fallback(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_min="warning", door_open=False,
        available={
            "entity:notify.living": True,
            "entity:notify.phone": True,
        },
    )
    configure_manager(monkeypatch, manager)
    j = job()
    j.occupancy_requested = False
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "general"
    assert j.notify_outputs == ("entity:notify.phone",)


def test_info_uses_same_room_snapcast_before_occupied_or_general(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_min="warning", kitchen_snapcast=True,
        available={
            "media_player.kitchen_snapcast": True,
            "entity:notify.living": True,
            "entity:notify.phone": True,
        },
    )
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "primary"
    assert j.outputs == ("kueche",)
    assert j.snapcast_clients == ("media_player.kitchen_snapcast",)
    assert j.notify_outputs == ()
    assert j.tts_text
    assert not j.tts_suppressed_by_level


def test_info_prefers_ready_visual_over_same_room_snapcast(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_snapcast=True,
        available={
            "entity:notify.kitchen": True,
            "media_player.kitchen_snapcast": True,
            "entity:notify.phone": True,
        },
    )
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "primary"
    assert j.notify_outputs == ("entity:notify.kitchen",)
    assert j.snapcast_clients == ()
    assert j.tts_text is None


def test_unavailable_visual_does_not_block_ready_same_room_snapcast(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_snapcast=True,
        available={
            "entity:notify.kitchen": False,
            "media_player.kitchen_snapcast": True,
            "entity:notify.phone": True,
        },
    )
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "primary"
    assert j.snapcast_clients == ("media_player.kitchen_snapcast",)
    assert j.notify_outputs == ()


def test_moved_to_occupied_room_prefers_speech_even_with_visual(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_min="warning", living_snapcast=True,
        available={
            "entity:notify.living": True,
            "media_player.living_snapcast": True,
            "entity:notify.phone": True,
        },
    )
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "occupied"
    assert j.outputs == ("wohnzimmer",)
    assert j.snapcast_clients == ("media_player.living_snapcast",)
    assert j.notify_outputs == ()


def test_door_gated_fallback_uses_room_speech_at_info_all_levels(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_min="warning", occupied=(), entrance_snapcast=True,
        available={
            "entity:notify.entrance": True,
            "media_player.entrance_snapcast": True,
            "entity:notify.phone": True,
        },
        door_open=True,
    )
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "fallback"
    assert j.outputs == ("eingang",)
    assert j.snapcast_clients == ("media_player.entrance_snapcast",)
    assert j.notify_outputs == ()
    manager.door_open = False
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "general"
    assert j.notify_outputs == ("entity:notify.phone",)
    assert not j.snapcast_clients


def test_failed_visual_retries_audio_in_same_room_before_next_stage(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_snapcast=True,
        available={
            "entity:notify.kitchen": True,
            "media_player.kitchen_snapcast": True,
            "entity:notify.living": True,
        },
    )
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.notify_outputs == ("entity:notify.kitchen",)
    manager._requeue_undelivered_stage(j, "provider failure")
    assert j.routing_stage == "primary"
    assert j.routing_audio_retry
    assert manager._staged_route_ready(j)
    assert j.snapcast_clients == ("media_player.kitchen_snapcast",)
    assert j.notify_outputs == ()
    assert any("trying same-room audio" in entry for entry in j.routing_history)


def test_both_room_channels_unavailable_wait_before_other_room(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_snapcast=True, timeout=5,
        available={"entity:notify.living": True, "entity:notify.phone": True},
    )
    configure_manager(monkeypatch, manager)
    j = job(age=2)
    assert not manager._staged_route_ready(j)
    assert j.routing_stage == "primary"
    assert j.snapcast_clients == ("media_player.kitchen_snapcast",)
    j.routing_stage_started_at = (
        datetime.now(UTC) - timedelta(seconds=6)
    ).isoformat()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "occupied"


def test_room_speech_respects_never_and_restricted_notify_service(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_min="warning", kitchen_snapcast=True,
        occupied=(), door_open=False,
        available={
            "media_player.kitchen_snapcast": True,
            "entity:notify.phone": True,
        },
    )
    manager.settings["tts_min_level"] = "never"
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "general"
    assert j.snapcast_clients == ()
    manager.settings["tts_min_level"] = "warning"
    j = job(services=("mobile_app",))
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "general"
    assert j.snapcast_clients == ()


def test_visual_first_failure_retries_speech_in_same_requested_room(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_snapcast=True,
        available={
            "entity:notify.kitchen": True,
            "media_player.kitchen_snapcast": True,
            "entity:notify.phone": True,
        },
    )
    manager.settings["channel_fallback_mode"] = "visual_then_tts"
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "primary"
    assert j.notify_outputs == ("entity:notify.kitchen",)
    assert not j.snapcast_clients
    manager._requeue_undelivered_stage(j, "visual provider error")
    assert j.routing_stage == "primary"
    assert j.routing_channel_retry == "tts"
    assert manager._staged_route_ready(j)
    assert j.snapcast_clients == ("media_player.kitchen_snapcast",)
    assert not j.notify_outputs


def test_tts_first_failure_retries_visual_without_moving_rooms(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_snapcast=True,
        available={
            "entity:notify.kitchen": True,
            "media_player.kitchen_snapcast": True,
            "entity:notify.phone": True,
        },
    )
    manager.settings["channel_fallback_mode"] = "tts_then_visual"
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "primary"
    assert j.snapcast_clients == ("media_player.kitchen_snapcast",)
    assert not j.notify_outputs
    manager._requeue_undelivered_stage(j, "tts provider error")
    assert j.routing_stage == "primary"
    assert j.routing_channel_retry == "visual"
    assert manager._staged_route_ready(j)
    assert j.notify_outputs == ("entity:notify.kitchen",)
    assert not j.snapcast_clients


def test_tts_first_uses_visual_immediately_if_audio_offline(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_snapcast=True, timeout=10,
        available={
            "entity:notify.kitchen": True,
            "media_player.kitchen_snapcast": False,
            "entity:notify.phone": True,
        },
    )
    manager.settings["channel_fallback_mode"] = "tts_then_visual"
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "primary"
    assert j.notify_outputs == ("entity:notify.kitchen",)
    assert not j.snapcast_clients


def test_directional_fallback_never_creates_missing_tts_text(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_snapcast=True, occupied=(), door_open=False,
        available={
            "entity:notify.kitchen": True,
            "media_player.kitchen_snapcast": True,
            "entity:notify.phone": True,
        },
    )
    manager.settings["channel_fallback_mode"] = "visual_then_tts"
    configure_manager(monkeypatch, manager)
    j = job()
    j.text_tts = None
    assert manager._staged_route_ready(j)
    assert j.notify_outputs == ("entity:notify.kitchen",)
    assert not j.snapcast_clients
    manager._requeue_undelivered_stage(j, "visual provider error")
    assert j.routing_channel_retry is None
    # After one channel fails, advance the stage; the worker then evaluates
    # the next permitted room. It must not invent missing TTS content.
    assert j.routing_stage == "occupied"
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "general"


def test_visual_first_respects_hard_never_and_does_not_add_speakers(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_snapcast=True,
        available={
            "entity:notify.kitchen": True,
            "media_player.kitchen_snapcast": True,
        },
    )
    manager.settings["channel_fallback_mode"] = "visual_then_tts"
    manager.settings["tts_min_level"] = "never"
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    manager._requeue_undelivered_stage(j, "visual provider error")
    assert j.routing_channel_retry is None
    assert not j.snapcast_clients


def test_missing_alternate_channel_advances_room_without_broadcast(monkeypatch):
    global manager
    manager = FakeManager(
        available={
            "entity:notify.kitchen": True,
            "entity:notify.living": True,
            "entity:notify.phone": True,
        },
    )
    manager.settings["channel_fallback_mode"] = "visual_then_tts"
    configure_manager(monkeypatch, manager)
    j = job()
    assert manager._staged_route_ready(j)
    assert j.routing_stage == "primary"
    manager._requeue_undelivered_stage(j, "visual failure")
    assert j.routing_channel_retry is None
    assert j.routing_stage == "occupied"
    assert manager._staged_route_ready(j)
    assert j.notify_outputs == ("entity:notify.living",)


def test_simultaneous_mode_keeps_both_channels_at_warning(monkeypatch):
    global manager
    manager = FakeManager(
        kitchen_snapcast=True,
        available={
            "entity:notify.kitchen": True,
            "media_player.kitchen_snapcast": True,
        },
    )
    manager.settings["channel_fallback_mode"] = "both"
    configure_manager(monkeypatch, manager)
    j = job(level="warning")
    assert manager._staged_route_ready(j)
    assert j.notify_outputs == ("entity:notify.kitchen",)
    assert j.snapcast_clients == ("media_player.kitchen_snapcast",)


def test_scheduler_does_not_drop_undelivered_jobs():
    scheduler = SRC[
        SRC.index("    def _next_runnable_job("):
        SRC.index("    async def _async_process_job(")
    ]
    assert "self._expire_waiting_job(" not in SRC
    assert "return None" in scheduler
    assert "self._staged_route_ready(job)" in scheduler
    assert "elif self._job_runnable_now(job)" in scheduler
