"""Fallback follows live listeners without blocking or overlapping queued TTS.

Run the real staging, door and scheduler methods against the existing small
Home Assistant fixture. No service calls or physical playback are needed.
"""

from __future__ import annotations

import ast
import asyncio
from collections import deque
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import test_room_grace_escalation as staged


class LiveFallbackManager(staged.FakeManager):
    def __init__(self, *, fallback_area="eingang", doors=None, **kwargs):
        super().__init__(**kwargs)
        self.fallback_area = fallback_area
        self.doors = dict(doors or {})
        self.settings["fallback_check_door"] = True
        self.settings["fallback_door_label"] = ""
        self.configured_notifies = ()
        self.hass.states.async_all = lambda _domain: [
            SimpleNamespace(
                entity_id=entity_id,
                state=state,
                attributes={"device_class": "door"},
            )
            for entity_id, state in self.doors.items()
        ]
        self._active_jobs = {}

    def _fallback_area_id(self):
        return self.fallback_area


door_namespace = dict(
    staged.namespace,
    CONF_FALLBACK_CHECK_DOOR="fallback_check_door",
    DEFAULT_FALLBACK_CHECK_DOOR=True,
    CONF_FALLBACK_DOOR_LABEL="fallback_door_label",
    STATE_ON="on",
    er=SimpleNamespace(async_get=lambda _hass: SimpleNamespace(
        async_get=lambda _entity_id: SimpleNamespace(labels=set())
    )),
    asyncio=asyncio,
    EVENT_CHANNEL_STARTED="announcement_hub_channel_started",
    COMPANION_STREAM_DEFAULT="default",
    HomeAssistantError=RuntimeError,
    JobCancelled=type("JobCancelled", (RuntimeError,), {}),
    mobile_app_webhook_id=lambda _hass, _entry_id: "relay-webhook",
)
for name in (
    "_fallback_door_allows", "_room_lane_keys", "_delivery_lane_keys",
    "_next_runnable_job", "_async_deliver_companion_tts",
):
    method = next(node for node in staged.klass.body
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and node.name == name)
    exec(compile("from __future__ import annotations\n" + ast.unparse(method),
                 "live room fallback", "exec"), door_namespace)
    setattr(LiveFallbackManager, name, door_namespace[name])


@pytest.fixture
def make_manager(monkeypatch):
    def create(**kwargs):
        manager = LiveFallbackManager(**kwargs)
        staged.configure_manager(monkeypatch, manager)
        return manager
    return create


def speech_job(*, preferred=(), job_id="queued"):
    item = staged.job(preferred=preferred, level="warning")
    item.job_id = job_id
    item.text_notify = None
    item.ai = {}
    return item


def expire_availability_grace(manager, item):
    item.routing_stage_started_at = (
        datetime.now(UTC) - timedelta(seconds=manager._availability_timeout + 1)
    ).isoformat()


@pytest.mark.parametrize("preferred", [(), ("kueche",)])
def test_queued_announcements_follow_move_to_unready_room(make_manager, preferred):
    manager = make_manager(
        occupied=("kueche",), timeout=5,
        kitchen_snapcast=True, living_snapcast=True, entrance_snapcast=True,
        available={
            "media_player.kitchen_snapcast": True,
            "media_player.living_snapcast": False,
            "media_player.entrance_snapcast": True,
        },
        doors={
            "binary_sensor.kitchen_door": "off",
            "binary_sensor.living_door": "on",
        },
    )
    queued = speech_job(preferred=preferred)
    assert manager._staged_route_ready(queued)
    assert queued.outputs == ("kueche",)

    # A previously prepared queued message must not stay pinned to that room.
    manager.occupied = ("wohnzimmer",)
    assert not manager._staged_route_ready(queued)
    assert queued.routing_stage == "occupied"
    assert queued.outputs == ("wohnzimmer",)
    expire_availability_grace(manager, queued)
    assert manager._staged_route_ready(queued)
    assert queued.routing_stage == "fallback"
    assert queued.outputs == ("eingang",)
    assert queued.snapcast_clients == ("media_player.entrance_snapcast",)
    manager._assert_live_room_route(queued, ("eingang",))

    # The following message also succeeds without the listener coming back.
    following = speech_job(preferred=preferred, job_id="following")
    assert not manager._staged_route_ready(following)
    expire_availability_grace(manager, following)
    assert manager._staged_route_ready(following)
    assert following.snapcast_clients == ("media_player.entrance_snapcast",)
    assert manager.occupied == ("wohnzimmer",)

    manager.available["media_player.living_snapcast"] = True
    ready_room = speech_job(preferred=preferred, job_id="ready-room")
    assert manager._staged_route_ready(ready_room)
    assert ready_room.routing_stage == "occupied"
    assert ready_room.snapcast_clients == ("media_player.living_snapcast",)


def test_room_without_tts_goes_directly_to_configured_fallback(make_manager):
    manager = make_manager(
        occupied=("wohnzimmer",), timeout=60, entrance_snapcast=True,
        available={"media_player.entrance_snapcast": True},
        doors={"binary_sensor.living_door": "on"},
    )
    item = speech_job()
    assert manager._staged_route_ready(item)
    assert item.routing_stage == "fallback"
    assert item.snapcast_clients == ("media_player.entrance_snapcast",)


def test_old_preferred_room_can_be_the_configured_empty_relay(make_manager):
    manager = make_manager(
        occupied=("wohnzimmer",), fallback_area="kueche",
        kitchen_snapcast=True,
        available={"media_player.kitchen_snapcast": True},
        doors={
            "binary_sensor.kitchen_door": "off",
            "binary_sensor.living_door": "on",
        },
    )
    item = speech_job(preferred=("kueche",))
    assert manager._staged_route_ready(item)
    assert item.routing_stage == "fallback"
    assert item.outputs == ("kueche",)
    assert item.snapcast_clients == ("media_player.kitchen_snapcast",)
    assert item.preferred_areas == ("kueche",)
    manager._assert_live_room_route(item, ("kueche",))


@pytest.mark.parametrize("current_door", ["off", "unknown", "unavailable", None])
def test_old_open_door_cannot_authorize_new_room_fallback(make_manager, current_door):
    doors = {"binary_sensor.kitchen_door": "on"}
    if current_door is not None:
        doors["binary_sensor.living_door"] = current_door
    manager = make_manager(
        occupied=("wohnzimmer",), timeout=0, entrance_snapcast=True,
        available={"media_player.entrance_snapcast": True}, doors=doors,
    )
    item = speech_job(preferred=("kueche",))
    assert not manager._staged_route_ready(item)
    assert item.snapcast_clients == ()
    assert not item.successful_channels


def test_disabling_door_check_permits_current_room_fallback(make_manager):
    manager = make_manager(
        occupied=("wohnzimmer",), entrance_snapcast=True,
        available={"media_player.entrance_snapcast": True},
        doors={"binary_sensor.living_door": "off"},
    )
    manager.settings["fallback_check_door"] = False
    item = speech_job()
    assert manager._staged_route_ready(item)
    assert item.routing_stage == "fallback"
    assert item.snapcast_clients == ("media_player.entrance_snapcast",)


@pytest.mark.parametrize("preferred", [(), ("kueche",)])
def test_live_fallback_rechecks_new_listener_door_before_playback(make_manager, preferred):
    manager = make_manager(
        occupied=("kueche",), entrance_snapcast=True,
        available={"media_player.entrance_snapcast": True},
        doors={
            "binary_sensor.kitchen_door": "on",
            "binary_sensor.living_door": "on",
        },
    )
    item = speech_job(preferred=preferred)
    assert manager._staged_route_ready(item)
    manager._assert_live_room_route(item, ("eingang",))

    # The relay is still audible after the listener changes room.
    manager.occupied = ("wohnzimmer",)
    manager._assert_live_room_route(item, ("eingang",))

    # A fresh closure must stop fallback even though the original door is open.
    manager.doors["binary_sensor.living_door"] = "off"
    with pytest.raises(staged.namespace["RoomRouteMoved"]):
        manager._assert_live_room_route(item, ("eingang",))


@pytest.mark.parametrize("blocked_by", ["nobody", "sleep", "disabled", "missing-source"])
def test_fallback_needs_a_current_eligible_listener(make_manager, blocked_by):
    manager = make_manager(
        occupied=("wohnzimmer",), entrance_snapcast=True,
        available={"media_player.entrance_snapcast": True},
        doors={"binary_sensor.living_door": "on"},
    )
    item = speech_job()
    if blocked_by == "nobody":
        manager.occupied = ()
    elif blocked_by == "sleep":
        manager.settings["sleep_rooms"] = ("wohnzimmer",)
    elif blocked_by == "disabled":
        manager.settings["person_area_enabled"] = {"wohnzimmer": False}
    else:
        manager.occupied = None
    assert not manager._staged_route_ready(item)
    assert item.snapcast_clients == ()
    assert not item.successful_channels


def test_awake_listener_cannot_use_sleeping_or_disabled_fallback(make_manager):
    manager = make_manager(
        occupied=("wohnzimmer",), entrance_snapcast=True,
        available={"media_player.entrance_snapcast": True},
        doors={"binary_sensor.living_door": "on"},
    )
    manager.settings["sleep_rooms"] = ("eingang",)
    assert not manager._staged_route_ready(speech_job())
    manager.settings["sleep_rooms"] = ()
    manager.settings["person_area_enabled"] = {"eingang": False}
    assert not manager._staged_route_ready(speech_job())


def test_fixed_room_request_does_not_borrow_an_unrelated_listener(make_manager):
    manager = make_manager(
        occupied=("wohnzimmer",),
        doors={"binary_sensor.living_door": "on"},
    )
    item = speech_job(preferred=("kueche",))
    item.occupancy_requested = False
    assert manager._staged_areas(item, "fallback") == ()


def test_exact_service_selection_does_not_expand_to_fallback_speakers(make_manager):
    manager = make_manager(
        occupied=("wohnzimmer",), entrance_snapcast=True,
        available={"entity:notify.phone": True, "media_player.entrance_snapcast": True},
        doors={"binary_sensor.living_door": "on"},
    )
    item = staged.job(preferred=(), services=("mobile_app",))
    assert manager._staged_route_ready(item)
    assert item.routing_stage == "general"
    assert item.notify_outputs == ("entity:notify.phone",)
    assert item.snapcast_clients == ()
    assert item.tts_text is None


@pytest.mark.parametrize("preferred", [(), ("kueche",)])
def test_replanned_fallback_waits_for_active_speaker_then_continues(make_manager, preferred):
    manager = make_manager(
        occupied=("kueche",), entrance_snapcast=True,
        available={"media_player.entrance_snapcast": True},
        doors={"binary_sensor.kitchen_door": "on"},
    )
    active = speech_job(job_id="active")
    active.routing_stage = "fallback"
    active.outputs = ("eingang",)
    active.snapcast_clients = ("media_player.entrance_snapcast",)
    active.server_tts_enabled = True
    active.tts_text = active.text_tts
    manager._active_jobs[active.job_id] = active
    waiting = speech_job(preferred=preferred)
    manager._queue = deque((waiting,))
    assert waiting.outputs == ()
    assert not manager._delivery_lane_keys(waiting) & manager._delivery_lane_keys(active)

    # Selection refreshes the empty/stale route. Its newly selected room and
    # shared Snapcast source must be checked against the ongoing delivery.
    assert manager._next_runnable_job() is None
    assert waiting.outputs == ("eingang",)
    assert waiting.snapcast_clients == ("media_player.entrance_snapcast",)
    manager._active_jobs.clear()
    assert manager._next_runnable_job() is waiting


def test_newly_resolved_unready_fallback_keeps_older_job_first(make_manager):
    manager = make_manager(
        occupied=("kueche",), timeout=5, entrance_snapcast=True,
        available={
            "media_player.entrance_snapcast": False,
            "entity:notify.entrance": True,
        },
        doors={"binary_sensor.kitchen_door": "on"},
    )
    older = speech_job(job_id="older")
    later = staged.job(preferred=("eingang",))
    later.job_id = "later"
    later.ai = {}
    later.routing_mode = "normal"
    later.outputs = ("eingang",)
    later.notify_outputs = ("entity:notify.entrance",)
    later.notify_output_areas = {"entity:notify.entrance": "eingang"}
    later.notify_text = later.text_notify
    manager._queue = deque((older, later))
    assert manager._job_runnable_now(later)
    assert older.outputs == ()

    # The older job discovers its fallback during this scan. Even though it
    # is not ready yet, the ready later message must keep that room's FIFO.
    assert manager._next_runnable_job() is None
    assert older.routing_stage == "fallback"
    assert older.outputs == ("eingang",)
    assert not manager._job_runnable_now(older)
    manager.available["media_player.entrance_snapcast"] = True
    assert manager._next_runnable_job() is older


def test_new_room_route_does_not_take_over_active_shared_snapcast(make_manager):
    manager = make_manager(
        occupied=("wohnzimmer",), living_snapcast=True,
        available={"media_player.living_snapcast": True},
    )
    active = speech_job(job_id="active")
    active.outputs = ("kueche",)
    active.snapcast_clients = ("media_player.kitchen_snapcast",)
    active.server_tts_enabled = True
    active.tts_text = active.text_tts
    manager._active_jobs[active.job_id] = active
    waiting = speech_job()
    manager._queue = deque((waiting,))

    # The new room differs from the active room, but both use the same
    # Snapcast source. Replanning must not let the second job interrupt it.
    assert manager._next_runnable_job() is None
    assert waiting.outputs == ("wohnzimmer",)
    assert waiting.snapcast_clients == ("media_player.living_snapcast",)
    assert not manager._room_lane_keys(waiting) & manager._room_lane_keys(active)
    assert manager._delivery_lane_keys(waiting) & manager._delivery_lane_keys(active) == {
        "audio:snapcast-shared"
    }
    manager._active_jobs.clear()
    assert manager._next_runnable_job() is waiting


@pytest.mark.parametrize(
    "door_state,check_door,already_delivered,should_send",
    [
        ("off", True, False, False),
        ("on", True, False, True),
        ("off", False, False, True),
        ("off", True, True, False),
    ],
)
def test_companion_tts_rechecks_fallback_door_before_notify(
    monkeypatch, make_manager, door_state, check_door,
    already_delivered, should_send,
):
    manager = make_manager(
        occupied=("wohnzimmer",),
        doors={"binary_sensor.living_door": "on"},
    )
    output = SimpleNamespace(entry_id="relay-phone", area_id="eingang", title="Relay")
    manager._configured_outputs = lambda: ((), (), (), (), (output.entry_id,))
    monkeypatch.setitem(
        staged.namespace, "resolve_companion_tts_outputs",
        lambda _hass, ids: (output,) if output.entry_id in ids else (),
    )
    manager._staged_audio_ready = lambda *, targets, **_kwargs: bool(targets.companion_tts)
    manager._job_runnable_now = lambda item: bool(item.tts_text and item.companion_tts_entries)
    item = speech_job()
    item.companion_tts_requested = True
    item.companion_tts_media_stream = "default"
    item.companion_tts_words_per_minute = 150
    assert manager._staged_route_ready(item)
    assert item.routing_stage == "fallback"
    assert item.companion_tts_entries == (output.entry_id,)
    assert item.companion_tts_entry_areas == {output.entry_id: "eingang"}

    calls, events, marked, successes = [], [], [], []

    async def async_call(domain, service, data, *, blocking):
        calls.append((domain, service, data, blocking))

    async def reading_hold(_job, _seconds):
        pass

    manager.hass.services = SimpleNamespace(async_call=async_call)
    manager._raise_if_cancelled = lambda _job: None
    manager._group_already_delivered = lambda _job, _channel: already_delivered
    manager._fire_channel_event = lambda event, _job, channel: events.append((event, channel))
    manager._mark_group_physical = lambda _job, channel: marked.append(channel)
    manager._record_channel_success = lambda _job, channel: successes.append(channel)
    manager._companion_tts_hold_time = lambda _text, _wpm: 0
    manager._async_reading_hold = reading_hold

    # The route was selected while open, then the door changed before the
    # physical Companion notify service. Recheck at the service boundary.
    manager.doors["binary_sensor.living_door"] = door_state
    manager.settings["fallback_check_door"] = check_door
    if not should_send and not already_delivered:
        with pytest.raises(staged.namespace["RoomRouteMoved"]):
            asyncio.run(manager._async_deliver_companion_tts(item, output))
        assert calls == events == marked == successes == []
        return

    asyncio.run(manager._async_deliver_companion_tts(item, output))
    channel = "companion_tts:relay-phone"
    assert successes == [channel]
    if already_delivered:
        assert calls == events == marked == []
    else:
        assert calls == [("notify", "mobile_app", {
            "target": ["relay-webhook"], "message": "TTS",
            "data": {"tts_text": item.tts_text},
        }, True)]
        assert events == [("announcement_hub_channel_started", channel)]
        assert marked == [channel]
