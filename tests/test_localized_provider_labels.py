"""Dynamic provider names must use the configured HA language safely."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE = (Path(__file__).resolve().parents[1] / "custom_components"
          / "announcement_hub" / "provider_labels.py")
spec = importlib.util.spec_from_file_location("provider_labels_test", MODULE)
assert spec and spec.loader
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)


def hass(language):
    return SimpleNamespace(config=SimpleNamespace(language=language))


@pytest.mark.parametrize(("language", "expected"), [
    ("en", "Original announcement"),
    ("el-GR", "Αρχική ανακοίνωση"),
    ("de-DE", "Originalankündigung"),
    ("fr", "Annonce d'origine"),
    ("pt-BR", "Anúncio original"),
    ("ar", "الإعلان الأصلي"),
    ("zh-TW", "原始公告"),
    ("ja", "元のアナウンス"),
])
def test_localized_ai_backup_options(language, expected):
    actual = provider.provider_label(hass(language), "original")
    assert expected in actual


@pytest.mark.parametrize("language", [
    "el", "de", "en", "fr", "es", "it", "pt", "pt-BR",
    "nl", "pl", "ru", "tr", "uk", "ar",
    "zh-Hans", "zh-Hant", "ja", "ko", "sv", "cs",
])
def test_no_lost_placeholders_in_dynamic_provider_labels(language):
    for key in ("preferred", "task", "agent_unavailable",
                "backup_unavailable"):
        text = provider.provider_label(hass(language), key, name="ai_task.example")
        assert "ai_task.example" in text
        assert "{name}" not in text


def test_unsupported_language_uses_safe_english_fallback():
    assert provider.provider_label(
        hass("xx-XY"), "unavailable"
    ) == "Preferred Assist pipeline: unavailable"
