"""Regression contracts for occupied-area output filtering."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def test_occupancy_source_supports_state_attribute_and_common_list_formats() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "def _occupied_area_ids(" in manager
    assert "CONF_OCCUPANCY_SENSOR" in manager
    assert "CONF_OCCUPANCY_ATTRIBUTE" in manager
    assert "state.attributes.get(attribute) if attribute else state.state" in manager
    assert "json.loads(value)" in manager
    assert 're.split(r"[,;\\n]+", value)' in manager


def test_occupancy_filter_is_applied_before_job_is_frozen() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "occupancy_filter_active = occupied_area_ids is not None" in manager
    assert "if output.area_id is not None and output.area_id in effective_areas" in manager
    assert "server_tts_enabled = bool(selected[2])" in manager
    assert "if not plan.has_output and not occupancy_filter_active:" in manager


def test_occupied_only_defaults_true_and_does_not_touch_task_lifecycle() -> None:
    init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "ATTR_OCCUPIED_ONLY" in init
    assert "default=DEFAULT_OCCUPIED_ONLY" in init
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(") == 2
