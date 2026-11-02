"""Durable dashboard queue ordering and private authenticated message access."""
from __future__ import annotations

import ast
import asyncio
from collections import deque
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
SOURCE = (COMPONENT / "manager.py").read_text(encoding="utf-8")
INIT = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
MODEL = (COMPONENT / "models.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
MANAGER = next(n for n in TREE.body if isinstance(n, ast.ClassDef)
               and n.name == "AnnouncementManager")


def standalone(name):
    method = next(n for n in MANAGER.body
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n.name == name)
    ns = {"ServiceValidationError": ValueError, "asyncio": asyncio,
          "_TERMINAL_JOB_STATES": {"cancelled", "completed", "completed_with_errors", "failed"}}
    exec(compile("from __future__ import annotations\n" + ast.unparse(method),
                 name, "exec"), ns)
    return ns[name]


class Job:
    def __init__(self, id, order, created, *, active=False):
        self.job_id = id
        self.queue_order = order
        self.created_at = created
        self.title = "Private " + id
        self.level = "info"
        self.status = "processing" if active else "pending"
        self.text_tts = "Confidential speech " + id
        self.text_notify = "Confidential visual " + id
        self.ai = {"pending_preprocessing": False, "mode": "rewrite"}
        self.routing_stage = "primary"
        self.related_job_ids = ()
        self.group_id = None

    def to_dict(self):
        return {"job_id": self.job_id, "queue_order": self.queue_order,
                "created_at": self.created_at, "status": self.status}


class Store:
    def __init__(self):
        self.saved = []

    async def async_save(self, obj):
        self.saved.append(obj)


class Fake:
    _queue_order_key = staticmethod(standalone("_queue_order_key"))
    _normalise_queue_orders = standalone("_normalise_queue_orders")
    queue_view = standalone("queue_view")
    async_reorder_queue = standalone("async_reorder_queue")
    _serialize = standalone("_serialize")

    def __init__(self, jobs):
        self._queue = deque(jobs)
        self._active_jobs = {}
        self._next_queue_order = 0
        self._last = None
        self._ai_history = deque(maxlen=20)
        self._volume_restore = {}
        self._save_lock = asyncio.Lock()
        self._store = Store()
        self._wake = SimpleNamespace(set=lambda: None)
        self.updated = 0

    def _notify_update(self):
        self.updated += 1


def test_manual_reorder_survives_durable_serialization_without_changing_creation_times():
    jobs = [
        Job("a", None, "2026-10-30T10:00:00+00:00"),
        Job("b", None, "2026-10-30T11:00:00+00:00"),
        Job("c", None, "2026-10-30T12:00:00+00:00"),
    ]
    fake = Fake(jobs)
    fake._normalise_queue_orders()
    result = asyncio.run(fake.async_reorder_queue(
        "c", "up", neighbor_job_id="b"))
    assert result["moved"] is True
    assert [item.job_id for item in fake._queue] == ["a", "c", "b"]
    assert [item["job_id"] for item in fake._store.saved[-1]["jobs"]] == ["a", "c", "b"]
    assert [item.created_at for item in jobs] == [
        "2026-10-30T10:00:00+00:00",
        "2026-10-30T11:00:00+00:00",
        "2026-10-30T12:00:00+00:00",
    ]
    persisted = [Job(item["job_id"], item["queue_order"], item["created_at"])
                 for item in fake._store.saved[-1]["jobs"]]
    restored = Fake(persisted)
    restored._normalise_queue_orders()
    assert [job.job_id for job in restored._queue] == ["a", "c", "b"]
    assert restored._next_queue_order > max(job.queue_order for job in restored._queue)


def test_stale_neighbor_rejected_and_active_jobs_not_moved():
    fake = Fake([Job("a", 0, "2026-10-30"), Job("b", 1, "2026-10-31")])
    fake._active_jobs = {"active": Job("active", 2, "2026-11-01", active=True)}
    for args in (("b", "up", "missing"), ("active", "up", "a")):
        try:
            asyncio.run(fake.async_reorder_queue(
                args[0], args[1], neighbor_job_id=args[2]))
        except ValueError:
            pass
        else:
            raise AssertionError("Rejected queue mutation was allowed")
    assert not fake._store.saved
    assert [job.job_id for job in fake._queue] == ["a", "b"]


def test_queue_snapshot_is_complete_and_uses_only_explicit_authenticated_service():
    fake = Fake([Job("a", 0, "2026-10-30"), Job("b", 1, "2026-10-31")])
    fake._active_jobs["live"] = Job("live", 3, "2026-11-01", active=True)
    snapshot = fake.queue_view()
    assert snapshot["queue_size"] == 2
    assert snapshot["active_count"] == 1
    assert [item["job_id"] for item in snapshot["jobs"]] == ["a", "b"]
    assert snapshot["jobs"][0]["text_tts"] == "Confidential speech a"
    assert snapshot["jobs"][0]["text_notify"] == "Confidential visual a"
    assert snapshot["active"][0]["active"] is True
    # Never include queued text in the ordinary sensor public status.
    status = SOURCE.split("    def status_dict(", 1)[1].split("    async def async_start(", 1)[0]
    assert "job.public_dict()" in status and "include_text=True" not in status
    assert 'supports_response=SupportsResponse.OPTIONAL' in INIT
    assert '"list_queue"' in (COMPONENT / "const.py").read_text()
    assert '"reorder_queue"' in (COMPONENT / "const.py").read_text()


def test_all_requeue_paths_use_manual_order_and_model_restores_previous_jobs():
    assert SOURCE.count("key=self._queue_order_key") >= 3
    assert 'if isinstance(item.get("queue_order"), int)' in SOURCE
    assert 'payload.setdefault("queue_order", None)' in MODEL
    assert "job.queue_order = self._next_queue_order" in SOURCE
    assert "self._next_queue_order += 1" in SOURCE
    assert "job.queue_order: int | None" not in MODEL  # dataclass field, not dynamic
    assert "queue_order: int | None = None" in MODEL
