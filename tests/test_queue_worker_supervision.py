"""Regression contracts for the self-healing serialized queue worker."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "custom_components" / "announcement_hub" / "manager.py"


def test_worker_is_self_healing_and_send_checks_it() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    assert "def _ensure_worker(self)" in source
    assert "self._ensure_worker()" in source
    assert "self._wake.set()" in source
    assert "self.hass.loop.call_soon(self._ensure_worker)" in source
    assert '"worker_alive": bool(' in source


def test_worker_remains_a_config_entry_background_task() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    assert "self.hass.async_create_task(" not in source
    assert source.count("self.entry.async_create_background_task(") == 2
