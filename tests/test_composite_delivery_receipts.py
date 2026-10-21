"""Executable tests for combined area and explicit-recipient deliveries.

Run real manager methods with a minimal HA-independent harness. A recipient
that succeeded on the first leg must never be sent the same action twice;
success must survive a queue-storage round trip.
"""

from __future__ import annotations

import ast
import asyncio
from collections import deque
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "custom_components/announcement_hub/manager.py").read_text(
    encoding="utf-8"
)
klass = next(
    node for node in ast.parse(SOURCE).body
    if isinstance(node, ast.ClassDef) and node.name == "AnnouncementManager"
)


def _install_method(harness, name: str):
    method = next(
        node for node in klass.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )
    scope = {
        "asyncio": asyncio,
        "suppress": suppress,
        "utcnow_iso": lambda: datetime.now(UTC).isoformat(),
        "EVENT_CANCELLED": "announcement_hub_cancelled",
        "ServiceValidationError": ValueError,
    }
    exec(
        compile("from __future__ import annotations\n" + ast.unparse(method),
                f"manager::{name}", "exec"),
        scope,
    )
    setattr(harness, name, scope[name])


class Harness:
    def __init__(self):
        self._queue = deque()
        self._current = None
        self._last = None
        self._prefetch_tasks = {}
        self._ai_tasks = {}
        self._group_success = {}
        self._cancel_requested = set()
        self._active_tts_players = set()
        self.events = []
        self.saved = 0
        self.delivered = []
        self.hass = SimpleNamespace()

    def _fill_ai_slots(self):
        pass

    def _fill_prefetch_slots(self):
        pass

    def _schedule_save(self):
        self.saved += 1

    def _notify_update(self):
        pass

    def _fire_event(self, event, job):
        self.events.append((event, job.job_id))

    def _raise_if_cancelled(self, job):
        if job.job_id in self._cancel_requested:
            raise AssertionError("Unexpected cancellation")

    def _record_channel_success(self, job, channel):
        job.successful_channels.append(channel)

    def _fire_channel_event(self, event, job, channel):
        self.events.append((event, job.job_id, channel))


for name in (
    "_group_already_delivered",
    "_mark_group_physical",
    "_cleanup_group_success",
    "_async_deliver_notification",
    "async_cancel",
):
    _install_method(Harness, name)


def job(job_id: str, *, group="g", related=()):
    return SimpleNamespace(
        job_id=job_id, group_id=group, related_job_ids=related,
        delivered_physical=[], successful_channels=[], status="pending",
        finished_at=None,
    )


def test_successful_recipient_persists_on_both_delivery_legs():
    h = Harness()
    area = job("area", related=("exact",))
    exact = job("exact")
    h._queue.extend((area, exact))
    h._mark_group_physical(area, "notify:entity:notify.tv")
    assert h._group_success == {"g": {"notify:entity:notify.tv"}}
    assert area.delivered_physical == exact.delivered_physical == [
        "notify:entity:notify.tv"
    ]
    assert h._group_already_delivered(exact, "notify:entity:notify.tv")
    # A different channel or physical recipient remains eligible.
    assert not h._group_already_delivered(exact, "snapcast:media_player.tv")
    assert not h._group_already_delivered(exact, "notify:entity:notify.other")
    assert not h._group_already_delivered(job("unrelated", group="h"),
                                           "notify:entity:notify.tv")


def test_duplicate_visual_output_is_marked_satisfied_without_sending_twice():
    h = Harness()
    exact = job("exact")
    h._queue.append(exact)
    h._group_success = {"g": {"notify:entity:notify.tv"}}
    output = SimpleNamespace(ref="entity:notify.tv")
    # This code path would need a real HA notify provider if it didn't return
    # before checking the output's provider profile.
    asyncio.run(h._async_deliver_notification(exact, output))
    assert exact.successful_channels == ["entity:notify.tv"]
    assert not h.events


def test_group_receipts_are_cleaned_only_after_final_pending_leg():
    h = Harness()
    area = job("area", related=("exact",))
    exact = job("exact")
    h._queue.extend((area, exact))
    h._mark_group_physical(area, "notify:entity:notify.tv")
    h._queue.remove(area)
    h._cleanup_group_success(area)
    assert "g" in h._group_success
    h._queue.remove(exact)
    h._cleanup_group_success(exact)
    assert not h._group_success


def test_cancelling_returned_job_cancels_related_pending_job():
    h = Harness()
    area = job("area", related=("exact",))
    exact = job("exact")
    h._queue.extend((area, exact))
    assert asyncio.run(h.async_cancel("area")) == "cancelled"
    assert not h._queue
    assert area.status == exact.status == "cancelled"
    assert set(h.events) == {
        ("announcement_hub_cancelled", "area"),
        ("announcement_hub_cancelled", "exact"),
    }


def test_normal_noncomposite_job_does_not_allocate_group_receipts():
    h = Harness()
    ordinary = job("ordinary", group=None)
    h._queue.append(ordinary)
    h._mark_group_physical(ordinary, "notify:entity:notify.tv")
    assert ordinary.delivered_physical == []
    assert h._group_success == {}
