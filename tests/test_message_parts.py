
"""Tests for natural visual splitting, read timing, and profiles."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from enum import StrEnum
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = ROOT / "custom_components" / "announcement_hub"

if "homeassistant.const" not in sys.modules:
    homeassistant = ModuleType("homeassistant")
    homeassistant_const = ModuleType("homeassistant.const")

    class Platform(StrEnum):
        SENSOR = "sensor"

    homeassistant_const.Platform = Platform
    homeassistant.const = homeassistant_const
    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.const"] = homeassistant_const

package = ModuleType("announcement_hub")
package.__path__ = [str(MODULE_ROOT)]
sys.modules.setdefault("announcement_hub", package)

for module_name in ("const", "message_parts"):
    spec = importlib.util.spec_from_file_location(
        f"announcement_hub.{module_name}", MODULE_ROOT / f"{module_name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from announcement_hub.message_parts import (  # noqa: E402
    default_notify_profile,
    format_part_title,
    reading_seconds,
    resolve_notify_profile,
    split_message,
)


def test_split_prefers_complete_sentences_then_commas() -> None:
    text = "First complete sentence. Second part, with more words after it."
    parts = split_message(text, 32)
    assert parts == [
        "First complete sentence.",
        "Second part,",
        "with more words after it.",
    ]
    assert " ".join(parts) == text


def test_split_handles_greek_punctuation_and_words() -> None:
    text = "Η πρώτη πρόταση τελείωσε. Η δεύτερη, συνεχίζει κανονικά."
    parts = split_message(text, 30)
    assert parts[0] == "Η πρώτη πρόταση τελείωσε."
    assert all(len(part) <= 30 for part in parts)
    assert " ".join(parts) == text


def test_split_never_cuts_normal_words() -> None:
    text = "alpha beta gamma delta epsilon"
    parts = split_message(text, 12)
    assert parts == ["alpha beta", "gamma delta", "epsilon"]
    assert all(len(part) <= 12 for part in parts)


def test_only_an_overlong_single_word_is_hard_cut() -> None:
    parts = split_message("supercalifragilistic", 5)
    assert parts == ["super", "calif", "ragil", "istic"]


def test_read_time_uses_word_count_buffer_and_clamps() -> None:
    assert reading_seconds(
        "one two three four",
        words_per_minute=120,
        minimum_seconds=1,
        maximum_seconds=30,
        buffer_seconds=1,
    ) == 3.0
    assert reading_seconds(
        "one",
        words_per_minute=600,
        minimum_seconds=4,
        maximum_seconds=30,
        buffer_seconds=0,
    ) == 4.0
    assert reading_seconds(
        "one two three four five six seven eight nine ten",
        words_per_minute=60,
        minimum_seconds=1,
        maximum_seconds=5,
        buffer_seconds=2,
    ) == 5.0


def test_provider_defaults_and_generic_fallback() -> None:
    android_tv = default_notify_profile("nfandroidtv")
    assert android_tv["max_length"] == 193
    assert android_tv["position"] == "bottom-right"
    mobile = default_notify_profile("mobile_app")
    assert mobile["replace_parts"] is True
    resolved = resolve_notify_profile(
        {"default": {"max_length": 77}}, "unknown_provider"
    )
    assert resolved["max_length"] == 77


def test_part_title_numbering() -> None:
    assert format_part_title(
        "Notice", index=2, total=3, show_part_number=True
    ) == "Notice · 2/3"
    assert format_part_title(
        None, index=1, total=2, show_part_number=True
    ) == "1/2"
    assert format_part_title(
        "Notice", index=1, total=1, show_part_number=True
    ) == "Notice"
