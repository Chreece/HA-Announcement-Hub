"""Mobile push acknowledgments must not stall room FIFO for visual read time.

Exercise the real notification delivery method with Home Assistant service
operations replaced by deterministic in-memory helpers.
"""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

SOURCE = (Path(__file__).resolve().parents[1] /
          "custom_components" / "announcement_hub" / "manager.py").read_text("utf-8")
MANAGER = next(n for n in ast.parse(SOURCE).body
               if isinstance(n, ast.ClassDef) and n.name == "AnnouncementManager")
METHOD = next(n for n in MANAGER.body
              if isinstance(n, ast.AsyncFunctionDef)
              and n.name == "_async_deliver_notification")

NS = {
    "asyncio": asyncio,
    "JobCancelled": type("JobCancelled", (Exception,), {}),
    "HomeAssistantError": RuntimeError,
    "EVENT_CHANNEL_STARTED": "started",
    "INTEGRATION_NFANDROIDTV": "nfandroidtv",
    "INTEGRATION_MOBILE_APP": "mobile_app",
    "PROFILE_MAX_LENGTH": "max_length",
    "PROFILE_READING_WPM": "reading_words_per_minute",
    "PROFILE_MIN_DISPLAY": "minimum_display_seconds",
    "PROFILE_MAX_DISPLAY": "maximum_display_seconds",
    "PROFILE_DISPLAY_BUFFER": "display_buffer_seconds",
    "PROFILE_PART_GAP": "part_gap_seconds",
    "PROFILE_SHOW_PART_NUMBER": "show_part_number",
    "PROFILE_DEFAULT": "default",
    "normalise_notify_profile": lambda profile, integration: {
        "max_length": 1000,
        "reading_words_per_minute": 200,
        "minimum_display_seconds": 3.0,
        "maximum_display_seconds": 30.0,
        "display_buffer_seconds": 1,
        "part_gap_seconds": 0.15,
        "show_part_number": False,
    },
    "reading_seconds": lambda text, **kw: 25.0,
    "resolve_notify_profile": lambda profiles, integration: {},
    "split_message": lambda text, maximum: [text],
    "format_part_title": lambda title, **kw: title,
}
exec(compile("from __future__ import annotations\n" + ast.unparse(METHOD),
             "mobile quick notification", "exec"), NS)


class Harness:
    def __init__(self):
        self.holds = []
        self.sent = []
        self.success = []

    def _group_already_delivered(self, job, physical):
        return False

    def _raise_if_cancelled(self, job):
        pass

    def _fire_channel_event(self, *args):
        pass

    async def _async_deliver_notification_part(self, job, output, **kwargs):
        self.sent.append((output.ref, kwargs["message"]))

    async def _async_reading_hold(self, job, seconds):
        self.holds.append(seconds)

    def _mark_group_physical(self, job, physical):
        pass

    def _record_channel_success(self, job, channel):
        self.success.append(channel)


async def deliver(integration):
    h = Harness()
    job = SimpleNamespace(
        title="Test", notify_text="Hello", tts_text=None,
        notify_output_profiles={}, job_id="test",
    )
    output = SimpleNamespace(ref="entity:notify.example",
                             integration=integration)
    await NS["_async_deliver_notification"](h, job, output)
    return h


def test_phone_push_returns_without_25_second_reading_hold():
    h = asyncio.run(deliver("mobile_app"))
    assert h.sent == [("entity:notify.example", "Hello")]
    assert h.success == ["entity:notify.example"]
    assert h.holds == []


def test_tv_notification_keeps_reading_time_and_same_room_fifo():
    h = asyncio.run(deliver("nfandroidtv"))
    assert h.success == ["entity:notify.example"]
    assert h.holds == [25.0]


def test_other_expiring_visual_outputs_preserve_existing_hold_policy():
    h = asyncio.run(deliver("desktop"))
    assert h.holds == [25.0]
