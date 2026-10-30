"""Stop historical English copy from surviving new English source rewrites.

The initial Issue #50 quality gate detected exact matches against en.json,
but older English strings can remain when en.json has evolved. Check both
the old literal wording and the current English source for every locale.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub"
LOCALES = COMPONENT / "translations"
CARD_LOCALES = COMPONENT / "frontend" / "announcement-hub-locales.json"
LANGUAGES = (
    "el", "de", "fr", "es", "it", "pt", "pt-BR", "nl", "pl", "ru",
    "tr", "uk", "ar", "zh-Hans", "zh-Hant", "ja", "ko", "sv", "cs",
)
PERSON_FIELDS = (
    (
        "config.step.reconfigure.menu_option_descriptions.edit_people",
        "options.step.init.menu_option_descriptions.edit_people",
    ),
    ("config.step.people.description", "options.step.people.description"),
    (
        "config.step.person_profile.data.translate",
        "options.step.person_profile.data.translate",
    ),
)
LEGACY_ENGLISH = {
    "Configure tracked people, room sensors, languages and voices.",
    "Configure people's room trackers and individual/group voice settings.",
    "Select people for explicitly targeted room announcements. No automatic broadcasts are enabled.",
    "Select people for person-targeted announcements; they are never automatically added to unrelated broadcasts.",
    "Translate to person's language",
}
CARD_HINT = (
    "Room uses location tracking. Mobile, Watch, Tablet and Other "
    "target only that person's assigned output devices."
)
VARIABLES = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")


def flatten(value, prefix=""):
    if isinstance(value, str):
        return {prefix: value}
    output = {}
    for name, child in value.items():
        path = f"{prefix}.{name}" if prefix else name
        output.update(flatten(child, path))
    return output


def read(lang):
    return flatten(
        json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))
    )


def test_person_legacy_english_not_present_after_source_rewrites():
    en = read("en")
    assert len(en) == 639
    for lang in LANGUAGES:
        translated = read(lang)
        assert set(en) == set(translated), lang
        for group in PERSON_FIELDS:
            first, second = group
            assert translated[first] == translated[second], (lang, group)
            assert translated[first] != en[first], (lang, first)
            assert translated[first] not in LEGACY_ENGLISH, (lang, first)
            assert translated[first].strip(), (lang, first)
        for key, value in translated.items():
            assert value not in LEGACY_ENGLISH, (lang, key)
            assert sorted(VARIABLES.findall(value)) == sorted(
                VARIABLES.findall(en[key])
            ), (lang, key)


def test_greek_and_german_queue_explanations_have_no_untranslated_prose():
    el = read("el")
    for path in (
        "config.step.queue.description",
        "config.step.queue.data_description.fallback_check_door",
        "config.step.queue.data_description.fallback_door_label",
    ):
        assert not any(
            old in el[path] for old in (
                "fallback", "door sensor", "target rooms",
                "queue/timeouts", "door binary sensors",
            )
        ), path
        mirror = "options." + path[len("config."):]
        assert el[path] == el[mirror], path

    de = read("de")
    fallback = "config.step.queue.data_description.fallback_room"
    assert "unavailable/unknown" not in de[fallback]
    assert de[fallback] == de["options." + fallback[len("config."):]]


def test_card_person_destination_help_matches_rendered_chip_labels():
    languages = json.loads(CARD_LOCALES.read_text(encoding="utf-8"))
    assert set(languages) == set(LANGUAGES)
    assert all(len(messages) == 156 for messages in languages.values())
    for lang, messages in languages.items():
        hint = messages[CARD_HINT].casefold()
        for name in ("Room", "Mobile", "Watch", "Tablet", "Other"):
            assert messages[name].casefold() in hint, (lang, name)
        for key, value in messages.items():
            assert sorted(re.findall(r"\{[a-z]+\}", key)) == sorted(
                re.findall(r"\{[a-z]+\}", value)
            ), (lang, key)
