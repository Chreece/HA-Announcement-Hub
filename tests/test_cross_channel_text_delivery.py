"""Regression contracts for text fallback across selected output channels."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_notify_candidate_accepts_tts_only_announcements() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    block=manager[
        manager.index('"kind": "notify"'):
        manager.index('if not tts_hard_disabled:')
    ]
    assert '"native_text": bool(text_notify or text_tts)' in block


def test_tts_candidates_accept_notify_only_announcements() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert manager.count('"native_text": bool(text_tts or text_notify)') == 3


def test_selected_visual_channel_uses_notify_then_tts_text() -> None:
    models=(C/"models.py").read_text(encoding="utf-8")
    assert "notify_text = text_notify or text_tts" in models


def test_selected_tts_channel_uses_tts_then_notify_text() -> None:
    models=(C/"models.py").read_text(encoding="utf-8")
    assert "(text_tts or text_notify)" in models


def test_dedicated_text_still_wins_when_both_are_present() -> None:
    models=(C/"models.py").read_text(encoding="utf-8")
    assert "text_tts or text_notify" in models
    assert "text_notify or text_tts" in models
