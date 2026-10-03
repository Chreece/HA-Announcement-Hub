"""Static contract checks for Home Assistant resources."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def test_json_resources_parse() -> None:
    paths = [
        COMPONENT / "manifest.json",
        COMPONENT / "strings.json",
        COMPONENT / "icons.json",
        *sorted((COMPONENT / "translations").glob("*.json")),
        ROOT / "hacs.json",
    ]
    for path in paths:
        assert isinstance(json.loads(path.read_text()), dict), path


def test_service_fields_sections_and_translations_match() -> None:
    services = yaml.safe_load((COMPONENT / "services.yaml").read_text())
    strings = json.loads((COMPONENT / "strings.json").read_text())["services"]
    icons = json.loads((COMPONENT / "icons.json").read_text())["services"]

    assert set(services) == set(strings) == set(icons)
    for service_name, service_schema in services.items():
        translated = strings[service_name]
        assert translated["name"]
        assert translated["description"]
        assert icons[service_name]["service"].startswith("mdi:")

        for field_or_section, schema in service_schema.get("fields", {}).items():
            if "fields" in schema:
                assert field_or_section in translated.get("sections", {})
                for field_name in schema["fields"]:
                    assert field_name in translated.get("fields", {})
            else:
                assert field_or_section in translated.get("fields", {})


def test_config_and_options_steps_match_flow_contract() -> None:
    strings = json.loads((COMPONENT / "strings.json").read_text())
    expected_steps = {"outputs", "tts", "notification_profile", "queue"}
    assert set(strings["config"]["step"]) == expected_steps
    assert set(strings["options"]["step"]) == expected_steps

    all_config_fields = {
        field
        for step in strings["config"]["step"].values()
        for field in step.get("data", {})
    }
    assert "allowed_tts_entities" not in all_config_fields
    assert "default_tts_entities" not in all_config_fields
    assert "allowed_notify_entities" not in all_config_fields
    assert "default_notify_entities" not in all_config_fields
    assert {
        "notify_outputs",
        "notify_room_outputs",
        "notify_info_outputs",
        "notify_warning_outputs",
        "notify_error_outputs",
        "notify_critical_outputs",
        "snapcast_outputs",
        "companion_tts_outputs",
        "tts_engines",
        "tts_room_players",
        "tts_area_players",
        "tts_min_level",
        "output_availability_timeout",
        "occupancy_sensor",
        "occupancy_attribute",
        "fallback_room",
        "fallback_check_door",
        "fallback_door_label",
        "max_length",
        "reading_words_per_minute",
        "position",
    }.issubset(all_config_fields)

    services = yaml.safe_load((COMPONENT / "services.yaml").read_text())
    companion_tts = services["send"]["fields"]["routing"]["fields"][
        "companion_tts"
    ]
    assert companion_tts["default"] is False
    assert "boolean" in companion_tts["selector"]
    occupied_only = services["send"]["fields"]["routing"]["fields"]["occupied_only"]
    assert occupied_only["default"] is True
    assert "boolean" in occupied_only["selector"]


def test_source_contains_output_centric_features() -> None:
    manager = (COMPONENT / "manager.py").read_text()
    config_flow = (COMPONENT / "config_flow.py").read_text()
    init = (COMPONENT / "__init__.py").read_text()
    assert '"message": "TTS"' in manager
    assert '"tts_text": job.tts_text' in manager
    assert "companion_tts: bool" in manager
    assert "tuple(companion_entries) if companion_tts else ()" in manager
    assert "if raw_entry in configured_companion and companion_tts" in manager
    assert "if expanded_companion and companion_tts" in manager
    assert "selected_companion.extend(companion_entries)" in manager
    assert "CONF_TTS_MIN_LEVEL" in manager
    assert "CONF_OUTPUT_AVAILABILITY_TIMEOUT" in manager
    assert "skipped unavailable output(s)" in manager
    assert "last_errors" in manager
    assert "companion_tts_output_options" in config_flow
    outputs = (COMPONENT / "outputs.py").read_text()
    assert "notify_entity_by_entry" in outputs
    assert "entity_area_id(hass, notify_entity)" in outputs
    assert "notify_output_areas" in manager
    assert "notify_output_profiles" in manager
    assert "split_message" in manager
    assert "reading_seconds" in manager
    assert "parallel=True" in manager
    assert "notify_output_legacy_service" in manager
    assert "snapcast_client_areas" in manager
    assert 'f"{TARGET_INTEGRATION_PREFIX}snapcast"' in manager
    assert "unselected client cannot leak" in manager
    assert "companion_tts_entry_areas" in manager
    assert "async_migrate_entry" in init
    assert config_flow.count("self._notify_profile_domains = []") == 2
    diagnostics = (COMPONENT / "diagnostics.py").read_text()
    assert "CONF_NOTIFY_PROFILES" in diagnostics
    installer = (ROOT / "install.sh").read_text()
    assert '"message_parts.py"' in installer


def test_local_brand_assets_exist() -> None:
    for name in ("icon.png", "logo.png"):
        path = COMPONENT / "brand" / name
        assert path.is_file()
        assert path.stat().st_size > 0


def test_manifest_and_hacs_identity() -> None:
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert manifest["domain"] == "announcement_hub"
    assert manifest["config_flow"] is True
    assert manifest["version"] == "0.9.2"
    assert hacs["name"] == manifest["name"]


def test_platform_enum_is_used_for_forwarded_platforms() -> None:
    const_source = (COMPONENT / "const.py").read_text()
    assert "from homeassistant.const import Platform" in const_source
    assert "PLATFORMS: Final = [Platform.SENSOR]" in const_source


def test_translations_cover_all_config_steps_and_service_fields() -> None:
    base = json.loads((COMPONENT / "strings.json").read_text())
    service_fields = set(base["services"]["send"]["fields"])
    for path in sorted((COMPONENT / "translations").glob("*.json")):
        translated = json.loads(path.read_text())
        assert set(translated["config"]["step"]) == set(base["config"]["step"]), path
        assert set(translated["options"]["step"]) == set(base["options"]["step"]), path
        assert service_fields.issubset(
            translated["services"]["send"]["fields"]
        ), path
