"""Safe person preferences, presence, prompt and audio isolation regressions."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub"


def load(filename):
    spec = importlib.util.spec_from_file_location(filename, COMPONENT / (filename + ".py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


people = load("person_delivery")
ai = load("ai_filter")


def test_literal_greetings_never_evaluate_arbitrary_ha_templates():
    assert people.personalized_text(
        "Dinner is ready", "Alex", prepend=True
    ) == "Alex, Dinner is ready"
    assert people.personalized_text(
        "{{ name }}, dinner is ready", "Alex", prepend=True
    ) == "Alex, dinner is ready"
    assert people.personalized_text(
        "{{ states('sensor.secret') }} at 23°C", "Alex", prepend=True
    ) == "Alex, {{ states('sensor.secret') }} at 23°C"
    assert people.personalized_text(None, "Alex", prepend=True) is None


def test_group_provider_rewrite_and_translation_precedence():
    assert people.allowed_person_ai(
        requested_enabled=False, configured_rewrite=True, should_translate=True
    ) == (False, "rewrite")
    assert people.allowed_person_ai(
        requested_enabled=None, configured_rewrite=False, should_translate=True
    ) == (True, "translate")
    assert people.allowed_person_ai(
        requested_enabled=None, configured_rewrite=True, should_translate=True
    ) == (True, "rewrite")
    assert people.allowed_person_ai(
        requested_enabled=None, configured_rewrite=False, should_translate=False
    ) == (None, "rewrite")


def test_presence_is_positive_only_and_person_disabled_is_never_eligible():
    states = {
        "binary_sensor.kitchen": SimpleNamespace(state="on"),
        "binary_sensor.unknown": SimpleNamespace(state="unavailable"),
        "binary_sensor.off": SimpleNamespace(state="off"),
    }
    hass_states = SimpleNamespace(get=states.get)
    assert people.presence_confirmed(hass_states, "binary_sensor.kitchen")
    for entity_id in ("binary_sensor.unknown", "binary_sensor.off", "binary_sensor.missing", None):
        assert not people.presence_confirmed(hass_states, entity_id)
    assert people.person_is_enabled({"enabled": True})
    assert not people.person_is_enabled({"enabled": False})


def test_custom_prompts_only_allow_literal_message_and_language_parameters():
    source = {"text_tts": "Room 23°C", "text_notify": None}
    assert "Room 23°C" in ai.custom_style_instruction(
        {"translate": "Please use {language}: {message}"},
        mode="translate", target_language="Greek", originals=source,
    )
    assert ai.custom_style_instruction(
        {}, mode="rewrite", target_language=None, originals=source
    ) == ""
    for invalid in (
        "{states('sensor.secret')}", "{message.__class__}",
        "x" * 1300, "{{ language }}",
    ):
        with pytest.raises(ValueError):
            ai.custom_style_instruction(
                {"rewrite": invalid}, mode="rewrite",
                target_language=None, originals=source,
            )


def test_switches_and_recovery_are_scoped_to_exact_person_or_area():
    switch = (COMPONENT / "switch.py").read_text()
    manager = (COMPONENT / "manager.py").read_text()
    services = (COMPONENT / "services.yaml").read_text()
    assert 'if self.kind == "person":' in switch
    assert '"person_area_enabled"' in switch
    assert '"person_profiles"' in switch
    assert "options=options" in switch
    assert '"presence_sensors"' in (COMPONENT / "models.py").read_text()
    assert 'presence_confirmed(self.hass.states, sensor)' in manager
    assert '_async_optional_direct_chime(job, player)' in manager
    assert 'if player == job.tts_media_player:' in manager
    assert '"/local/"' in manager
    assert 'self._volume_restore[player]' in manager
    assert '"volume_restore": dict(getattr(self, "_volume_restore", {}))' in manager
    assert "finally:" in manager
    assert "await asyncio.shield(self._async_restore_volume(player))" in manager
    assert "pre_announce_sound:" in services


def test_new_config_steps_have_locale_and_error_keys():
    en = json.loads((COMPONENT / "translations/en.json").read_text())
    for section in ("config", "options"):
        for step in ("edit_audio", "edit_advanced_ai", "edit_room_safety"):
            assert step in en[section]["step"]
        for error in (
            "invalid_person_area", "invalid_person_presence",
            "invalid_chime_url", "invalid_prompt_template",
        ):
            assert error in en[section]["error"]
