"""Final Issue #50 catalog coverage and Korean/Czech localization regressions."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "announcement_hub" / "translations"
)
NATIVE = (
    "el", "de", "fr", "es", "it", "pt", "pt-BR", "nl", "pl", "ru",
    "tr", "uk", "ar", "zh-Hans", "zh-Hant", "ja", "ko", "sv", "cs",
)
EXCEPTIONS = {
    "ko": {"0%", "25%", "50%", "75%", "100%"},
    "cs": {"0%", "25%", "50%", "75%", "100%", "Tablet"},
}
VARIABLES = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")


def flatten(obj, prefix=""):
    if isinstance(obj, str):
        return {prefix: obj}
    result = {}
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        result.update(flatten(value, path))
    return result


def read(lang):
    return flatten(
        json.loads((ROOT / f"{lang}.json").read_text(encoding="utf-8"))
    )


@pytest.mark.parametrize("lang", NATIVE)
def test_all_native_locale_help_strings_are_present_and_localized(lang):
    en, localized = read("en"), read(lang)
    assert len(en) == 639
    assert set(localized) == set(en), lang
    for key, source in en.items():
        assert localized[key], (lang, key)
        assert sorted(VARIABLES.findall(source)) == sorted(
            VARIABLES.findall(localized[key])
        ), (lang, key)
        if "description" in key or ".error." in key:
            assert localized[key] != source, (lang, key)


@pytest.mark.parametrize("lang", ("ko", "cs"))
def test_last_two_native_catalogs_have_no_english_fallback(lang):
    en, localized = read("en"), read(lang)
    equal = {key: source for key, source in en.items()
             if localized[key] == source}
    assert set(equal.values()) == EXCEPTIONS[lang], equal
    assert len(equal) == (5 if lang == "ko" else 6), equal


@pytest.mark.parametrize("lang", ("ko", "cs"))
def test_last_two_catalogs_preserve_config_mirrors_and_api_ids(lang):
    localized = read(lang)
    for key, value in localized.items():
        if key.startswith("config.step."):
            mirror = "options.step." + key[len("config.step."):]
            if mirror in localized:
                assert localized[mirror] == value, (lang, key, mirror)

    assert localized["options.step.init.title"] == {
        "ko": "Announcement Hub 설정",
        "cs": "Nastavit Announcement Hub",
    }[lang]

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
    for path, ids in identifiers.items():
        for identifier in ids:
            assert identifier in localized[path], (lang, path, identifier)


@pytest.mark.parametrize("lang", ("ko", "cs"))
def test_last_two_locale_safety_help_avoids_recipient_broadening(lang):
    data = read(lang)
    manual = data["services.send.fields.manual_targets.description"]
    person = data["services.send.fields.target_person.description"]
    area = data["services.send.fields.area.description"]
    snap = data[
        "config.step.notification_profile.data_description.snapcast_only_source"
    ]
    fragments = {
        "ko": {
            "manual": ("선택하지 않은", "휴대전화"),
            "person": ("다른 방", "대체 전송하지"),
            "area": ("문 상태", "별도로 처리"),
            "snap": ("다른 Snapcast", "변경하지"),
        },
        "cs": {
            "manual": ("nevybrané", "telefonům"),
            "person": ("jiných místností", "bez přesunu"),
            "area": ("stavem dveří", "samostatně"),
            "snap": ("ostatní skupiny", "beze změny"),
        },
    }[lang]
    for text, category in (
        (manual, "manual"), (person, "person"), (area, "area"), (snap, "snap")
    ):
        for part in fragments[category]:
            assert part in text, (lang, category, part)
