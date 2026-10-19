"""Executable contracts for independent recipient and service selection."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "custom_components" / "announcement_hub"
MANAGER = (C / "manager.py").read_text(encoding="utf-8")
spec = importlib.util.spec_from_file_location(
    "announcement_hub_composable_targeting_test", C / "targeting.py"
)
assert spec and spec.loader
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)

CFG = (
    ("tts.piper",),
    ("entity:notify.tv", "entity:notify.phone"),
    ("media_player.kitchen",),
    ("media_player.kitchen_snapcast",),
    ("phone-entry",),
)


@pytest.mark.parametrize("services,expected", [
    ([], (("tts.piper",), ("entity:notify.tv", "entity:notify.phone"),
          ("media_player.kitchen",), ("media_player.kitchen_snapcast",),
          ("phone-entry",))),
    (["notification"], ((), CFG[1], (), (), ())),
    (["notify"], ((), CFG[1], (), (), ())),
    (["tts"], (CFG[0], (), CFG[2], CFG[3], CFG[4])),
    (["snapcast"], (CFG[0], (), (), CFG[3], ())),
    (["companion_tts"], ((), (), (), (), CFG[4])),
    (["notification", "companion_tts"], ((), CFG[1], (), (), CFG[4])),
    (["all"], (CFG[0], CFG[1], CFG[2], CFG[3], CFG[4])),
])
def test_service_filters_channels_but_does_not_add_physical_recipients(
    services, expected
):
    assert target.filter_selected_outputs(CFG, services) == expected


def test_engine_is_not_a_device_and_does_not_create_speakers():
    selected = (("tts.piper",), (), (), (), ())
    assert target.filter_selected_outputs(selected, ["tts"]) == (
        (), (), (), (), ()
    )
    assert not target.physical_keys(selected)


def test_exact_notify_only_never_inherits_snapcast_even_for_critical():
    selected = ((), ("entity:notify.phone",), (), (), ())
    assert target.filter_selected_outputs(selected, ["all"]) == selected
    assert target.filter_selected_outputs(selected, ["notification"]) == selected
    assert target.filter_selected_outputs(selected, ["tts"]) == (
        (), (), (), (), ()
    )


def test_composite_physical_overlap_is_removed_only_from_area_branch():
    explicit = ((), ("entity:notify.tv",), (), (), ())
    room = (("tts.piper",), ("entity:notify.tv", "entity:notify.phone"),
            (), ("media_player.kitchen_snapcast",), ())
    excluded = target.physical_keys(explicit)
    result = target.restrict_physical_keys(room, excluded)
    assert result[1] == ("entity:notify.phone",)
    assert result[3] == ("media_player.kitchen_snapcast",)
    assert result[0] == ("tts.piper",)
    assert explicit[1] == ("entity:notify.tv",)


@pytest.mark.parametrize("invalid", [
    ["nfandroidtv"], ["mobile_app"], ["integration:mobile_app"],
    ["notify.tv"], [""], ["notification", "unknown"],
])
def test_a_service_must_not_be_confused_with_a_device_or_integration(invalid):
    with pytest.raises(ValueError):
        target.channel_selection(invalid)


def test_action_schema_has_independent_target_selectors():
    description = yaml.safe_load((C / "services.yaml").read_text())
    fields = description["send"]["fields"]["routing"]["fields"]
    assert {"area", "integration", "device", "entity", "service"} <= set(fields)
    assert "output" not in fields
    assert "area" in fields["area"]["selector"]
    assert fields["device"]["selector"]["device"]["multiple"] is True
    assert fields["entity"]["selector"]["entity"]["multiple"] is True
    assert fields["service"]["selector"]["select"]["multiple"] is True


def test_send_wiring_uses_service_only_for_channels_and_area_for_rooms():
    init = (C / "__init__.py").read_text()
    for contract in (
        "areas=call.data.get(ATTR_AREA)",
        "integrations=call.data.get(ATTR_INTEGRATION)",
        "devices=call.data.get(ATTR_DEVICE)",
        "entities=call.data.get(ATTR_ENTITY)",
        "channels=call.data.get(ATTR_SERVICE)",
        "requested_services=None",
    ):
        assert contract in init


def test_mixed_area_recipient_request_is_fanned_out_as_independent_jobs():
    outer = MANAGER[
        MANAGER.index("    async def async_enqueue("):
        MANAGER.index("    async def async_clear_queue(")
    ]
    assert "if explicit_area_routing and requested and not _fanout:" in outer
    assert "area_job = await self.async_enqueue(" in outer
    assert "explicit_job = await self.async_enqueue(" in outer
    assert "area_job.related_job_ids = (explicit_job.job_id,)" in outer
    assert "explicit_job.group_id = area_job.job_id" in outer
    assert "_group_token=group_token" in outer
    assert "area_job = await self.async_enqueue(" in outer
    assert "_excluded_physical=physical_keys(static)" not in outer
    assert "room_fallback_routing = explicit_area_routing" in outer
    assert "occupancy_filter_active = False" in outer
    # The dynamic worker may never expand a fixed recipient selection.
    assert "filter_selected_outputs(" in MANAGER
    assert "restrict_physical_keys(" in MANAGER


def test_group_id_cancels_related_job_and_survives_restarts():
    manager = MANAGER[
        MANAGER.index("    async def async_cancel("):
        MANAGER.index("    async def _async_worker(")
    ]
    assert "for sibling_id in group.related_job_ids" in manager
    assert "await self.async_cancel(sibling_id, _cascade=False)" in manager
    model = (C / "models.py").read_text()
    assert "payload.setdefault(\"related_job_ids\", ())" in model
    assert "payload.setdefault(\"group_id\", None)" in model


def test_severity_never_overrides_selected_text_channel():
    model = (C / "models.py").read_text()
    assert "tts_text = text_tts if (audible or force_tts) else None" in model
    assert "notify_text = text_notify" in model
    routing = MANAGER[MANAGER.index("    def _prepare_staged_route("):]
    assert "job.tts_text = job.text_tts if audible else None" in routing
    assert "job.notify_text = job.text_notify if job.notify_outputs else None" in routing


def test_configured_device_registry_identity_does_not_expand_other_hardware():
    assert "device_reg.async_get(device_id)" in MANAGER
    assert "entry.device_id == device_id" in MANAGER
    assert "entry.entity_id in allowed" in MANAGER
    assert "Device {device_id} has no configured Announcement Hub output" in MANAGER


def test_combined_service_targets_are_a_union_not_an_intersection():
    example = yaml.safe_load("""
    action: notify.announcement_hub
    data:
      area:
        - kitchen
      entity:
        - notify.mobile_phone
      integration:
        - nfandroidtv
      service:
        - notification
      text_notify: "Window open"
    """)
    data = example["data"]
    assert data["area"] == ["kitchen"]
    assert data["entity"] == ["notify.mobile_phone"]
    assert data["integration"] == ["nfandroidtv"]
    assert data["service"] == ["notification"]
    assert "output" not in data
