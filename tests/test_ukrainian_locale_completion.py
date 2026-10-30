"""Verify full Ukrainian native Announcement Hub localization and safety text."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "announcement_hub" / "translations"
)
IDENTICAL = {"0%", "25%", "50%", "75%", "100%"}
MARKERS = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")


def _flatten(obj, prefix=""):
    if isinstance(obj, str):
        return {prefix: obj}
    result = {}
    for key, item in obj.items():
        full = f"{prefix}.{key}" if prefix else key
        result.update(_flatten(item, full))
    return result


def _read(lang):
    return _flatten(
        json.loads((ROOT / f"{lang}.json").read_text(encoding="utf-8"))
    )


def test_ukrainian_native_catalog_all_keys_and_translated_help():
    en, uk = _read("en"), _read("uk")
    assert len(en) == 625
    assert set(en) == set(uk)
    unchanged = {key: s for key, s in en.items() if uk[key] == s}
    assert len(unchanged) == 5, unchanged
    assert set(unchanged.values()) == IDENTICAL, unchanged
    for key, source in en.items():
        if "description" in key or ".error." in key:
            assert uk[key] != source, key


def test_ukrainian_options_and_config_forms_have_same_help():
    uk = _read("uk")
    for key, text in uk.items():
        if key.startswith("config.step."):
            corresponding = "options.step." + key[len("config.step."):]
            if corresponding in uk:
                assert uk[corresponding] == text, (key, corresponding)
    assert uk["options.step.init.title"] == "Налаштувати Announcement Hub"


def test_ukrainian_preserves_api_fields_and_template_variables():
    en, uk = _read("en"), _read("uk")
    for key, original in en.items():
        assert sorted(MARKERS.findall(original)) == sorted(
            MARKERS.findall(uk[key])
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
    for key, ids in required.items():
        for name in ids:
            assert name in uk[key], (key, name)


def test_ukrainian_safety_help_preserves_scoped_recipients():
    uk = _read("uk")
    manual = uk["services.send.fields.manual_targets.description"]
    assert "невибрані виходи" in manual
    assert "всім телефонам" in manual
    person = uk["services.send.fields.target_person.description"]
    assert "без переходу" in person
    room = uk["services.send.fields.area.description"]
    assert "резервна кімната" in room
    assert "перевіркою дверей" in room
    assert "окремо" in room
    snap = uk[
        "config.step.notification_profile.data_description.snapcast_only_source"
    ]
    assert "Інші групи та джерела Snapcast" in snap
    assert "без змін" in snap
