"""Full pt and pt-BR localization regression and identifier protection."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub" / "translations"
LOCALES = ("pt", "pt-BR")
IDENTICAL = {"0%", "25%", "50%", "75%", "100%", "Tablet"}


def _flatten(data, prefix=""):
    if isinstance(data, str):
        return {prefix: data}
    items = {}
    for name, value in data.items():
        path = f"{prefix}.{name}" if prefix else name
        items.update(_flatten(value, path))
    return items


def _read(lang):
    return _flatten(json.loads((ROOT / f"{lang}.json").read_text(encoding="utf-8")))


def test_portuguese_native_catalogs_no_english_help():
    en = _read("en")
    assert len(en) >= 599
    for lang in LOCALES:
        dictionary = _read(lang)
        assert set(dictionary) == set(en), lang
        unchanged = {key: value for key, value in dictionary.items()
                     if value == en[key]}
        assert len(unchanged) == 6, (lang, unchanged)
        assert set(unchanged.values()) <= IDENTICAL, (lang, unchanged)
        for key, original in en.items():
            if "description" in key or ".error." in key:
                assert dictionary[key] != original, (lang, key)


def test_portuguese_preserves_templates_and_api_literals():
    en = _read("en")
    marker = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")
    required = {
        "config.step.queue.data_description.default_use_ai":
            ("use_ai", "response_variable"),
        "config.step.queue.data_description.channel_fallback_mode":
            ("text_tts", "text_notify"),
        "config.step.tts.data_description.tts_voice": ("el_GR",),
        "services.send.fields.click_action.description":
            ("app://", "entityId:entity_id", "clickAction", "notify_data"),
        "services.send.fields.text.description": ("text_tts", "text_notify", "text"),
        "config.step.edit_advanced_ai.data_description.rewrite":
            ("{message}", "{language}"),
        "services.send.description": ("notify.announcement_hub",),
    }
    for lang in LOCALES:
        data = _read(lang)
        for key, original in en.items():
            assert sorted(marker.findall(original)) == sorted(
                marker.findall(data[key])
            ), (lang, key)
        for key, ids in required.items():
            for name in ids:
                assert name in data[key], (lang, key, name)


def test_brazilian_room_and_text_help_has_no_portugal_grammar_damage():
    br = _read("pt-BR")
    for key, text in br.items():
        invalid = (
            "das cômodos", "às cômodos", "na cômodo", "uma cômodo",
            "a cômodo", "mesma cômodo", "cômodo ocupada",
            "cômodos selecionadas", "cômodo válida",
            "desativa a cômodo", "a aplicativo", "exibedo",
            "restaurarte", "tirar seu o foco", "recurso a outras cômodos",
        )
        assert not any(word in text for word in invalid), (key, text)

    assert "divisão do texto" in br[
        "config.step.notification_profile.data_description.max_length"
    ]
    assert "cômodo ocupado ou alternativo" in br[
        "config.step.tts.data_description.tts_area_players"
    ]
    assert "encaminhamento alternativo" in br[
        "config.step.queue.data_description.fallback_door_label"
    ]


def test_portugal_and_brazil_native_help_are_locally_distinct():
    pt, br = _read("pt"), _read("pt-BR")
    assert "divisões" in pt["config.step.tts.data_description.snapcast_outputs"]
    assert "cômodos" in br["config.step.tts.data_description.snapcast_outputs"]
    assert "ficheiro" in pt["config.step.edit_audio.data_description.person_chime_url"].lower()
    assert "arquivo" in br["config.step.edit_audio.data_description.person_chime_url"].lower()
