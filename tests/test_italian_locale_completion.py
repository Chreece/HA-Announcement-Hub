"""Prevent English fallbacks returning to the fully localized Italian UI."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub" / "translations"
# Identical in Italian and English by design; these are not untranslated instructions.
UNCHANGED = {"Area", "Position", "Debug", "Tablet", "0%", "25%", "50%", "75%", "100%"}


def _flatten(value, prefix=""):
    if isinstance(value, str):
        return {prefix: value}
    result = {}
    for key, child in value.items():
        result.update(_flatten(child, f"{prefix}.{key}" if prefix else key))
    return result


def _locale(name):
    return _flatten(json.loads((ROOT / (name + ".json")).read_text(encoding="utf-8")))


def test_italian_has_all_native_strings_without_unreviewed_english_fallback():
    english = _locale("en")
    italian = _locale("it")
    assert len(english) >= 599
    assert set(italian) == set(english)
    identical = {key: source for key, source in english.items() if italian[key] == source}
    assert identical, "The intentional identical-value exceptions unexpectedly disappeared"
    assert set(identical.values()) <= UNCHANGED, identical
    assert len(identical) <= 13, identical


def test_italian_descriptions_and_errors_are_translated():
    english, italian = _locale("en"), _locale("it")
    for path, source in english.items():
        if "description" in path or ".error." in path:
            assert italian[path] != source, path


def test_italian_preserves_template_tokens_and_critical_api_spelling():
    english, italian = _locale("en"), _locale("it")
    tokens = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")
    for key, source in english.items():
        assert sorted(tokens.findall(source)) == sorted(tokens.findall(italian[key])), key

    required = {
        "config.step.queue.data_description.default_use_ai": ("use_ai", "response_variable"),
        "services.send.fields.click_action.description": ("app://", "entityId:entity_id", "clickAction", "notify_data"),
        "services.send.fields.text.description": ("text_tts", "text_notify", "text"),
        "config.step.tts.data_description.tts_voice": ("el_GR",),
        "config.step.edit_advanced_ai.data_description.rewrite": ("{message}", "{language}"),
        "services.send.description": ("notify.announcement_hub",),
        "services.cancel.fields.job_id.description": ("announcement_hub.send",),
    }
    for path, identifiers in required.items():
        for identifier in identifiers:
            assert identifier in italian[path], (path, identifier)
