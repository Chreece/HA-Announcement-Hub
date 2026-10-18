"""Executable persistence/retry contracts for announcements without delivery."""

from __future__ import annotations

import ast
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "custom_components" / "announcement_hub" / "manager.py"
).read_text(encoding="utf-8")

tree = ast.parse(SOURCE)
klass = next(
    node for node in tree.body
    if isinstance(node, ast.ClassDef) and node.name == "AnnouncementManager"
)
methods = ("_requeue_undelivered_job", "_next_runnable_job")


class Harness:
    def __init__(self):
        self._availability_timeout = 4.0
        self._queue = deque()
        self._wake = SimpleNamespace(set=lambda: None)
        self._staged_calls = []

    def _requeue_undelivered_stage(self, job, reason):
        self._staged_calls.append((job.job_id, reason))
        job.status = "pending"
        self._queue.append(job)

    def _staged_route_ready(self, job):
        return False

    def _job_runnable_now(self, job):
        return bool(job.ready)


for node in klass.body:
    if isinstance(node, ast.FunctionDef) and node.name in methods:
        ns = {
            "datetime": datetime,
            "timedelta": timedelta,
            "UTC": UTC,
        }
        exec(
            compile(
                "from __future__ import annotations\n" + ast.unparse(node),
                "AnnouncementHub manager durability method",
                "exec",
            ),
            ns,
        )
        setattr(Harness, node.name, ns[node.name])


def make_job(*, routing_mode="normal", ready=True):
    return SimpleNamespace(
        job_id="air-quality",
        routing_mode=routing_mode,
        routing_retry_after=None,
        successful_channels=[],
        status="processing",
        started_at=datetime.now(UTC).isoformat(),
        finished_at=None,
        error="previous error",
        channel_errors={"old": "failed"},
        ready=ready,
    )


def test_normal_explicit_device_failure_stays_pending_no_cross_provider():
    h = Harness()
    job = make_job(ready=True)
    h._requeue_undelivered_job(job, "provider failure")
    assert job in h._queue
    assert job.status == "pending"
    assert job.started_at is None
    assert job.error is None
    assert not job.channel_errors
    assert job.routing_retry_after is not None
    assert h._next_runnable_job() is None
    job.routing_retry_after = (
        datetime.now(UTC) - timedelta(seconds=1)
    ).isoformat()
    assert h._next_runnable_job() is job
    assert job.routing_retry_after is None
    assert not h._staged_calls


def test_unavailable_nonroom_output_keeps_waiting_until_available():
    h = Harness()
    job = make_job(ready=False)
    h._queue.append(job)
    assert h._next_runnable_job() is None
    assert h._queue == deque([job])
    job.ready = True
    assert h._next_runnable_job() is job


def test_staged_room_errors_delegate_to_tier_progression():
    h = Harness()
    job = make_job(routing_mode="room_fallback")
    h._requeue_undelivered_job(job, "selected outputs did not deliver")
    assert h._staged_calls == [("air-quality", "selected outputs did not deliver")]
    assert h._queue == deque([job])


def test_worker_only_completes_after_successful_delivery():
    worker = SOURCE[
        SOURCE.index("    async def _async_worker("):
        SOURCE.index("    def _staged_areas(", SOURCE.index("    async def _async_worker("))
    ]
    assert "if not job.successful_channels:" in worker
    assert 'self._requeue_undelivered_job(job, "provider failure")' in worker
    assert '"selected outputs did not deliver"' in worker
    assert "if job.routing_mode == \"room_fallback\" and not job.successful_channels" not in worker


def test_no_expire_waiter_or_requeue_busy_loop():
    assert "def _expire_waiting_job(" not in SOURCE
    assert "def _next_runnable_job(" in SOURCE
    assert "job.routing_retry_after" in SOURCE
    assert "delay = max(self._availability_timeout, 5.0)" in SOURCE
