"""Regression contracts for silent handling of unavailable outputs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def test_unavailable_outputs_do_not_create_channel_errors() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "then silently skip unavailable ones" in manager
    assert "skipped unavailable output(s)" in manager
    assert "self._record_channel_failure(job, channel_name, error)" not in manager
    assert "Delivery did not succeed within" not in manager


def test_all_unavailable_outputs_are_a_valid_no_op() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "if not job.successful_channels and job.channel_errors:" in manager
    server = manager[
        manager.index("async def _async_send_server_tts"):
        manager.index("async def _async_play_server_round")
    ]
    assert "if not await self._async_wait_player_available(player, job):" in server
    assert "return" in server
    assert "skipped unavailable Snapcast output(s)" in manager


def test_silent_skip_change_does_not_regress_task_lifecycle() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(") == 2
