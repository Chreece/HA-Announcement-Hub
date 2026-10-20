"""Channel fallback preference and independent-channel delivery contracts.

Pure routing policy is exercised directly; the real manager dispatch function
is extracted to test correct sequencing without touching Home Assistant.
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "custom_components" / "announcement_hub"
ROUTING = C / "routing_fallback.py"
MANAGER = (C / "manager.py").read_text(encoding="utf-8")
spec = importlib.util.spec_from_file_location(
    "announcement_hub_fallback_channel_tests", ROUTING
)
assert spec and spec.loader
routing = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = routing
spec.loader.exec_module(routing)


def candidates(*, visual=True, speech=True):
    return routing.StageTargets(
        notify=("entity:notify.kitchen",) if visual else (),
        snapcast=("media_player.kitchen_snapcast",) if speech else (),
    )


@pytest.mark.parametrize("mode,visual_ready,audio_ready,visual,speech", [
    ("visual_then_tts", True, True, True, False),
    ("visual_then_tts", False, True, False, True),
    ("visual_then_tts", True, False, True, False),
    ("tts_then_visual", True, True, False, True),
    ("tts_then_visual", True, False, True, False),
    ("tts_then_visual", False, True, False, True),
    ("both", True, True, True, True),
])
def test_primary_channel_and_ready_fallback(
    mode, visual_ready, audio_ready, visual, speech
):
    result = routing.prioritize_stage_targets(
        stage="primary", candidates=candidates(),
        normal_speech_allowed=True,
        visual_ready=visual_ready, audio_ready=audio_ready,
        mode=mode,
    )
    assert bool(result.notify) is visual
    assert result.has_audio is speech


@pytest.mark.parametrize("mode", ["visual_then_tts", "tts_then_visual", "both"])
@pytest.mark.parametrize("has_visual,has_audio", [(True, False), (False, True)])
def test_single_eligible_channel_is_never_suppressed(
    mode, has_visual, has_audio
):
    selected = candidates(visual=has_visual, speech=has_audio)
    result = routing.prioritize_stage_targets(
        stage="primary", candidates=selected,
        normal_speech_allowed=False,
        visual_ready=has_visual, audio_ready=has_audio, mode=mode,
    )
    assert result == selected


@pytest.mark.parametrize("mode", ["visual_then_tts", "tts_then_visual"])
def test_both_unavailable_are_kept_for_availability_grace(mode):
    c = candidates()
    result = routing.prioritize_stage_targets(
        stage="primary", candidates=c, mode=mode,
        normal_speech_allowed=False,
        visual_ready=False, audio_ready=False,
    )
    assert result == c


@pytest.mark.parametrize("stage", ["primary", "occupied", "fallback", "general"])
def test_failure_retry_never_expands_other_rooms_or_generals(stage):
    c = candidates()
    for destination in ("visual", "tts"):
        result = routing.prioritize_stage_targets(
            stage=stage, candidates=c, mode="visual_then_tts",
            normal_speech_allowed=True, visual_ready=True,
            audio_ready=True, retry_channel=destination,
        )
        assert set(result.notify).issubset(c.notify)
        assert set(result.snapcast).issubset(c.snapcast)
        assert (bool(result.notify), result.has_audio) == (
            (True, False) if destination == "visual" else (False, True)
        )


def test_simultaneous_default_retains_legacy_low_severity_room_rules():
    c = candidates()
    primary = routing.prioritize_stage_targets(
        stage="primary", candidates=c,
        normal_speech_allowed=False,
        visual_ready=True, audio_ready=True, mode="both",
    )
    occupied = routing.prioritize_stage_targets(
        stage="occupied", candidates=c,
        normal_speech_allowed=False,
        visual_ready=True, audio_ready=True, mode="both",
    )
    assert primary.notify and not primary.has_audio
    assert occupied.has_audio and not occupied.notify


def test_config_choice_is_present_in_initial_setup_and_reconfigure():
    flow = (C / "config_flow.py").read_text(encoding="utf-8")
    const = (C / "const.py").read_text(encoding="utf-8")
    assert 'CONF_CHANNEL_FALLBACK_MODE: Final = "channel_fallback_mode"' in const
    assert 'DEFAULT_CHANNEL_FALLBACK_MODE: Final = CHANNEL_BOTH' in const
    assert "options=list(CHANNEL_FALLBACK_MODES)" in flow
    assert 'translation_key="channel_fallback_mode"' in flow
    assert "(CONF_CHANNEL_FALLBACK_MODE, DEFAULT_CHANNEL_FALLBACK_MODE)" in flow
    queue = flow[flow.index("    async def async_step_queue("):]
    assert "probatio.Required(\n                    CONF_CHANNEL_FALLBACK_MODE" in queue
    assert "options=list(DISPATCH_ORDERS)" not in queue
    for file in (
        "strings.json", "translations/en.json", "translations/de.json",
        "translations/el.json",
    ):
        local = json.loads((C / file).read_text(encoding="utf-8"))
        assert set(local["selector"]["channel_fallback_mode"]["options"]) == {
            "visual_then_tts", "tts_then_visual", "both"
        }
        for section in ("config", "options"):
            step = local[section]["step"]["queue"]
            assert "channel_fallback_mode" in step["data"]
            description = step["data_description"]["channel_fallback_mode"]
            assert "text_tts" in description and "text_notify" in description


_TREE = ast.parse(MANAGER)
_CLASS = next(node for node in _TREE.body
              if isinstance(node, ast.ClassDef)
              and node.name == "AnnouncementManager")
_METHOD = next(node for node in _CLASS.body
               if isinstance(node, ast.AsyncFunctionDef)
               and node.name == "_async_process_job")
_SCOPE = {
    "asyncio": asyncio,
    "CONF_CHANNEL_FALLBACK_MODE": "channel_fallback_mode",
    "DEFAULT_CHANNEL_FALLBACK_MODE": "both",
    "CHANNEL_VISUAL_THEN_TTS": "visual_then_tts",
    "CHANNEL_TTS_THEN_VISUAL": "tts_then_visual",
    "CONF_DISPATCH_ORDER": "dispatch_order",
    "DEFAULT_DISPATCH_ORDER": "notify_then_tts",
    "DISPATCH_NOTIFY_THEN_TTS": "notify_then_tts",
    "HomeAssistantError": RuntimeError,
}
exec(
    compile(
        "from __future__ import annotations\n" + ast.unparse(_METHOD),
        "AnnouncementManager._async_process_job", "exec",
    ),
    _SCOPE,
)
_async_process_job = _SCOPE["_async_process_job"]


class DeliveryHarness:
    def __init__(self, mode: str, fails=()):
        self.settings = {"channel_fallback_mode": mode}
        self.fails = set(fails)
        self.calls = []

    async def _async_send_notifications(self, job):
        if not job.notify_text or not job.notify_outputs:
            return
        self.calls.append("visual")
        await asyncio.sleep(0)
        if "visual" in self.fails:
            job.channel_errors["visual"] = "provider failed"
            raise RuntimeError("visual failed")
        job.successful_channels.append("notify.tv")

    async def _async_send_tts(self, job):
        if not job.tts_text or not (
            job.room_tts_players or job.server_tts_enabled
            or job.companion_tts_entries
        ):
            return
        self.calls.append("tts")
        await asyncio.sleep(0)
        if "tts" in self.fails:
            job.channel_errors["tts"] = "provider failed"
            raise RuntimeError("tts failed")
        job.successful_channels.append("speaker")

    @staticmethod
    def _raise_if_cancelled(job):
        return None


def job(*, visual=True, tts=True):
    return SimpleNamespace(
        notify_text="Notice" if visual else None,
        tts_text="Spoken" if tts else None,
        notify_outputs=("entity:notify.tv",) if visual else (),
        room_tts_players=("media_player.kitchen",) if tts else (),
        server_tts_enabled=False, companion_tts_entries=(),
        successful_channels=[], channel_errors={}
    )


@pytest.mark.parametrize("mode,expected", [
    ("visual_then_tts", ["visual"]),
    ("tts_then_visual", ["tts"]),
    ("both", ["visual", "tts"]),
])
def test_normal_delivery_sends_only_needed_channels(mode, expected):
    worker = DeliveryHarness(mode)
    j = job()
    asyncio.run(_async_process_job(worker, j))
    assert worker.calls == expected


@pytest.mark.parametrize("mode,fail,expected", [
    ("visual_then_tts", "visual", ["visual", "tts"]),
    ("tts_then_visual", "tts", ["tts", "visual"]),
])
def test_normal_delivery_tries_opposite_only_after_failure(mode, fail, expected):
    worker = DeliveryHarness(mode, fails=[fail])
    j = job()
    asyncio.run(_async_process_job(worker, j))
    assert worker.calls == expected
    assert j.successful_channels


@pytest.mark.parametrize("mode", ["visual_then_tts", "tts_then_visual", "both"])
@pytest.mark.parametrize("visual,tts", [(False, True), (True, False)])
def test_normal_delivery_single_channel_ignores_preference(
    mode, visual, tts
):
    worker = DeliveryHarness(mode)
    j = job(visual=visual, tts=tts)
    asyncio.run(_async_process_job(worker, j))
    assert worker.calls.count("tts" if tts else "visual") == 1
    assert len(j.successful_channels) == 1


def test_no_fallback_changes_text_payload_or_exact_recipient_list():
    assert 'job.text_tts if audible else None' in MANAGER
    assert 'job.text_notify if job.notify_outputs else None' in MANAGER
    assert "self._select_requested_outputs(" in MANAGER
    assert "job.routing_channel_retry = desired_retry" in MANAGER
    assert "self._prepare_staged_route(job)" in MANAGER
