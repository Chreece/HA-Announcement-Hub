from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


root = Path.cwd()
component = root / "custom_components" / "announcement_hub"
manager = component / "manager.py"
init = component / "__init__.py"
const = component / "const.py"
manifest = component / "manifest.json"
resource_tests = root / "tests" / "test_resources.py"
changelog = root / "CHANGELOG.md"

replace_once(
    manager,
    "        self._active_tts_player: str | None = None\n",
    "        self._active_tts_player: str | None = None\n"
    "        self._stop_lock = asyncio.Lock()\n",
)

replace_once(
    manager,
    "        self._worker_task = self.hass.async_create_task(\n"
    "            self._async_worker(), f\"{DOMAIN} worker\"\n"
    "        )\n",
    "        self._worker_task = self.entry.async_create_background_task(\n"
    "            self.hass,\n"
    "            self._async_worker(),\n"
    "            f\"{DOMAIN} worker\",\n"
    "        )\n",
)

old_stop = '''    async def async_stop(self) -> None:\n        self._running = False\n        self._wake.set()\n        if self._active_tts_player:\n            await self._async_stop_player(self._active_tts_player)\n        if self._worker_task:\n            self._worker_task.cancel()\n            with suppress(asyncio.CancelledError):\n                await self._worker_task\n            self._worker_task = None\n        for task in self._prefetch_tasks.values():\n            task.cancel()\n        if self._prefetch_tasks:\n            await asyncio.gather(\n                *self._prefetch_tasks.values(), return_exceptions=True\n            )\n        self._prefetch_tasks.clear()\n        if self._current and self._current.status == "processing":\n            self._current.status = "pending"\n            self._current.started_at = None\n            self._queue.appendleft(self._current)\n            self._current = None\n        await self._store.async_save(self._serialize())\n        self._notify_update()\n'''
new_stop = '''    async def async_stop(self) -> None:\n        \"\"\"Stop all integration-owned tasks and persist the queue exactly once.\"\"\"\n        async with self._stop_lock:\n            if (\n                not self._running\n                and self._worker_task is None\n                and not self._prefetch_tasks\n            ):\n                return\n\n            self._running = False\n            self._wake.set()\n\n            # The permanent queue worker is a config-entry background task so it\n            # never participates in Home Assistant's startup barrier. We still\n            # explicitly cancel and await it here for deterministic unload and\n            # shutdown ordering.\n            worker_task = self._worker_task\n            self._worker_task = None\n            if worker_task is not None:\n                worker_task.cancel()\n                with suppress(asyncio.CancelledError):\n                    await worker_task\n\n            # Prefetch operations are also entry-owned background tasks. Cancel\n            # and await every one before the queue snapshot is written.\n            prefetch_tasks = tuple(self._prefetch_tasks.values())\n            self._prefetch_tasks.clear()\n            for task in prefetch_tasks:\n                task.cancel()\n            if prefetch_tasks:\n                await asyncio.gather(*prefetch_tasks, return_exceptions=True)\n\n            if self._active_tts_player:\n                await self._async_stop_player(self._active_tts_player)\n            self._active_tts_player = None\n\n            if self._current and self._current.status == "processing":\n                self._current.status = "pending"\n                self._current.started_at = None\n                self._queue.appendleft(self._current)\n                self._current = None\n\n            await self._store.async_save(self._serialize())\n            self._notify_update()\n'''
replace_once(manager, old_stop, new_stop)

replace_once(
    manager,
    "        task = self.hass.async_create_task(\n"
    "            self._async_prefetch(job), f\"{DOMAIN} prefetch {job.job_id}\"\n"
    "        )\n",
    "        task = self.entry.async_create_background_task(\n"
    "            self.hass,\n"
    "            self._async_prefetch(job),\n"
    "            f\"{DOMAIN} prefetch {job.job_id}\",\n"
    "        )\n",
)

replace_once(
    init,
    "from homeassistant.config_entries import ConfigEntry\n"
    "from homeassistant.core import (\n"
    "    HomeAssistant,\n",
    "from homeassistant.config_entries import ConfigEntry\n"
    "from homeassistant.core import (\n"
    "    HassJob,\n"
    "    HomeAssistant,\n",
)

old_setup = '''    await manager.async_start()\n    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)\n\n    async def async_options_updated(\n        hass: HomeAssistant, updated_entry: ConfigEntry\n    ) -> None:\n        await manager.async_update_config()\n\n    entry.async_on_unload(entry.add_update_listener(async_options_updated))\n    return True\n'''
new_setup = '''    try:\n        await manager.async_start()\n\n        # Run graceful queue shutdown before Home Assistant cancels background\n        # tasks. The returned remover is tied to config-entry unload so a normal\n        # reload does not leave a stale global shutdown job behind.\n        entry.async_on_unload(\n            hass.async_add_shutdown_job(\n                HassJob(manager.async_stop, f\"{DOMAIN} shutdown\")\n            )\n        )\n\n        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)\n    except BaseException:\n        await manager.async_stop()\n        if hass.data.get(DOMAIN, {}).get("manager") is manager:\n            hass.data[DOMAIN].pop("manager", None)\n        raise\n\n    async def async_options_updated(\n        hass: HomeAssistant, updated_entry: ConfigEntry\n    ) -> None:\n        await manager.async_update_config()\n\n    entry.async_on_unload(entry.add_update_listener(async_options_updated))\n    return True\n'''
replace_once(init, old_setup, new_setup)

replace_once(const, 'VERSION: Final = "0.3.0"', 'VERSION: Final = "0.3.1"')
replace_once(manifest, '"version": "0.3.0"', '"version": "0.3.1"')
replace_once(
    resource_tests,
    'assert manifest["version"] == "0.3.0"',
    'assert manifest["version"] == "0.3.1"',
)

lifecycle_test = root / "tests" / "test_task_lifecycle.py"
lifecycle_test.write_text(
    '''"""Regression tests for Home Assistant task lifecycle integration."""\n\nfrom __future__ import annotations\n\nimport ast\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\nCOMPONENT = ROOT / "custom_components" / "announcement_hub"\n\n\ndef _calls(path: Path) -> list[str]:\n    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))\n    result: list[str] = []\n    for node in ast.walk(tree):\n        if not isinstance(node, ast.Call):\n            continue\n        func = node.func\n        parts: list[str] = []\n        while isinstance(func, ast.Attribute):\n            parts.append(func.attr)\n            func = func.value\n        if isinstance(func, ast.Name):\n            parts.append(func.id)\n        result.append(".".join(reversed(parts)))\n    return result\n\n\ndef test_manager_uses_only_config_entry_background_tasks() -> None:\n    calls = _calls(COMPONENT / "manager.py")\n    assert "self.hass.async_create_task" not in calls\n    assert calls.count("self.entry.async_create_background_task") == 2\n\n\ndef test_graceful_shutdown_job_is_registered() -> None:\n    source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")\n    assert "hass.async_add_shutdown_job(" in source\n    assert 'HassJob(manager.async_stop, f"{DOMAIN} shutdown")' in source\n    assert "entry.async_on_unload(" in source\n\n\ndef test_stop_is_serialized_and_idempotent() -> None:\n    source = (COMPONENT / "manager.py").read_text(encoding="utf-8")\n    assert "self._stop_lock = asyncio.Lock()" in source\n    assert "async with self._stop_lock:" in source\n    assert "worker_task.cancel()" in source\n    assert "await worker_task" in source\n    assert "await asyncio.gather(*prefetch_tasks, return_exceptions=True)" in source\n''',
    encoding="utf-8",
)

old_changelog = "# Changelog\n\n## 0.3.0\n"
new_changelog = '''# Changelog\n\n## 0.3.1 - 2026-10-02\n\n- Fixed the permanent queue worker being registered as a normal Home Assistant\n  task, which made it participate in the startup barrier and survive into final\n  shutdown writes.\n- Registered the worker and TTS prefetch jobs as config-entry background tasks,\n  so they do not block startup and are automatically cancelled with the entry.\n- Added an awaited Home Assistant shutdown job plus serialized, idempotent\n  manager cleanup to cancel all tasks and persist the queue before shutdown.\n- Added lifecycle regression tests preventing normal `hass.async_create_task`\n  use from returning to the integration.\n\n## 0.3.0\n'''
replace_once(changelog, old_changelog, new_changelog)

print("Applied Announcement Hub 0.3.1 lifecycle hotfix")
