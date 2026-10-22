"""Protect the fully localized Russian Announcement Hub catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path

TRANSLATIONS = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "announcement_hub" / "translations"
)
UNCHANGED = {"0%", "25%", "50%", "75%", "100%"}
PLACEHOLDERS = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")


def _flat(value, prefix=""):
    if isinstance(value, str):
        return {prefix: value}
    result = {}
    for name, child in value.items():
        path = f"{prefix}.{name}" if prefix else name
        result.update(_flat(child, path))
    return result


def _read(lang):
    return _flat(
        json.loads(
            (TRANSLATIONS / f"{lang}.json").read_text(encoding="utf-8")
        )
    )


def test_russian_native_strings_complete_without_english_help():
    en, ru = _read("en"), _read("ru")
    assert len(en) == 599
    assert set(en) == set(ru)
    identical = {key: source for key, source in en.items() if ru[key] == source}
    assert len(identical) == 5, identical
    assert set(identical.values()) == UNCHANGED, identical
    for key, source in en.items():
        if "description" in key or ".error." in key:
            assert ru[key] != source, key


def test_russian_initial_and_reconfigure_options_match():
    ru = _read("ru")
    for key, value in ru.items():
        if key.startswith("config.step."):
            options = "options.step." + key[len("config.step."):]
            if options in ru:
                assert ru[options] == value, (key, options)
    assert ru["options.step.init.title"] == "Настроить Announcement Hub"


def test_russian_preserves_placeholders_and_service_identifiers():
    en, ru = _read("en"), _read("ru")
    for key, source in en.items():
        assert sorted(PLACEHOLDERS.findall(source)) == sorted(
            PLACEHOLDERS.findall(ru[key])
        ), key
    identifiers = {
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
    for key, names in identifiers.items():
        for name in names:
            assert name in ru[key], (key, name)


def test_russian_safety_help_preserves_explicit_recipients_and_fallback():
    ru = _read("ru")
    manual = ru["services.send.fields.manual_targets.description"]
    assert "невыбранные выходы" in manual
    assert "всем телефонам" in manual

    personal = ru["services.send.fields.target_person.description"]
    assert "без перехода" in personal
    room = ru["services.send.fields.area.description"]
    assert "резервная комната" in room
    assert "проверкой двери" in room
    assert "отдельно" in room

    snapcast = ru[
        "config.step.notification_profile.data_description.snapcast_only_source"
    ]
    assert "остальные группы и источники Snapcast" in snapcast
    assert "не меняются" in snapcast
