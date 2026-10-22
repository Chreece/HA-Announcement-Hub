"""Prevent regressions in per-person room tracking and destination localizations."""

from __future__ import annotations

import json
import re
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub"
LANGUAGES = [
    "ar", "cs", "de", "el", "es", "fr", "it", "ja", "ko", "nl",
    "pl", "pt", "pt-BR", "ru", "sv", "tr", "uk", "zh-Hans", "zh-Hant",
]
PERSON_FIELDS = (
    ("people", "data_description", (
        "tracked_people", "person_group_language", "person_group_voice",
        "person_group_translate",
    )),
    ("person_profile", "data_description", (
        "tracker", "language", "voice", "ignore_home", "translate",
        "destination_mobile", "destination_watch", "destination_tablet",
        "destination_other",
    )),
)
LABELS = (
    ("people", "data", ("person_group_translate",)),
    ("person_profile", "data", (
        "destination_mobile", "destination_watch", "destination_tablet",
        "destination_other",
    )),
)
CARD_KEYS = (
    "Person destinations",
    "Target named persons, not entity IDs",
    "Assigned in integration setup",
    "Search people...",
    "Search Home Assistant people",
    "Choose people, then select Room, Mobile, Watch or other destinations assigned in their Hub settings.",
    "Room uses location tracking. Mobile, Watch, Tablet and Other target only that person's assigned output devices.",
    "Choose at least one person.",
    "Choose at least one person destination.",
    "{count} selected people",
    "Explicit room outputs only",
    "All eligible HA outputs from this integration",
    "Only selected recipients are eligible in manual mode; missing endpoints cannot cause a broadcast.",
    "Translate into person's language",
    "Person translation",
    "Person setting",
    "Original language",
)


def test_person_setup_and_action_help_translated_for_all_locales():
    en = json.loads((COMPONENT / "translations/en.json").read_text(encoding="utf-8"))
    for lang in LANGUAGES:
        translated = json.loads(
            (COMPONENT / "translations" / f"{lang}.json").read_text(encoding="utf-8")
        )
        for section in ("config", "options"):
            for step, kind, keys in (*PERSON_FIELDS, *LABELS):
                for key in keys:
                    original = en[section]["step"][step][kind][key]
                    actual = translated[section]["step"][step][kind][key]
                    assert actual != original, (lang, section, step, key)
                    assert actual.strip(), (lang, section, step, key)
        for key in ("person_destination", "person_translate"):
            for attr in ("name", "description"):
                assert translated["services"]["send"]["fields"][key][attr] != (
                    en["services"]["send"]["fields"][key][attr]
                ), (lang, key, attr)
        assert translated["config"]["error"]["invalid_person_output"] != (
            en["config"]["error"]["invalid_person_output"]
        ), lang


def test_new_card_person_targets_have_localizations_everywhere():
    data = json.loads(
        (COMPONENT / "frontend/announcement-hub-locales.json")
        .read_text(encoding="utf-8")
    )
    assert set(data) == set(LANGUAGES)
    for lang, entries in data.items():
        for source in CARD_KEYS:
            assert source in entries and entries[source].strip(), (lang, source)
            assert entries[source] != source, (lang, source)
            assert sorted(re.findall(r"\{[a-z]+\}", source)) == sorted(
                re.findall(r"\{[a-z]+\}", entries[source])
            ), (lang, source)


def test_bermuda_and_espresense_examples_documented_without_new_dependency():
    readme = (COMPONENT.parents[1] / "README.md").read_text(encoding="utf-8")
    source = (COMPONENT / "person_targeting.py").read_text(encoding="utf-8")
    assert "Bermuda" in readme and "ESPresense" in readme
    assert '"area_id", "room", "area", "room_name"' in source
    assert 'configured_tracker = str(profile.get("tracker")' in source
