"""Executable dashboard resource auto-registration safety and upgrade tests."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

FILE = (Path(__file__).resolve().parents[1] / "custom_components"
        / "announcement_hub" / "dashboard_resource.py")
spec = importlib.util.spec_from_file_location("hub_dashboard_resource", FILE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Collection:
    def __init__(self, items=(), *, loaded=False, fail_load=False):
        self.loaded = loaded
        self._stored = list(items)
        self._items = list(items) if loaded else []
        self.fail_load = fail_load
        self.loads = 0
        self.creates = []
        self.updates = []

    async def async_load(self):
        self.loads += 1
        if self.fail_load:
            raise RuntimeError("storage unavailable")
        self._items = [dict(item) for item in self._stored]

    def async_items(self):
        return list(self._items)

    async def async_create_item(self, value):
        self.creates.append(dict(value))
        self._items.append({**value, "id": len(self._items) + 1})

    async def async_update_item(self, item_id, value):
        self.updates.append((item_id, dict(value)))
        for item in self._items:
            if item["id"] == item_id:
                item.update(value)
                break


def hass(resources, mode="storage"):
    return SimpleNamespace(data={"lovelace": SimpleNamespace(
        resource_mode=mode, resources=resources,
    )})


def run(h, version="0.9.40"):
    return asyncio.run(mod.async_ensure_card_resource(h, version))


def test_preserves_existing_lovelace_resources_before_creating_card():
    earlier = {"id": 9, "res_type": "module", "url": "/local/other-card.js"}
    resources = Collection([earlier], loaded=False)
    assert run(hass(resources))
    assert resources.loads == 1
    assert earlier in resources.async_items()
    assert resources.creates == [
        {"res_type": "module", "url": mod.CARD_RESOURCE_PATH + "?v=0.9.40"}
    ]


def test_auto_registration_is_idempotent_across_restart():
    resources = Collection(loaded=True)
    ha = hass(resources)
    assert run(ha)
    assert run(ha)
    assert len(resources.creates) == 1


def test_existing_manually_registered_resource_is_not_replaced_or_duplicated():
    original = {"id": 17, "res_type": "module", "url": mod.CARD_RESOURCE_PATH}
    resources = Collection([original], loaded=False)
    assert run(hass(resources))
    assert resources.creates == []
    assert resources.updates == []
    assert resources.async_items()[0] == original


def test_auto_versioned_resource_updates_with_no_duplicate():
    original = {
        "id": 17, "res_type": "module",
        "url": mod.CARD_RESOURCE_PATH + "?v=0.9.39",
    }
    resources = Collection([original], loaded=False)
    assert run(hass(resources))
    assert resources.creates == []
    assert resources.updates == [
        (17, {"res_type": "module", "url": mod.CARD_RESOURCE_PATH + "?v=0.9.40"})
    ]


def test_yaml_mode_is_never_mutated():
    resources = Collection([{"id": 1, "url": "/local/test.js"}])
    assert not run(hass(resources, mode="yaml"))
    assert resources.loads == 0
    assert resources.creates == []


def test_missing_lovelace_is_safe():
    assert not run(SimpleNamespace(data={}))


def test_failed_storage_load_does_not_overwrite_resources():
    resources = Collection(
        [{"id": 1, "res_type": "module", "url": "/local/important.js"}],
        fail_load=True,
    )
    assert not run(hass(resources))
    assert resources.creates == []
    assert resources.updates == []


def test_existing_non_module_is_preserved():
    original = {"id": 2, "res_type": "js", "url": mod.CARD_RESOURCE_PATH}
    resources = Collection([original], loaded=True)
    assert not run(hass(resources))
    assert resources.creates == []
    assert resources.updates == []


def test_setup_hooks_lovelace_after_start_instead_of_synchronous_unsafe_write():
    setup = FILE.with_name("__init__.py").read_text(encoding="utf-8")
    assert "async_at_started(hass, _register_dashboard_card)" in setup
    assert "await async_ensure_card_resource(started_hass, VERSION)" in setup
