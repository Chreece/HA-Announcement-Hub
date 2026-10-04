"""Contracts for the continuous TTS producer/consumer pipeline."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "custom_components" / "announcement_hub" / "manager.py"


def _source() -> str:
    return MANAGER.read_text(encoding="utf-8")


def test_prefetch_is_not_disabled_when_file_cache_is_off() -> None:
    source = _source()
    start = source.index("def _schedule_prefetch")
    end = source.index("async def _async_prefetch", start)
    block = source[start:end]
    assert "not job.tts_cache" not in block
    assert "short-lived memory" in block
    assert "self._async_prefetch(job)" in block


def test_prefetch_marks_media_ready_only_after_render_finishes() -> None:
    source = _source()
    start = source.index("async def _async_prefetch")
    end = source.index("def _prefetch_ready_for_job", start)
    block = source[start:end]
    render = block.index("await tts.async_get_media_source_audio")
    ready = block.index("job.media_source_ids[engine] = media_source_id")
    assert render < ready


def test_playback_waits_only_for_preferred_render_not_all_fallbacks() -> None:
    source = _source()
    start = source.index("async def _await_prefetch")
    end = source.index("def _build_media_source_id", start)
    block = source[start:end]
    assert "preferred = next(" in block
    assert "preferred in job.media_source_ids" in block
    assert "await asyncio.wait({task}, timeout=0.02)" in block


def test_visual_and_audio_channels_overlap_instead_of_serializing() -> None:
    source = _source()
    start = source.index("async def _async_process_job")
    end = source.index("@property\n    def _availability_timeout", start)
    block = source[start:end]
    assert "first_task = asyncio.create_task(first(job))" in block
    assert "second_task = asyncio.create_task(second(job))" in block
    assert "await asyncio.gather(*tasks)" in block


def test_final_visual_reading_hold_does_not_block_spoken_pipeline() -> None:
    source = _source()
    assert "hold_after_part = (" in source
    assert "index < len(parts)" in source
    assert "or not job.tts_text" in source


def test_independent_audible_output_classes_start_concurrently() -> None:
    source = _source()
    start = source.index("async def _async_send_tts")
    end = source.index("async def _async_send_room_tts", start)
    block = source[start:end]
    assert "deliveries:" in block
    assert '"room_tts"' in block
    assert '"server_tts"' in block
    assert '"companion_tts"' in block
    assert "asyncio.create_task(run_channel" in block
    assert "await asyncio.gather(*tasks)" in block


def test_multiple_direct_and_companion_outputs_launch_in_parallel() -> None:
    source = _source()
    direct = source[
        source.index("async def _async_send_room_tts"):
        source.index("async def _async_send_server_tts")
    ]
    assert "results = await asyncio.gather(" in direct
    companion = source[
        source.index("async def _async_send_companion_tts"):
        source.index("async def _async_deliver_companion_tts")
    ]
    assert "parallel=True" in companion


def test_queued_audio_skips_intentional_post_play_gap() -> None:
    source = _source()
    assert "if post_delay > 0 and not self._has_pending_audible_job():" in source
    assert "def _has_pending_audible_job(" in source


def test_identical_prepared_snapcast_route_is_handed_off_without_restore_reapply() -> None:
    source = _source()
    assert "def _should_hold_snapcast_route(" in source
    assert "self._prefetch_ready_for_job(pending)" in source
    assert "def _held_snapcast_route_is_applied(" in source
    assert "await self._async_restore_held_snapcast_route()" in source
    assert "self._held_snapcast_snapshot" in source


def test_partial_snapcast_round_is_never_held_warm() -> None:
    source = _source()
    start = source.index("def _should_hold_snapcast_route")
    end = source.index("async def _async_restore_held_snapcast_route", start)
    block = source[start:end]
    assert "if set(target_clients) != set(selected_clients):" in block
    assert "return False" in block
