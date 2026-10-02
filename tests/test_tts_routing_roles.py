"""Contracts for the three distinct server/direct TTS routing roles."""

from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_setup_distinguishes_direct_shared_and_routing_players() -> None:
    strings=json.loads((C/"strings.json").read_text())
    for section in ("config","options"):
        outputs=strings[section]["step"]["outputs"]["data"]
        tts=strings[section]["step"]["tts"]["data"]
        assert "snapcast_outputs" not in outputs
        assert "tts_room_players" in tts
        assert "tts_media_player" in tts
        assert "snapcast_outputs" in tts


def test_direct_room_players_are_area_bound_but_shared_player_is_global() -> None:
    manager=(C/"manager.py").read_text()
    assert "room_tts_player_areas" in manager
    assert "def _job_has_ready_room_tts(" in manager
    assert "entity_area_id(self.hass, job.tts_media_player)" not in manager[
        manager.index("def _job_has_ready_server_tts"):
        manager.index("def _job_runnable_now")
    ]
    assert "server_tts_enabled = bool(routed_selected[3])" in manager


def test_snapcast_clients_remain_routing_only() -> None:
    manager=(C/"manager.py").read_text()
    server=manager[
        manager.index("async def _async_send_server_tts"):
        manager.index("async def _async_play_server_round")
    ]
    assert "_snapcast_output_available" in server
    assert "_async_play_server_round" in server
    direct=manager[
        manager.index("async def _async_send_room_tts"):
        manager.index("async def _async_send_server_tts")
    ]
    assert "_async_play_media_source" in direct
    assert "job.room_tts_players" in direct


def test_new_role_model_keeps_startup_safe_tasks() -> None:
    manager=(C/"manager.py").read_text()
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(")==2
