"""Snapcast route restoration must be recoverable and fail closed."""

from __future__ import annotations

import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = (Path(__file__).resolve().parents[1] / "custom_components"
          / "announcement_hub" / "manager.py").read_text(encoding="utf-8")
KLASS = next(node for node in ast.parse(SOURCE).body
             if isinstance(node, ast.ClassDef) and node.name == "AnnouncementManager")


def install(cls, name):
    method = next(node for node in KLASS.body
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and node.name == name)
    scope = {"asyncio": asyncio, "HomeAssistantError": RuntimeError,
             "_LOGGER": logging.getLogger(__name__)}
    exec(compile("from __future__ import annotations\n" + ast.unparse(method),
                 f"manager::{name}", "exec"), scope)
    setattr(cls, name, scope[name])


class Harness:
    def __init__(self):
        self._held_snapcast_snapshot = {"media_player.client": False}
        self._held_snapcast_selected = ("media_player.client",)
        self._held_snapcast_targets = ("media_player.client",)
        self._held_snapcast_player = "media_player.mpd"
        self.fail_restore = True
        self.restored = 0

    async def _async_restore_snapcast(self, snapshot):
        self.restored += 1
        assert snapshot == {"media_player.client": False}
        if self.fail_restore:
            raise RuntimeError("Provider unavailable")

    def _job_matches_snapcast_route(self, *args):
        return False


for name in ("_clear_held_snapcast_route", "_async_restore_held_snapcast_route",
             "_async_apply_snapcast_route"):
    install(Harness, name)


def test_failed_held_restore_preserves_snapshot_for_retry():
    async def scenario():
        h = Harness()
        await h._async_restore_held_snapcast_route()
        assert h._held_snapcast_snapshot == {"media_player.client": False}
        h.fail_restore = False
        await h._async_restore_held_snapcast_route()
        assert h._held_snapcast_snapshot is None
        assert h._held_snapcast_selected == ()
        assert h.restored == 2
    asyncio.run(scenario())


def test_new_shared_playback_is_refused_when_previous_route_cannot_restore():
    async def scenario():
        h = Harness()
        job = SimpleNamespace(tts_media_player="media_player.mpd")
        with pytest.raises(RuntimeError, match="Refusing shared playback"):
            await h._async_apply_snapcast_route(
                job, selected_clients=("media_player.client",),
                target_clients=("media_player.client",)
            )
        assert h._held_snapcast_snapshot is not None
    asyncio.run(scenario())


def test_round_failure_retains_restoration_snapshot():
    src = SOURCE[SOURCE.index("    async def _async_play_server_round("):
                 SOURCE.index("    async def _async_available_tts_engines(")]
    last = src[src.rindex('except Exception as err:  # noqa: BLE001'):]
    assert "self._held_snapcast_snapshot = route_snapshot" in last
    assert "self._clear_held_snapcast_route()" not in last
