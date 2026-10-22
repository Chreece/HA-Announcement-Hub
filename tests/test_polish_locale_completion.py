"""Verify full Polish native setup, options, and service-action localization."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "announcement_hub" / "translations"
)
SHARED = {"Tablet", "0%", "25%", "50%", "75%", "100%"}
MARKERS = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")


def _flatten(value, prefix=""):
    if isinstance(value, str):
        return {prefix: value}
    result = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        result.update(_flatten(item, path))
    return result


def _read(locale):
    return _flatten(
        json.loads((ROOT / f"{locale}.json").read_text(encoding="utf-8"))
    )


def test_polish_native_catalog_is_complete_and_has_no_english_help():
    en, pl = _read("en"), _read("pl")
    assert len(en) == 599
    assert set(pl) == set(en)
    identical = {key: source for key, source in en.items() if pl[key] == source}
    assert len(identical) == 6, identical
    assert set(identical.values()) <= SHARED, identical
    for path, source in en.items():
        if "description" in path or ".error." in path:
            assert pl[path] != source, path


def test_polish_setup_reconfigure_and_options_are_consistent():
    pl = _read("pl")
    for path, text in pl.items():
        if path.startswith("config.step."):
            options_key = "options.step." + path[len("config.step."):]
            if options_key in pl:
                assert pl[options_key] == text, (path, options_key)
    assert pl["options.step.init.title"] == "Skonfiguruj Announcement Hub"


def test_polish_placeholders_and_api_identifiers_are_preserved():
    en, pl = _read("en"), _read("pl")
    for key, source in en.items():
        assert sorted(MARKERS.findall(pl[key])) == sorted(
            MARKERS.findall(source)
        ), key
    required = {
        "services.send.description": ("notify.announcement_hub",),
        "services.send.fields.click_action.description":
            ("app://", "entityId:entity_id", "clickAction", "notify_data"),
        "services.send.fields.text.description":
            ("text_tts", "text_notify", "text"),
        "services.send.fields.service.description":
            ("notification", "tts", "snapcast", "companion_tts"),
        "config.step.queue.data_description.default_use_ai":
            ("use_ai", "response_variable"),
        "config.step.queue.data_description.channel_fallback_mode":
            ("text_tts", "text_notify"),
        "config.step.tts.data_description.tts_voice": ("el_GR",),
        "config.step.edit_advanced_ai.data_description.rewrite":
            ("{message}", "{language}"),
        "config.step.edit_audio.data_description.person_chime_url":
            ("/local/chime.mp3",),
        "services.cancel.fields.job_id.description":
            ("announcement_hub.send",),
    }
    for key, identifiers in required.items():
        for identifier in identifiers:
            assert identifier in pl[key], (key, identifier)


def test_polish_safety_help_preserves_target_restrictions():
    pl = _read("pl")
    manual = pl["services.send.fields.manual_targets.description"]
    assert "niewybrane wyjścia" in manual
    assert "wszystkie telefony" in manual

    area = pl["services.send.fields.area.description"]
    assert "po sprawdzeniu drzwi" in area
    assert "oddzielnie" in area

    person = pl["services.send.fields.target_person.description"]
    assert "bez przekierowania" in person

    snapcast = pl[
        "config.step.notification_profile.data_description.snapcast_only_source"
    ]
    assert "Inne grupy i źródła Snapcast" in snapcast
    assert "nienaruszone" in snapcast
