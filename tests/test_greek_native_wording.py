"""Protect reviewed Greek setup/help wording against copied English jargon.

This supplements exact-source string parity: older partially translated Greek
sentences remained even after all 19 locales had complete non-English catalogs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

TRANSLATIONS = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "announcement_hub" / "translations"
)
PLACEHOLDERS = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")
# Technical API identifiers, product names and legitimate placeholders are
# deliberately excluded. Only previously observed English prose is rejected.
ENGLISH_JARGON = re.compile(
    r"fallback|laptops|provider(?:-specific)?|players?|media\s+player|"
    r"room-scoped|routing|audio\s+focus|queue|split|tag|overlay|"
    r"interactive|mute|source|stream|clients?|payload|keys|"
    r"legacy\s+alias|voice\s+ID|locale|play\s+request|"
    r"cache(?:-άρει)?",
    re.IGNORECASE,
)


def _flatten(value, prefix=""):
    if isinstance(value, str):
        return {prefix: value}
    result = {}
    for name, child in value.items():
        path = f"{prefix}.{name}" if prefix else name
        result.update(_flatten(child, path))
    return result


def _read(lang):
    raw = json.loads((TRANSLATIONS / f"{lang}.json").read_text("utf-8"))
    return raw, _flatten(raw)


def test_greek_native_599_keys_and_placeholders_remain_identical():
    _, english = _read("en")
    _, greek = _read("el")
    assert len(english) == 625
    assert set(greek) == set(english)
    for key, source in english.items():
        assert greek[key].strip(), key
        assert sorted(PLACEHOLDERS.findall(greek[key])) == sorted(
            PLACEHOLDERS.findall(source)
        ), key


def test_greek_help_contains_no_previous_english_prose():
    _, greek = _read("el")
    for key, value in greek.items():
        cleaned = re.sub(r"\{[a-z_]+\}", "", value)
        assert not ENGLISH_JARGON.search(cleaned), (key, value)


def test_greek_setup_and_options_stay_consistent_including_errors():
    raw, values = _read("el")
    for key, text in values.items():
        if key.startswith("config.step."):
            mirror = "options.step." + key[len("config.step."):]
            if mirror in values:
                assert text == values[mirror], (key, mirror)
    assert set(raw["config"]["error"]) == set(raw["options"]["error"])
    for key, text in raw["config"]["error"].items():
        assert text == raw["options"]["error"][key], key


def test_greek_provider_identifiers_and_recipient_safety_remain_intact():
    _, greek = _read("el")
    api_identifiers = {
        "services.send.description": ("notify.announcement_hub",),
        "services.send.fields.click_action.description":
            ("app://", "entityId:entity_id", "clickAction", "notify_data"),
        "config.step.notification_profile.data_description.integration_data":
            ("notify_data",),
        "config.step.tts.data_description.tts_voice": ("el_GR",),
        "config.step.edit_advanced_ai.data_description.rewrite":
            ("{message}", "{language}"),
    }
    for key, identifiers in api_identifiers.items():
        for identifier in identifiers:
            assert identifier in greek[key], (key, identifier)

    shared = greek[
        "config.step.notification_profile.data_description.snapcast_only_source"
    ]
    assert "μόνο των πελατών" in shared
    assert "άλλες ομάδες και πηγές Snapcast" in shared

    scoped = greek["services.send.fields.manual_targets.description"]
    assert "παραλήπτες" in scoped
    assert "ρητά" in scoped
