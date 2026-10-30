"""Ensure native Swedish descriptions and action fields stay translated."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "announcement_hub" / "translations"
)
IDENTICAL = {"Information", "Indigo", "0%", "25%", "50%", "75%", "100%"}
TOKENS = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")


def flatten(data, prefix=""):
    if isinstance(data, str):
        return {prefix: data}
    result = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        result.update(flatten(value, path))
    return result


def read(lang):
    return flatten(json.loads((ROOT / f"{lang}.json").read_text(encoding="utf-8")))


def test_swedish_native_catalog_is_complete():
    en, sv = read("en"), read("sv")
    assert len(en) == 639
    assert set(en) == set(sv)
    same = {key: value for key, value in en.items() if sv[key] == value}
    assert len(same) == 8, same
    assert set(same.values()) == IDENTICAL, same
    for key, value in en.items():
        if "description" in key or ".error." in key:
            assert sv[key] != value, key


def test_swedish_setup_and_options_match():
    sv = read("sv")
    for key, value in sv.items():
        if key.startswith("config.step."):
            option = "options.step." + key[len("config.step."):]
            if option in sv:
                assert sv[option] == value, (key, option)
    assert sv["options.step.init.title"] == "Konfigurera Announcement Hub"


def test_swedish_preserves_placeholders_and_api_names():
    en, sv = read("en"), read("sv")
    for key, value in en.items():
        assert sorted(TOKENS.findall(value)) == sorted(TOKENS.findall(sv[key])), key

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
        "services.cancel.fields.job_id.description": ("announcement_hub.send",),
    }
    for key, vals in identifiers.items():
        for val in vals:
            assert val in sv[key], (key, val)


def test_swedish_safety_help_preserves_recipient_limits():
    sv = read("sv")
    manual = sv["services.send.fields.manual_targets.description"]
    assert "ovald" in manual.lower()
    assert "alla telefoner" in manual

    person = sv["services.send.fields.target_person.description"]
    assert "andra rum" in person and "utan" in person

    fallback = sv["services.send.fields.area.description"]
    assert "reservområdet" in fallback and "separat" in fallback

    shared = sv[
        "config.step.notification_profile.data_description.snapcast_only_source"
    ]
    assert "andra Snapcast-grupper" in shared
    assert "påverkas inte" in shared
