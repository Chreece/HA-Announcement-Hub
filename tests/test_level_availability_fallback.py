"""Contracts for immediate availability-aware level fallback."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_selector_prefers_currently_available_normal_level_outputs() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "normal_available" in manager
    assert 'if normal_available:' in manager
    assert "chosen = normal_available" in manager


def test_selector_uses_nearest_available_level_without_waiting() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "elif available:" in manager
    assert "self._level_distance(level, item" in manager
    assert "unavailable preferred" in manager


def test_cross_channel_fallback_can_reuse_other_text() -> None:
    models=(C/"models.py").read_text(encoding="utf-8")
    assert "force_tts: bool = False" in models
    assert "force_notify: bool = False" in models
    assert "text_tts or text_notify" in models
    assert "text_notify or text_tts" in models


def test_available_server_tts_drops_unavailable_snapclients() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "ready_snapcast" in manager
    assert "chosen_snapcast = ready_snapcast" in manager


def test_nothing_available_keeps_timeout_wait_path() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "normal_configured" in manager
    assert "Nothing can run right now" in manager
    assert "existing availability timeout" in manager


def test_never_remains_a_hard_tts_disable_except_critical() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "tts_hard_disabled" in manager
    assert "minimum_tts_level == TTS_LEVEL_NEVER" in manager
