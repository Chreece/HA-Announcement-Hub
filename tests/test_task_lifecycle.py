"""Regression tests for Home Assistant task lifecycle integration."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def _calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        parts: list[str] = []
        while isinstance(func, ast.Attribute):
            parts.append(func.attr)
            func = func.value
        if isinstance(func, ast.Name):
            parts.append(func.id)
        result.append(".".join(reversed(parts)))
    return result


def test_manager_uses_only_config_entry_background_tasks() -> None:
    calls = _calls(COMPONENT / "manager.py")
    assert "self.hass.async_create_task" not in calls
    assert calls.count("self.entry.async_create_background_task") == 2


def test_graceful_shutdown_job_is_registered() -> None:
    source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    assert "hass.async_add_shutdown_job(" in source
    assert 'HassJob(manager.async_stop, f"{DOMAIN} shutdown")' in source
    assert "entry.async_on_unload(" in source


def test_stop_is_serialized_and_idempotent() -> None:
    source = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "self._stop_lock = asyncio.Lock()" in source
    assert "async with self._stop_lock:" in source
    assert "worker_task.cancel()" in source
    assert "await worker_task" in source
    assert "await asyncio.gather(*prefetch_tasks, return_exceptions=True)" in source
