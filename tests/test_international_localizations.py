"""Translation coverage and interpolation safety for integration and card."""

from __future__ import annotations

import json
import re
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub"
LANGUAGES = {
    "en", "el", "de", "fr", "es", "it", "pt", "pt-BR", "nl", "pl",
    "ru", "tr", "uk", "ar", "zh-Hans", "zh-Hant", "ja", "ko", "sv", "cs",
}
VARIABLE = re.compile(r"(?<!\\){\\{([a-zA-Z_]+)\\}")


def flatten(value, prefix=""):
    if isinstance(value, str):
        return {prefix: value}
    result = {}
    for key, item in value.items():
        result.update(flatten(item, f"{prefix}.{key}" if prefix else key))
    return result


def test_native_translation_files_have_every_config_option_and_service_key():
    files = COMPONENT / "translations"
    found = {p.stem for p in files.glob("*.json")}
    assert LANGUAGES <= found
    en = flatten(json.loads((files / "en.json").read_text(encoding="utf-8")))
    for lang in LANGUAGES:
        strings = flatten(json.loads((files / (lang + ".json")).read_text(encoding="utf-8")))
        assert set(strings) == set(en), (lang, sorted(set(en) - set(strings)))
        for key, template in en.items():
            assert set(VARIABLE.findall(strings[key])) == set(VARIABLE.findall(template)), (lang, key)
            assert strings[key].strip(), (lang, key)


def test_greek_and_german_integration_text_is_fully_localized():
    folder = COMPONENT / "translations"
    en = flatten(json.loads((folder / "en.json").read_text(encoding="utf-8")))
    for lang in ("el", "de"):
        translations = flatten(json.loads((folder / (lang + ".json")).read_text(encoding="utf-8")))
        # Some public color names, integration identifiers and numeric options
        # are intentionally unchanged between languages.
        translated = sum(value != en[key] for key, value in translations.items())
        assert translated >= 340, (lang, translated)


def test_card_locale_catalog_and_critical_labels():
    locales = json.loads((COMPONENT / "frontend" / "announcement-hub-locales.json").read_text(encoding="utf-8"))
    assert set(locales) == LANGUAGES - {"en"}
    for lang, dictionary in locales.items():
        assert dictionary["Send announcement"] != "Send announcement"
        assert dictionary["Choose recipients"] != "Choose recipients"
        assert dictionary["AI provider"] != "AI provider"
        for source, translated in dictionary.items():
            assert translated.strip(), (lang, source)
            assert set(VARIABLE.findall(source)) == set(VARIABLE.findall(translated)), (lang, source)


def test_greek_card_static_and_dynamic_translations_are_extensive():
    locales = json.loads((COMPONENT / "frontend" / "announcement-hub-locales.json").read_text(encoding="utf-8"))
    for lang in ("el", "de"):
        assert len(locales[lang]) >= 115
    assert locales["el"]["Send announcement"] == "Αποστολή ανακοίνωσης"
    assert locales["el"]["The message"] == "Το μήνυμα"
    assert locales["el"]["AI provider"] == "Πάροχος AI"
    js = (COMPONENT / "frontend" / "announcement-hub-card.js").read_text(encoding="utf-8")
    assert "getLanguage(this._hass)" in js
    assert 'language === "ar" ? "rtl" : "ltr"' in js
    assert "data-hub-original-" in js
    assert "announcement-hub-locales.json" in js
