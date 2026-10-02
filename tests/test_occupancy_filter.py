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
    assert "output.area_id is not None" in manager
    assert "output.area_id in effective_areas" in manager
    assert "server_tts_enabled = bool(routed_selected[2])" in manager
    assert "if not plan.has_output and not occupancy_filter_active:" in manager


def test_occupied_only_defaults_true_and_does_not_touch_task_lifecycle() -> None:
    init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "ATTR_OCCUPIED_ONLY" in init
    assert "default=DEFAULT_OCCUPIED_ONLY" in init
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(") == 2



def test_fallback_requires_zero_candidates_and_optionally_open_door() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    config_flow = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    assert "if occupancy_filter_active and not plan.has_output:" in manager
    assert "def _fallback_area_id(" in manager
    assert "def _fallback_door_allows(" in manager
    assert 'self.hass.states.async_all("binary_sensor")' in manager
    assert 'state.attributes.get("device_class") != "door"' in manager
    assert "state.state == STATE_ON" in manager
    assert "CONF_FALLBACK_ROOM" in config_flow
    assert "CONF_FALLBACK_CHECK_DOOR" in config_flow


def test_fallback_does_not_regress_background_task_lifecycle() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(") == 2



def test_occupancy_ui_uses_live_dropdown_not_free_text() -> None:
    flow = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    assert "async def async_step_occupancy(" in flow
    assert "async def async_step_occupancy_source(" in flow
    assert 'return ["__state__", *attributes]' in flow
    assert 'translation_key="occupancy_source"' in flow
    source_block = flow[
        flow.index("async def async_step_occupancy_source"):
        flow.index("async def async_step_queue")
    ]
    assert "selector.SelectSelector(" in source_block
    assert "selector.TextSelector()" not in source_block


def test_occupancy_and_fallback_are_not_on_generic_outputs_page() -> None:
    import json

    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    for section in ("config", "options"):
        outputs = strings[section]["step"]["outputs"]["data"]
        assert "occupancy_sensor" not in outputs
        assert "occupancy_attribute" not in outputs
        assert "fallback_room" not in outputs
        assert "fallback_check_door" not in outputs
        occupancy = strings[section]["step"]["occupancy"]["data"]
        assert {"occupancy_sensor", "fallback_room", "fallback_check_door"} <= set(occupancy)
        source = strings[section]["step"]["occupancy_source"]["data"]
        assert set(source) == {"occupancy_attribute"}
