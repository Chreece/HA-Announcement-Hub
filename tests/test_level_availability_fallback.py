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


def test_server_tts_keeps_unavailable_snapclients_for_timeout_wait() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "chosen_snapcast = tuple(routed_selected[3])" in manager
    assert "chosen_snapcast = ready_snapcast" not in manager
    server=manager[
        manager.index("async def _async_send_server_tts"):
        manager.index("async def _async_play_server_round")
    ]
    assert "pending = [" in server
    assert "while pending and loop.time() < deadline:" in server


def test_nothing_available_keeps_timeout_wait_path() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "normal_configured" in manager
    assert "Nothing can run right now" in manager
    assert "existing availability timeout" in manager


def test_never_remains_a_hard_tts_disable_except_critical() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "tts_hard_disabled" in manager
    assert "minimum_tts_level == TTS_LEVEL_NEVER" in manager


def test_requested_tts_is_selected_independently_from_visual_notifications() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("# Resolve the audible channel independently")
    end=manager.index("# TTS has a stronger availability contract", start)
    block=manager[start:end]
    assert "tts_requested = bool(text_tts or level == LEVEL_CRITICAL)" in block
    assert "tts_candidates = [" in block
    assert "tts_normal_available" in block
    assert "elif tts_available:" in block
    assert "tts_normal_configured" in block
    assert "chosen.extend(" in block
    assert "force_tts = force_tts or tts_relaxed" in block
    assert "text_notify" not in block


def test_tts_fallback_is_not_blocked_only_because_level_was_relaxed() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("tts_must_output = bool(", manager.index(") = routed_plan("))
    end=manager.index("if (", start)
    block=manager[start:end]
    assert "minimum_tts_level != TTS_LEVEL_NEVER" in block
    assert "tts_allowed_for_level" not in block
