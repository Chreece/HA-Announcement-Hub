"""Contracts for the four-stage auto-discovery setup flow."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "custom_components" / "announcement_hub"


def test_only_four_visible_setup_steps_remain() -> None:
    strings = json.loads((C / "strings.json").read_text())
    expected = {"outputs", "tts", "notification_profile", "queue"}
    assert set(strings["config"]["step"]) == expected
    assert set(strings["options"]["step"]) == expected


def test_notify_step_auto_discovers_concrete_entities_and_groups_policies() -> None:
    flow = (C / "config_flow.py").read_text()
    outputs = (C / "outputs.py").read_text()
    assert "selected_default = list(known)" in flow
    assert "CONF_NOTIFY_ROOM_OUTPUTS" in flow
    assert "CONF_NOTIFY_INFO_OUTPUTS" in flow
    assert "concrete recognised notification entities only" in outputs
    assert "entity_device_name" in outputs


def test_tts_step_uses_ha_default_languages_and_role_discovery() -> None:
    flow = (C / "config_flow.py").read_text()
    outputs = (C / "outputs.py").read_text()
    assert "tts_default_engine(self.hass)" in flow
    assert "tts_media_player_options(self.hass)" in flow
    assert "snapcast_output_options(self.hass)" in flow
    assert "supported_languages" in outputs
    assert "tts.async_default_engine" in outputs


def test_general_step_has_presence_fallback_door_label_and_timeouts() -> None:
    flow = (C / "config_flow.py").read_text()
    assert "selector.EntitySelector()" in flow
    assert "selector.LabelSelector()" in flow
    assert "CONF_FALLBACK_DOOR_LABEL" in flow
    assert "CONF_OUTPUT_AVAILABILITY_TIMEOUT" in flow


def test_general_direct_tts_players_bypass_room_filter() -> None:
    manager = (C / "manager.py").read_text()
    assert "def _tts_player_scope(" in manager
    assert "NOTIFY_SCOPE_GENERAL" in manager
    assert "area_id is not None" in manager


def test_no_startup_task_regression() -> None:
    manager = (C / "manager.py").read_text()
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(") == 2
