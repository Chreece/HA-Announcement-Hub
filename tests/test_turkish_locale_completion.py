"""Regression checks for complete Turkish Announcement Hub localization."""

from __future__ import annotations

import json
import re
from pathlib import Path

TRANSLATIONS = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "announcement_hub" / "translations"
)
SHARED = {"Tablet", "0%", "25%", "50%", "75%", "100%"}
TOKENS = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")


def _flat(data, prefix=""):
    if isinstance(data, str):
        return {prefix: data}
    result = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        result.update(_flat(value, path))
    return result


def _read(lang):
    return _flat(
        json.loads((TRANSLATIONS / f"{lang}.json").read_text(encoding="utf-8"))
    )


def test_turkish_all_native_keys_and_help_are_localized():
    en, tr = _read("en"), _read("tr")
    assert len(en) == 599
    assert set(en) == set(tr)
    equal = {key: value for key, value in en.items() if tr[key] == value}
    assert len(equal) == 6, equal
    assert set(equal.values()) <= SHARED, equal
    for key, value in en.items():
        if "description" in key or ".error." in key:
            assert tr[key] != value, key


def test_turkish_config_option_mirrors_match():
    tr = _read("tr")
    for key, text in tr.items():
        if key.startswith("config.step."):
            other = "options.step." + key[len("config.step."):]
            if other in tr:
                assert tr[other] == text, (key, other)
    assert tr["options.step.init.title"] == "Announcement Hub'ı yapılandır"


def test_turkish_preserves_interpolation_and_action_identifiers():
    en, tr = _read("en"), _read("tr")
    for key, value in en.items():
        assert sorted(TOKENS.findall(tr[key])) == sorted(
            TOKENS.findall(value)
        ), key
    ids = {
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
    for key, values in ids.items():
        for name in values:
            assert name in tr[key], (key, name)


def test_turkish_targeting_and_snapcast_safety_help_is_scoped():
    tr = _read("tr")
    manual = tr["services.send.fields.manual_targets.description"]
    assert "Seçilmemiş çıkışları" in manual
    assert "tüm telefonları" in manual

    person = tr["services.send.fields.target_person.description"]
    assert "başka odalara" in person
    area = tr["services.send.fields.area.description"]
    assert "kapı kontrolüne" in area
    assert "bağımsız" in area

    shared = tr[
        "config.step.notification_profile.data_description.snapcast_only_source"
    ]
    assert "diğer Snapcast grupları" in shared
    assert "dokunmaz" in shared
