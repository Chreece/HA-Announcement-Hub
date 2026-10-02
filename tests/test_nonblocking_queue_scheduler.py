"""Contracts for non-blocking pending queue scheduling."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "custom_components" / "announcement_hub" / "manager.py"


def test_worker_scans_for_runnable_jobs_instead_of_popping_fifo_head() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    worker = source[source.index("async def _async_worker"):source.index("async def _async_process_job")]
    assert "job = self._next_runnable_job()" in worker
    assert "self._queue.popleft()" not in worker
    assert "self._queue.remove(job)" in worker


def test_waiting_jobs_expire_without_blocking_newer_ready_jobs() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    assert "def _next_runnable_job(" in source
    assert "if self._job_runnable_now(job):" in source
    assert "self._pending_age_seconds(job) >= timeout" in source
    assert "def _expire_waiting_job(" in source


def test_scheduler_readiness_covers_visual_server_and_companion_outputs() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    assert "def _job_has_ready_visual_output(" in source
    assert "def _job_has_ready_server_tts(" in source
    assert "def _job_has_ready_companion_tts(" in source
    assert "notify_output_available(self.hass, output)" in source
    assert "self._snapcast_output_available(entity_id)" in source
    assert "companion_output_available(self.hass, output)" in source


def test_scheduler_keeps_startup_safe_background_task_lifecycle() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    assert "self.hass.async_create_task(" not in source
    assert source.count("self.entry.async_create_background_task(") == 2
