"""Guard translated safety semantics and prevent English fallback regressions.

Translations are human-review candidates: key completeness alone is not
proof that the meaning is correct. Issue #50 tracks remaining older help.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub"
LOCALES = (
    "el", "de", "fr", "es", "it", "pt", "pt-BR", "nl", "pl", "ru",
    "tr", "uk", "ar", "zh-Hans", "zh-Hant", "ja", "ko", "sv", "cs",
)
CONFIG_HELP = (
    "queue.data_description.occupancy_sensor",
    "queue.data_description.fallback_room",
    "queue.data_description.fallback_check_door",
    "queue.data_description.default_use_ai",
    "queue.data_description.channel_fallback_mode",
    "tts.data_description.snapcast_outputs",
    "tts.data_description.tts_media_player",
    "tts.data_description.tts_min_level",
    "outputs.data_description.notify_room_outputs",
    "notification_profile.data_description.snapcast_only_source",
)
ACTION_HELP = (
    "level", "service", "area", "integration", "device", "entity",
    "manual_targets", "occupied_only", "text_tts", "text_notify",
    "use_ai", "ai_mode",
)
STALE_ENGLISH = (
    "Choose this person's current-room tracker",
    "Configure a sensor reporting the person's current room",
    "Configure a room sensor and optional voice",
    "Send to the selected people's current rooms only",
    "Announce in each selected person's current room only",
    "Target only the selected person's current room",
    "Discover only explicitly selected Home Assistant recipients",
)


def _load(lang: str) -> dict:
    return json.loads(
        (ROOT / "translations" / f"{lang}.json").read_text(encoding="utf-8")
    )


def _flatten(value: dict, prefix: str = "") -> dict[str, str]:
    output: dict[str, str] = {}
    for name, child in value.items():
        key = f"{prefix}.{name}" if prefix else name
        if isinstance(child, str):
            output[key] = child
        elif isinstance(child, dict):
            output.update(_flatten(child, key))
    return output


def test_native_catalogs_keep_all_599_keys_and_safety_help_translated():
    english = _load("en")
    baseline = _flatten(english)
    assert len(baseline) >= 599
    for lang in LOCALES:
        document = _load(lang)
        translated = _flatten(document)
        assert set(translated) == set(baseline), lang
        for short_path in CONFIG_HELP:
            config = "config.step." + short_path
            options = "options.step." + short_path
            assert translated[config] != baseline[config], (lang, config)
            assert translated[options] == translated[config], (lang, options)
        for field in ACTION_HELP:
            key = f"services.send.fields.{field}.description"
            assert translated[key] != baseline[key], (lang, key)


def test_old_english_person_tracking_help_does_not_survive():
    for lang in LOCALES:
        data = _flatten(_load(lang))
        for key in (
            "config.step.person_profile.description",
            "options.step.person_profile.description",
            "services.send.fields.target_person.description",
            "services.send.fields.manual_targets.description",
        ):
            phrase = data[key]
            assert phrase.strip(), (lang, key)
            assert not any(phrase.startswith(old) for old in STALE_ENGLISH), (
                lang, key, phrase,
            )
    greek = _flatten(_load("el"))
    fallback = greek["config.step.queue.data_description.fallback_room"]
    assert "fixed room candidates" not in fallback
    assert "target rooms" not in fallback


def test_french_and_spanish_native_descriptions_have_no_english_copies():
    english = _flatten(_load("en"))
    for lang in ("fr", "es"):
        translated = _flatten(_load(lang))
        for key, original in english.items():
            if "description" in key:
                assert translated[key] != original, (lang, key)
        # Percentages and international colour/error terms may be identical.
        assert sum(value == english[key] for key, value in translated.items()) <= 10


def test_identifier_literals_survive_critical_translations():
    for lang in LOCALES:
        data = _flatten(_load(lang))
        assert "text_tts" in data[
            "config.step.queue.data_description.channel_fallback_mode"
        ], lang
        assert "text_notify" in data[
            "config.step.queue.data_description.channel_fallback_mode"
        ], lang
        for source_key in ("area", "integration", "device", "entity"):
            value = data[f"services.send.fields.{source_key}.description"]
            assert value.strip(), (lang, source_key)
        assert "use_ai" in data[
            "config.step.queue.data_description.default_use_ai"
        ], lang
