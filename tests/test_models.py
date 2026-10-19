"""Pure unit tests for level-aware delivery plans and persistent jobs."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from enum import StrEnum
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = ROOT / "custom_components" / "announcement_hub"

# Keep these model tests independent of a full Home Assistant installation while
# still letting const.py use the real Platform enum in production.
if "homeassistant.const" not in sys.modules:
    homeassistant = ModuleType("homeassistant")
    homeassistant_const = ModuleType("homeassistant.const")

    class Platform(StrEnum):
        SENSOR = "sensor"

    homeassistant_const.Platform = Platform
    homeassistant.const = homeassistant_const
    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.const"] = homeassistant_const

package = ModuleType("announcement_hub")
package.__path__ = [str(MODULE_ROOT)]
sys.modules.setdefault("announcement_hub", package)

for module_name in ("const", "models"):
    spec = importlib.util.spec_from_file_location(
        f"announcement_hub.{module_name}", MODULE_ROOT / f"{module_name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from announcement_hub.models import (  # noqa: E402
    AnnouncementJob,
    build_delivery_plan,
    tts_allowed_for_level,
)


def test_tts_level_threshold_and_critical_override() -> None:
    assert not tts_allowed_for_level("info", "warning")
    assert tts_allowed_for_level("warning", "warning")
    assert tts_allowed_for_level("error", "warning")
    assert not tts_allowed_for_level("error", "never")
    assert tts_allowed_for_level("critical", "never")


def test_below_tts_threshold_prefers_visual_output() -> None:
    plan = build_delivery_plan(
        text_tts="Spoken-only information",
        text_notify=None,
        level="info",
        minimum_tts_level="warning",
        tts_engines=["tts.piper"],
        notify_outputs=["entity:notify.tv"],
        snapcast_clients=["media_player.living_room_snapcast"],
        companion_tts_entries=["phone-entry"],
        server_tts_enabled=True,
    )
    assert plan.tts_text is None
    assert plan.notify_text is None
    assert plan.tts_suppressed_by_level is True
    assert plan.has_visual_output is False
    assert plan.has_audible_output is False


def test_explicit_written_text_wins_below_tts_threshold() -> None:
    plan = build_delivery_plan(
        text_tts="Long spoken version",
        text_notify="Short visual version",
        level="debug",
        minimum_tts_level="info",
        tts_engines=["tts.piper"],
        notify_outputs=["entity:notify.phone"],
        snapcast_clients=[],
        companion_tts_entries=[],
        server_tts_enabled=True,
    )
    assert plan.tts_text is None
    assert plan.notify_text == "Short visual version"


def test_critical_uses_both_channels_even_when_one_text_is_missing() -> None:
    plan = build_delivery_plan(
        text_tts="Smoke detected",
        text_notify=None,
        level="critical",
        minimum_tts_level="never",
        tts_engines=["tts.piper", "tts.cloud", "tts.piper"],
        notify_outputs=["entity:notify.tv", "entity:notify.tv"],
        snapcast_clients=["media_player.kitchen_snapcast"],
        companion_tts_entries=["phone-entry"],
        server_tts_enabled=True,
    )
    assert plan.tts_text == "Smoke detected"
    assert plan.notify_text is None
    assert plan.tts_engines == ("tts.piper",)
    assert plan.notify_outputs == ("entity:notify.tv",)
    assert plan.has_visual_output is False
    assert plan.has_audible_output is True


def test_no_area_binding_is_preserved_as_empty_broadcast_tuple() -> None:
    plan = build_delivery_plan(
        text_tts="Every configured output",
        text_notify="Every configured output",
        level="info",
        minimum_tts_level="debug",
        tts_engines=["tts.piper"],
        notify_outputs=["entity:notify.tv"],
        snapcast_clients=["media_player.living_room_snapcast"],
        companion_tts_entries=[],
        server_tts_enabled=True,
    )
    job = AnnouncementJob.create(
        text_tts="Every configured output",
        text_notify="Every configured output",
        outputs=[],
        requested_services=[],
        level="info",
        title="Test",
        notify_data={},
        language=None,
        tts_options={},
        tts_cache=True,
        plan=plan,
    )
    assert job.outputs == ()
    assert job.notify_outputs == ("entity:notify.tv",)
    assert job.snapcast_clients == ("media_player.living_room_snapcast",)


def test_job_round_trip_preserves_output_and_room_binding() -> None:
    plan = build_delivery_plan(
        text_tts="Room-specific",
        text_notify="Written",
        level="warning",
        minimum_tts_level="info",
        tts_engines=["tts.piper"],
        notify_outputs=[
            "entity:notify.wall_display",
            "service:notify.mobile_app_phone",
        ],
        snapcast_clients=["media_player.kitchen_snapcast"],
        companion_tts_entries=["phone-entry"],
        server_tts_enabled=True,
    )
    job = AnnouncementJob.create(
        text_tts="Room-specific",
        text_notify="Written",
        outputs=["living_room", "kitchen"],
        requested_services=["all"],
        level="warning",
        title="Test",
        notify_data={"priority": "high"},
        language="el-GR",
        tts_options={"voice": "test"},
        tts_cache=True,
        plan=plan,
        tts_media_player="media_player.mpd",
        tts_player_area=None,
        notify_output_areas={
            "entity:notify.wall_display": "living_room",
            "service:notify.mobile_app_phone": None,
        },
        notify_output_profiles={
            "entity:notify.wall_display": {
                "max_length": 193,
                "position": "bottom-left",
                "integration_data": {"secret": "do-not-expose"},
            },
            "service:notify.mobile_app_phone": {
                "max_length": 500,
                "replace_parts": True,
            },
        },
        snapcast_client_areas={
            "media_player.kitchen_snapcast": "kitchen"
        },
        companion_tts_entry_areas={"phone-entry": "living_room"},
        companion_tts_media_stream="alarm_stream",
        companion_tts_words_per_minute=165,
    )
    job.media_source_ids["tts.piper"] = "media-source://tts/test"
    job.group_id = "group-123"
    job.related_job_ids = ("child-456",)
    job.delivered_physical.append("notify:entity:notify.wall_display")

    restored = AnnouncementJob.from_dict(job.to_dict())
    assert restored.job_id == job.job_id
    assert restored.group_id == "group-123"
    assert restored.related_job_ids == ("child-456",)
    assert restored.delivered_physical == ["notify:entity:notify.wall_display"]
    assert restored.outputs == ("living_room", "kitchen")
    assert restored.requested_services == ("all",)
    assert restored.tts_engines == ("tts.piper",)
    assert restored.notify_outputs == (
        "entity:notify.wall_display",
        "service:notify.mobile_app_phone",
    )
    assert restored.snapcast_clients == ("media_player.kitchen_snapcast",)
    assert restored.companion_tts_entries == ("phone-entry",)
    assert restored.tts_media_player == "media_player.mpd"
    assert restored.notify_output_areas == {
        "entity:notify.wall_display": "living_room",
        "service:notify.mobile_app_phone": None,
    }
    assert restored.notify_output_profiles[
        "entity:notify.wall_display"
    ]["position"] == "bottom-left"
    assert restored.notify_output_profiles[
        "service:notify.mobile_app_phone"
    ]["replace_parts"] is True
    assert restored.snapcast_client_areas == {
        "media_player.kitchen_snapcast": "kitchen"
    }
    assert restored.companion_tts_entry_areas == {
        "phone-entry": "living_room"
    }
    assert restored.companion_tts_media_stream == "alarm_stream"
    assert restored.companion_tts_words_per_minute == 165
    assert restored.media_source_ids == {"tts.piper": "media-source://tts/test"}
    assert restored.tts_cache is True
    public = restored.public_dict()
    assert "integration_data" not in public["notify_output_profiles"][
        "entity:notify.wall_display"
    ]


def test_v01_stored_job_best_effort_migration() -> None:
    legacy = {
        "job_id": "legacy",
        "created_at": "2026-10-01T00:00:00+00:00",
        "text_tts": "Legacy",
        "text_notify": "Legacy visual",
        "outputs": ["living_room"],
        "requested_services": [],
        "level": "info",
        "title": "Legacy",
        "notify_data": {},
        "language": None,
        "tts_options": {},
        "tts_cache": True,
        "tts_providers": ["tts.piper"],
        "notify_entities": ["notify.wall_display"],
        "notify_services": ["notify.mobile_app_phone"],
        "tts_text": "Legacy",
        "notify_text": "Legacy visual",
    }
    restored = AnnouncementJob.from_dict(legacy)
    assert restored.tts_engines == ("tts.piper",)
    assert restored.notify_outputs == (
        "entity:notify.wall_display",
        "service:notify.mobile_app_phone",
    )
    assert restored.server_tts_enabled is True


def test_public_status_omits_message_content_and_title() -> None:
    plan = build_delivery_plan(
        text_tts="Private spoken message",
        text_notify="Private written message",
        level="info",
        minimum_tts_level="debug",
        tts_engines=["tts.piper"],
        notify_outputs=["entity:notify.wall_display"],
        snapcast_clients=[],
        companion_tts_entries=[],
        server_tts_enabled=True,
    )
    job = AnnouncementJob.create(
        text_tts="Private spoken message",
        text_notify="Private written message",
        outputs=["living_room"],
        requested_services=[],
        level="info",
        title="Private title",
        notify_data={},
        language=None,
        tts_options={},
        tts_cache=True,
        plan=plan,
    )

    public = job.public_dict()
    assert "text_tts" not in public
    assert "text_notify" not in public
    assert "title" not in public
    private = job.public_dict(include_text=True)
    assert private["title"] == "Private title"
    assert private["text_tts"] == "Private spoken message"


def test_critical_visual_only_source_does_not_create_speech() -> None:
    """A dedicated notify text remains written even at Critical severity."""
    plan = build_delivery_plan(
        text_tts=None,
        text_notify="Window is open",
        level="critical",
        minimum_tts_level="never",
        tts_engines=["tts.piper"],
        notify_outputs=["entity:notify.tv"],
        room_tts_players=["media_player.kitchen"],
        snapcast_clients=[],
        companion_tts_entries=[],
        server_tts_enabled=False,
    )
    assert plan.tts_text is None
    assert plan.notify_text == "Window is open"
    assert not plan.has_audible_output
    assert plan.has_visual_output


def test_noncritical_visual_only_does_not_invent_speech() -> None:
    plan = build_delivery_plan(
        text_tts=None,
        text_notify="Window is open",
        level="info",
        minimum_tts_level="debug",
        tts_engines=["tts.piper"],
        notify_outputs=["entity:notify.tv"],
        room_tts_players=["media_player.kitchen"],
        snapcast_clients=[],
        companion_tts_entries=[],
        server_tts_enabled=False,
    )
    assert plan.tts_text is None
    assert plan.notify_text == "Window is open"



def test_ai_trace_is_persisted_and_backwards_compatible() -> None:
    plan = build_delivery_plan(
        text_tts="Door open", text_notify="Door open", level="info",
        minimum_tts_level="debug", tts_engines=["tts.piper"],
        notify_outputs=["entity:notify.phone"],
        room_tts_players=["media_player.kitchen"],
        snapcast_clients=[], companion_tts_entries=[],
        server_tts_enabled=False,
    )
    original = AnnouncementJob.create(
        text_tts="Door open", text_notify="Door open",
        outputs=[], requested_services=[], level="info", title="Door",
        notify_data={}, language=None, tts_options={}, tts_cache=True,
        plan=plan, ai={
            "enabled": True, "source": "integration",
            "status": "fallback_original", "agent": "conversation.home",
            "attempted": True,
        },
    )
    restored = AnnouncementJob.from_dict(original.to_dict())
    assert restored.ai["status"] == "fallback_original"
    assert restored.public_dict()["ai"]["enabled"] is True
    legacy = original.to_dict()
    legacy.pop("ai")
    assert AnnouncementJob.from_dict(legacy).ai == {}


def test_click_action_round_trip_and_legacy_default() -> None:
    plan = build_delivery_plan(
        text_tts=None, text_notify="Door open",
        level="info", minimum_tts_level="info",
        tts_engines=[], notify_outputs=["entity:notify.phone"],
        snapcast_clients=[], companion_tts_entries=[],
        server_tts_enabled=False,
    )
    job = AnnouncementJob.create(
        text_tts=None, text_notify="Door open",
        outputs=[], requested_services=["mobile_app"],
        level="info", title="Door", notify_data={"tag": "door"},
        language=None, tts_options=None, tts_cache=True,
        plan=plan, click_action="/lovelace/cameras",
    )
    restored = AnnouncementJob.from_dict(job.to_dict())
    assert restored.click_action == "/lovelace/cameras"
    assert restored.requested_services == ("mobile_app",)
    assert "click_action" not in restored.public_dict()
    assert restored.public_dict(include_text=True)["click_action"] == "/lovelace/cameras"
    old_data = job.to_dict()
    old_data.pop("click_action")
    assert AnnouncementJob.from_dict(old_data).click_action is None

def test_strict_targets_persist_in_job_and_legacy_jobs_default_false() -> None:
    plan = build_delivery_plan(
        text_tts=None, text_notify="Movement detected",
        level="critical", minimum_tts_level="never",
        tts_engines=[], notify_outputs=["entity:notify.phone"],
        room_tts_players=[], snapcast_clients=[],
        companion_tts_entries=[], server_tts_enabled=False,
    )
    job = AnnouncementJob.create(
        text_tts=None, text_notify="Movement detected",
        outputs=[], requested_services=["mobile_app"],
        level="critical", title="Alert", notify_data={},
        language=None, tts_options={}, tts_cache=True,
        plan=plan, strict_targets=True,
    )
    assert job.strict_targets
    assert job.public_dict()["strict_targets"] is True
    restored = AnnouncementJob.from_dict(job.to_dict())
    assert restored.strict_targets
    old_job = job.to_dict()
    old_job.pop("strict_targets")
    assert AnnouncementJob.from_dict(old_job).strict_targets is False
