"""Regression contracts for global server-TTS infrastructure."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def test_tts_engine_first_use_does_not_require_live_state() -> None:
    outputs = (COMPONENT / "outputs.py").read_text(encoding="utf-8")
    start = outputs.index("def tts_engine_available")
    end = outputs.index("def companion_output_available", start)
    block = outputs[start:end]
    assert "er.async_get(hass).async_get(entity_id)" in block
    assert "entry_state" in block
    assert "state is None or state.state != STATE_UNAVAILABLE" in block


def test_server_tts_area_filter_applies_only_to_snapcast_outputs() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    start = manager.index("def _job_has_ready_server_tts")
    end = manager.index("def _job_runnable_now", start)
    block = manager[start:end]
    assert "job.tts_media_player" in block
    assert "tts_engine_available(self.hass, engine)" in block
    assert "job.snapcast_client_areas.get(" in block
    assert "entity_area_id(self.hass, job.tts_media_player)" not in block
    assert "entity_area_id(self.hass, engine)" not in block


def test_global_tts_fix_keeps_background_task_lifecycle() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(") == 2
