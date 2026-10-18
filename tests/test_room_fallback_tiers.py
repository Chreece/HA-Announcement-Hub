"""Executable routing priority tests for Air Quality Advisor room announcements.

The real AnnouncementManager stage/planner methods are compiled from source;
only HA's entity registry, services, clocks and integration outputs are faked.
"""

from __future__ import annotations

import ast
from collections import deque
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
SOURCE = (COMPONENT / "manager.py").read_text(encoding="utf-8")

if "homeassistant.const" not in sys.modules:
    ha = ModuleType("homeassistant")
    hc = ModuleType("homeassistant.const")

    class Platform(StrEnum):
        SENSOR = "sensor"

    hc.Platform = Platform
    ha.const = hc
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.const"] = hc

package = ModuleType("announcement_hub")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("announcement_hub", package)
for name in ("const", "models", "room_routing"):
    full = f"announcement_hub.{name}"
    if full not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            full, COMPONENT / f"{name}.py"
        )
        assert spec and spec.loader
        obj = importlib.util.module_from_spec(spec)
        sys.modules[full] = obj
        spec.loader.exec_module(obj)

from announcement_hub.models import AnnouncementJob, build_delivery_plan  # noqa: E402
from announcement_hub.models import tts_allowed_for_level, utcnow_iso  # noqa: E402
from announcement_hub.room_routing import (  # noqa: E402
    STAGES, elapsed_seconds, next_stage,
)


def load_real_methods():
    tree = ast.parse(SOURCE)
    klass = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                 and x.name == "AnnouncementManager")
    methods = {
        "_room_stage_candidate",
        "_apply_room_stage",
        "_room_candidate_ready",
        "_advance_room_stage",
        "_refresh_room_fallback",
        "_next_runnable_job",
    }
    selected = [x for x in klass.body
                if isinstance(x, ast.FunctionDef) and x.name in methods]
    assert len(selected) == len(methods)
    namespace = {
        "Mapping": Mapping,
        "STAGES": STAGES,
        "next_stage": next_stage,
        "elapsed_seconds": elapsed_seconds,
        "utcnow_iso": utcnow_iso,
        "build_delivery_plan": build_delivery_plan,
        "tts_allowed_for_level": tts_allowed_for_level,
        "LEVEL_CRITICAL": "critical",
        "LEVEL_INFO": "info",
        "TTS_LEVEL_NEVER": "never",
        "CONF_TTS_MIN_LEVEL": "tts_min_level",
        "DEFAULT_TTS_MIN_LEVEL": "warning",
        "CONF_TTS_MEDIA_PLAYER": "tts_media_player",
        "CONF_NOTIFY_PROFILES": "notify_profiles",
        "NOTIFY_SCOPE_GENERAL": "general",
        "NOTIFY_SCOPE_ROOM": "room",
        "INTEGRATION_MOBILE_APP": "mobile_app",
        "resolve_notify_profile": lambda profiles, owner: {},
        "entity_area_id": lambda hass, entity: getattr(hass, "areas", {}).get(entity),
        "resolve_notify_outputs": lambda hass, refs: tuple(
            hass.outputs[ref] for ref in refs
        ),
        "resolve_companion_tts_outputs": lambda hass, refs: (),
        "notify_output_available": lambda hass, output: (
            output.ref in hass.ready
        ),
        "companion_output_available": lambda hass, output: False,
    }
    exec(compile("from __future__ import annotations\n" + "\n\n".join(
        ast.unparse(node) for node in selected
    ), "real-announcement-routing", "exec"), namespace)
    return {name: namespace[name] for name in methods}


METHODS = load_real_methods()


class Harness:
    _room_stage_candidate = METHODS["_room_stage_candidate"]
    _apply_room_stage = METHODS["_apply_room_stage"]
    _room_candidate_ready = METHODS["_room_candidate_ready"]
    _advance_room_stage = METHODS["_advance_room_stage"]
    _refresh_room_fallback = METHODS["_refresh_room_fallback"]
    _next_runnable_job = METHODS["_next_runnable_job"]

    def __init__(self):
        self.settings = {"tts_min_level": "warning"}
        self.hass = SimpleNamespace(
            outputs={}, areas={}, ready=set()
        )
        self.occupied = ("wohnzimmer",)
        self.fallback_area = "eingang"
        self.door_open = False
        self.minimums = {}
        self._queue = deque()
        self.saved = 0

    def add_notify(self, ref, area, minimum="info", scope=None, ready=False):
        self.hass.outputs[ref] = SimpleNamespace(
            ref=ref, area_id=area,
            integration="mobile_app" if "phone" in ref else "nfandroidtv"
        )
        self.minimums[ref] = (
            scope or ("room" if area else "general"),
            minimum,
        )
        if ready:
            self.hass.ready.add(ref)

    def _notify_policy(self, output):
        return self.minimums[output.ref]

    def _configured_outputs(self):
        return (
            ("tts.piper",),
            tuple(self.hass.outputs),
            (),
            (),
            (),
        )

    def _notify_level_allowed(self, level, minimum):
        weights = {"debug": 0, "info": 1, "success": 1,
                   "warning": 2, "error": 3, "critical": 4}
        return weights[level] >= weights[minimum]

    def _occupied_area_ids(self):
        return self.occupied

    def _fallback_area_id(self):
        return self.fallback_area

    def _fallback_door_allows(self, areas):
        return self.door_open

    def _job_runnable_now(self, job):
        return bool(
            job.notify_text and any(
                output in self.hass.ready for output in job.notify_outputs
            )
        )

    def _schedule_save(self):
        self.saved += 1

    def _notify_update(self):
        pass

    _availability_timeout = 10.0


def new_job(*, areas=("kouzina",), level="info", occupied_only=True):
    plan = build_delivery_plan(
        text_tts=None, text_notify=None,
        level=level, minimum_tts_level="never",
        tts_engines=(), notify_outputs=(),
        room_tts_players=(), snapcast_clients=(),
        companion_tts_entries=(), server_tts_enabled=False,
    )
    return AnnouncementJob.create(
        text_tts=None, text_notify="Άνοιξε τα παράθυρα στην κουζίνα",
        outputs=areas, requested_services=[], level=level, title="Αέρας",
        notify_data={}, language="el-GR", tts_options={}, tts_cache=True,
        plan=plan, room_fallback=True, strict_targets=True,
        requested_area_ids=areas, routing_occupied_only=occupied_only,
        routing_stage_started_at=utcnow_iso(),
        routing_source_tts=None,
        routing_source_notify="Άνοιξε τα παράθυρα στην κουζίνα",
    )


def age_stage(job):
    job.routing_stage_started_at = (
        datetime.now(UTC) - timedelta(seconds=30)
    ).isoformat()


def test_kitchen_has_matching_info_notify_and_does_not_broadcast():
    h = Harness()
    h.occupied = ("kouzina",)
    h.add_notify("entity:notify.kitchen_tv", "kouzina", ready=True)
    h.add_notify("entity:notify.phone", None, ready=True)
    job = new_job()
    assert h._refresh_room_fallback(job) is True
    assert job.routing_stage == "explicit"
    assert job.outputs == ("kouzina",)
    assert job.notify_outputs == ("entity:notify.kitchen_tv",)
    assert job.tts_text is None
    assert not job.server_tts_enabled


def test_missing_kitchen_device_moves_immediately_to_occupied_room():
    h = Harness()
    h.add_notify("entity:notify.living_tv", "wohnzimmer", ready=True)
    h.add_notify("entity:notify.phone", None, ready=True)
    job = new_job()
    assert h._refresh_room_fallback(job)
    assert job.routing_stage == "occupied"
    assert job.outputs == ("wohnzimmer",)
    assert job.notify_outputs == ("entity:notify.living_tv",)


def test_room_device_below_info_threshold_falls_back_without_forcing_tts():
    h = Harness()
    h.occupied = ("kouzina", "wohnzimmer")
    h.add_notify("entity:notify.kitchen_tv", "kouzina",
                 minimum="warning", ready=True)
    h.add_notify("entity:notify.living_tv", "wohnzimmer", ready=True)
    job = new_job()
    assert h._refresh_room_fallback(job)
    assert job.routing_stage == "occupied"
    assert job.notify_outputs == ("entity:notify.living_tv",)
    assert job.tts_engines == ()
    assert job.tts_text is None


def test_unavailable_kitchen_waits_grace_before_occupied_fallback():
    h = Harness()
    h.occupied = ("kouzina", "wohnzimmer")
    h.add_notify("entity:notify.kitchen_tv", "kouzina", ready=False)
    h.add_notify("entity:notify.living_tv", "wohnzimmer", ready=True)
    job = new_job()
    assert h._refresh_room_fallback(job) is False
    assert job.routing_stage == "explicit"
    assert job.notify_outputs == ("entity:notify.kitchen_tv",)
    age_stage(job)
    assert h._refresh_room_fallback(job) is True
    assert job.routing_stage == "occupied"
    assert job.notify_outputs == ("entity:notify.living_tv",)


def test_unavailable_occupied_waits_before_door_gated_fallback():
    h = Harness()
    h.door_open = True
    h.add_notify("entity:notify.living_tv", "wohnzimmer")
    h.add_notify("entity:notify.entry_tv", "eingang", ready=True)
    job = new_job()
    assert not h._refresh_room_fallback(job)
    assert job.routing_stage == "occupied"
    age_stage(job)
    assert h._refresh_room_fallback(job)
    assert job.routing_stage == "fallback_room"
    assert job.notify_outputs == ("entity:notify.entry_tv",)


def test_closed_door_blocks_fallback_room_and_uses_general_notify():
    h = Harness()
    h.add_notify("entity:notify.entry_tv", "eingang", ready=True)
    h.add_notify("entity:notify.phone", None, ready=True)
    job = new_job()
    assert h._refresh_room_fallback(job)
    assert job.routing_stage == "general"
    assert job.notify_outputs == ("entity:notify.phone",)
    assert job.outputs == ()


def test_unavailable_general_waits_indefinitely_then_delivers():
    h = Harness()
    h.add_notify("entity:notify.phone", None, ready=False)
    job = new_job()
    h._queue.append(job)
    assert h._next_runnable_job() is None
    assert job.routing_stage == "general"
    age_stage(job)
    assert h._next_runnable_job() is None
    assert job.routing_stage == "waiting"
    assert len(h._queue) == 1
    # Hours later the device comes online: same ID/text, no broadcast.
    h.hass.ready.add("entity:notify.phone")
    assert h._next_runnable_job() is job
    assert job.routing_stage == "general"
    assert job.notify_outputs == ("entity:notify.phone",)


def test_configured_new_room_output_can_revive_waiting_message():
    h = Harness()
    h.occupied = ("kouzina",)
    job = new_job()
    h._queue.append(job)
    assert h._next_runnable_job() is None
    assert job.routing_stage == "waiting"
    assert len(h._queue) == 1
    h.add_notify("entity:notify.kitchen_tv", "kouzina", ready=True)
    assert h._next_runnable_job() is job
    assert job.routing_stage == "explicit"
    assert job.notify_outputs == ("entity:notify.kitchen_tv",)


def test_occupied_only_intersects_explicit_room_and_uses_occupied():
    h = Harness()
    h.add_notify("entity:notify.kitchen_tv", "kouzina", ready=True)
    h.add_notify("entity:notify.living_tv", "wohnzimmer", ready=True)
    job = new_job(occupied_only=True)
    assert h._refresh_room_fallback(job)
    assert job.routing_stage == "occupied"
    assert job.notify_outputs == ("entity:notify.living_tv",)


def test_no_occupancy_source_leaves_explicit_room_active():
    h = Harness()
    h.occupied = None
    h.add_notify("entity:notify.kitchen_tv", "kouzina", ready=True)
    job = new_job(occupied_only=True)
    assert h._refresh_room_fallback(job)
    assert job.routing_stage == "explicit"
    assert job.notify_outputs == ("entity:notify.kitchen_tv",)


def test_indefinite_job_survives_store_roundtrip_with_original_room():
    job = new_job()
    job.routing_stage = "waiting"
    restored = AnnouncementJob.from_dict(job.to_dict())
    assert restored.job_id == job.job_id
    assert restored.routing_stage == "waiting"
    assert restored.room_fallback is True
    assert restored.requested_area_ids == ("kouzina",)
    assert restored.routing_source_notify == job.routing_source_notify
    assert "routing_source_notify" not in restored.public_dict()
    assert restored.public_dict()["routing_stage"] == "waiting"


def test_old_jobs_keep_legacy_behavior_on_load():
    job = new_job()
    legacy = job.to_dict()
    for key in (
        "room_fallback", "requested_area_ids", "routing_occupied_only",
        "routing_stage", "routing_stage_started_at",
        "routing_source_tts", "routing_source_notify",
    ):
        legacy.pop(key)
    restored = AnnouncementJob.from_dict(legacy)
    assert restored.room_fallback is False
    assert restored.routing_stage == "explicit"
    assert restored.routing_source_notify == restored.text_notify


def test_source_prevents_rejected_and_expired_info_announcements():
    assert "and not room_fallback" in SOURCE
    assert "if not requested and not plan.has_output:" in SOURCE
    assert "room_fallback = True" in SOURCE
    assert "self._refresh_room_fallback(job)" in SOURCE
    assert "self._expire_waiting_job(job)" not in SOURCE[
        SOURCE.index("    def _next_runnable_job("):
        SOURCE.index("    async def _async_process_job(")
    ]
    assert "self._requeue_undelivered_room_job(job)" in SOURCE
