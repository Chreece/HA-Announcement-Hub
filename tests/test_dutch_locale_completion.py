"""Regression checks for the complete Dutch native Announcement Hub catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path

TRANSLATIONS = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "announcement_hub" / "translations"
)
UNCHANGED = {"Debug", "Indigo", "Tablet", "0%", "25%", "50%", "75%", "100%"}
MARKERS = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")


def _flatten(data, prefix=""):
    if isinstance(data, str):
        return {prefix: data}
    result = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        result.update(_flatten(value, path))
    return result


def _read(lang):
    return _flatten(
        json.loads((TRANSLATIONS / f"{lang}.json").read_text(encoding="utf-8"))
    )


def test_dutch_native_catalog_has_no_unreviewed_english_fallback():
    english, dutch = _read("en"), _read("nl")
    assert len(english) == 599
    assert set(dutch) == set(english)
    identical = {key: source for key, source in english.items()
                 if dutch[key] == source}
    assert len(identical) == 10, identical
    assert set(identical.values()) <= UNCHANGED, identical
    for key, text in english.items():
        if "description" in key or ".error." in key:
            assert dutch[key] != text, key


def test_dutch_config_and_options_help_stay_in_sync():
    dutch = _read("nl")
    for path, value in dutch.items():
        if path.startswith("config.step."):
            option = "options.step." + path[len("config.step."):]
            if option in dutch:
                assert dutch[option] == value, (path, option)
    assert dutch["options.step.init.title"] == "Announcement Hub configureren"


def test_dutch_preserves_interpolation_and_technical_ids():
    english, dutch = _read("en"), _read("nl")
    for path, source in english.items():
        assert sorted(MARKERS.findall(source)) == sorted(
            MARKERS.findall(dutch[path])
        ), path

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
        "config.step.edit_advanced_ai.data_description.rewrite":
            ("{message}", "{language}"),
        "config.step.tts.data_description.tts_voice": ("el_GR",),
        "config.step.edit_audio.data_description.person_chime_url":
            ("/local/chime.mp3",),
        "services.cancel.fields.job_id.description":
            ("announcement_hub.send",),
    }
    for path, tokens in required.items():
        for token in tokens:
            assert token in dutch[path], (path, token)


def test_dutch_safety_explanations_keep_recipients_scoped():
    dutch = _read("nl")
    recipients = dutch["services.send.fields.manual_targets.description"]
    assert "nooit" in recipients.lower()
    assert "niet-geselecteerde" in recipients
    assert "telefoons" in recipients

    room = dutch["services.send.fields.area.description"]
    assert "uitwijkruimte" in room
    assert "afzonderlijk" in room

    snapcast = dutch[
        "config.step.notification_profile.data_description.snapcast_only_source"
    ]
    assert "andere Snapcast-groepen" in snapcast
    assert "ongemoeid" in snapcast

    people = dutch["services.send.fields.target_person.description"]
    assert "zonder uitwijk" in people
