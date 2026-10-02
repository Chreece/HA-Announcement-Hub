"""Contracts for per-device notification scope and log-level routing."""

from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_setup_has_per_concrete_output_notification_routing_step() -> None:
    flow=(C/"config_flow.py").read_text()
    assert "def _prepare_notify_routing_steps(" in flow
    assert "async def async_step_notification_routing(" in flow
    assert "CONF_NOTIFY_POLICIES" in flow
    assert 'translation_key="notify_scope"' in flow
    assert 'translation_key="notify_level"' in flow


def test_runtime_filters_level_and_only_room_scope_by_occupancy() -> None:
    manager=(C/"manager.py").read_text()
    assert "def _notify_policy(" in manager
    assert "def _notify_level_allowed(" in manager
    assert "NOTIFY_SCOPE_GENERAL" in manager
    assert "LEVEL_PRIORITY.get(level" in manager
    assert "self._notify_policy(output)[0] == NOTIFY_SCOPE_GENERAL" in manager


def test_general_outputs_freeze_without_area_binding() -> None:
    manager=(C/"manager.py").read_text()
    start=manager.index("notify_output_areas = {", manager.index("selected, notify_records"))
    block=manager[start:manager.index("configured_profiles =", start)]
    assert "NOTIFY_SCOPE_GENERAL" in block
    assert "None" in block


def test_existing_outputs_have_backward_compatible_policy_defaults() -> None:
    manager=(C/"manager.py").read_text()
    assert "NOTIFY_SCOPE_ROOM if output.area_id else NOTIFY_SCOPE_GENERAL" in manager
    assert "DEFAULT_NOTIFY_MIN_LEVEL" in manager


def test_translations_expose_scope_and_level_choices() -> None:
    strings=json.loads((C/"strings.json").read_text())
    for section in ("config","options"):
        outputs = strings[section]["step"]["outputs"]["data"]
        assert "notify_room_outputs" in outputs
        assert "notify_info_outputs" in outputs
        assert "notify_warning_outputs" in outputs
        assert "notify_error_outputs" in outputs
        assert "notify_critical_outputs" in outputs
