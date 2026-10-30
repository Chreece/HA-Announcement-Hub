"""Regression coverage for the complete native Arabic Announcement Hub UI."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "announcement_hub" / "translations"
)
IDENTICAL = {"0%", "25%", "50%", "75%", "100%"}
TEMPLATES = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")


def _flatten(value, prefix=""):
    if isinstance(value, str):
        return {prefix: value}
    result = {}
    for name, child in value.items():
        path = f"{prefix}.{name}" if prefix else name
        result.update(_flatten(child, path))
    return result


def _read(lang):
    return _flatten(
        json.loads((ROOT / f"{lang}.json").read_text(encoding="utf-8"))
    )


def test_arabic_every_native_key_localized():
    en, ar = _read("en"), _read("ar")
    assert len(en) == 603
    assert set(en) == set(ar)
    unchanged = {key: source for key, source in en.items()
                 if ar[key] == source}
    assert len(unchanged) == 5, unchanged
    assert set(unchanged.values()) == IDENTICAL, unchanged
    for key, source in en.items():
        if "description" in key or ".error." in key:
            assert ar[key] != source, key


def test_arabic_config_and_options_mirror_each_other():
    ar = _read("ar")
    for key, value in ar.items():
        if key.startswith("config.step."):
            option = "options.step." + key[len("config.step."):]
            if option in ar:
                assert ar[option] == value, (key, option)
    assert ar["options.step.init.title"] == "تهيئة Announcement Hub"


def test_arabic_template_and_technical_identifiers_are_unchanged():
    en, ar = _read("en"), _read("ar")
    for key, source in en.items():
        assert sorted(TEMPLATES.findall(ar[key])) == sorted(
            TEMPLATES.findall(source)
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
    for key, names in required.items():
        for name in names:
            assert name in ar[key], (key, name)


def test_arabic_recipient_and_audio_safety_help():
    ar = _read("ar")
    manual = ar["services.send.fields.manual_targets.description"]
    assert "غير مختارة" in manual
    assert "جميع الهواتف" in manual

    person = ar["services.send.fields.target_person.description"]
    assert "دون التحويل" in person
    area = ar["services.send.fields.area.description"]
    assert "المشروطة بفتح الباب" in area
    assert "مستقلة" in area

    snap = ar[
        "config.step.notification_profile.data_description.snapcast_only_source"
    ]
    assert "المجموعات أو المصادر الأخرى في Snapcast" in snap
    door = ar["config.step.queue.data_description.fallback_check_door"]
    assert "مستشعر باب" in door and "مفتوح" in door
