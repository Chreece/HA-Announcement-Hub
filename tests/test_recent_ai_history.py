"""Persistent, privacy-safe diagnostics for intermittent AI fallback."""

from __future__ import annotations

import ast
from collections import deque
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "custom_components" / "announcement_hub" /
          "manager.py").read_text(encoding="utf-8")
CLASS = next(node for node in ast.parse(SOURCE).body
             if isinstance(node, ast.ClassDef) and node.name == "AnnouncementManager")


def standalone(name):
    node = next(m for m in CLASS.body
                if isinstance(m, ast.FunctionDef) and m.name == name)
    ns = {"deque": deque}
    exec(compile("from __future__ import annotations\n" + ast.unparse(node),
                 name, "exec"), ns)
    return ns[name]


def test_interleaved_ai_failures_survive_later_success_in_sensor():
    history = deque([
        {
            "job_id": "one", "created_at": "2026-10-21",
            "status": "fallback_original", "failure_reason": "invalid_json",
            "source": "inherit", "mode": "rewrite",
            "attempts": [{"agent": "conversation.local", "outcome": "invalid_json"}],
        },
        {
            "job_id": "two", "created_at": "2026-10-21",
            "status": "rewritten", "failure_reason": None,
            "source": "inherit", "mode": "rewrite", "attempts": [],
        },
        {
            "job_id": "three", "created_at": "2026-10-21",
            "status": "disabled", "failure_reason": None,
            "source": "override", "mode": "rewrite", "attempts": [],
        },
    ], maxlen=20)
    model = SimpleNamespace(
        _queue=deque(), _active_jobs={}, _last=None, _current=None,
        _running=True, _worker_task=None, _ai_tasks={},
        _prefetch_tasks={}, _ai_history=history,
    )
    state = standalone("status_dict")(model)
    assert [x["status"] for x in state["recent_ai"]] == [
        "fallback_original", "rewritten", "disabled",
    ]
    snapshot = standalone("_serialize")(model)
    assert snapshot["ai_history"] == list(history)
    assert "source_tts" not in str(snapshot["ai_history"])
    assert "source_notify" not in str(snapshot["ai_history"])


def test_history_ring_buffer_is_bounded():
    ring = deque(maxlen=20)
    for index in range(80):
        ring.append({"job_id": str(index), "status": "rewritten"})
    assert len(ring) == 20
    assert ring[0]["job_id"] == "60"
    assert "deque(maxlen=20)" in SOURCE
