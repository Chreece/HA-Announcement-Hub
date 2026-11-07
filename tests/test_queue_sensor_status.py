"""Regression coverage for the queue sensor and privacy-safe status service."""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub"
INIT = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
SENSOR = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
CONSTANTS = (COMPONENT / "const.py").read_text(encoding="utf-8")
SERVICES = (COMPONENT / "services.yaml").read_text(encoding="utf-8")
CARD = (COMPONENT / "frontend" / "announcement-hub-card.js").read_text(encoding="utf-8")


def _queue_status_function(hass):
    tree = ast.parse(INIT)
    setup = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name == "async_setup")
    handler = next(node for node in setup.body
                   if isinstance(node, ast.AsyncFunctionDef)
                   and node.name == "async_queue_status")
    namespace = {
        "ServiceCall": object,
        "hass": hass,
        "ServiceResponse": dict,
        "DOMAIN": "announcement_hub",
        "er": SimpleNamespace(async_get=lambda hass: hass.registry),
        "_get_manager": lambda hass: hass.manager,
    }
    code = ast.fix_missing_locations(ast.Module(body=[handler], type_ignores=[]))
    exec(compile(code, "announcement_hub_queue_status_test.py", "exec"), namespace)
    return namespace["async_queue_status"]


def test_queue_sensor_has_stable_suggested_id_and_diagnostic_count():
    tree = ast.parse(SENSOR)
    sensor = next(node for node in tree.body
                  if isinstance(node, ast.ClassDef)
                  and node.name == "AnnouncementQueueSensor")
    attrs = {
        target.id: node.value.value for node in sensor.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
        for target in node.targets if isinstance(target, ast.Name)
    }
    assert attrs["_attr_suggested_object_id"] == "announcement_hub_queue"
    assert '_attr_translation_key = "queue"' in SENSOR
    assert 'return self._manager.queue_size' in SENSOR
    assert 'return self._manager.status_dict()' in SENSOR
    assert 'SIGNAL_UPDATE' in SENSOR
    assert 'async_dispatcher_connect(' in SENSOR


def test_status_response_resolves_real_registry_id_without_message_bodies():
    unique_id = "private-entry_queue"
    class Registry:
        def async_get_entity_id(self, domain, platform, key):
            assert (domain, platform, key) == (
                "sensor", "announcement_hub", unique_id
            )
            return "sensor.renamed_greek_oura"

    manager = SimpleNamespace(
        entry=SimpleNamespace(entry_id="private-entry"),
        queue_size=6,
        _active_jobs={"active-1": object(), "active-2": object()},
        # Queue texts are not accessed by this endpoint.
    )
    hass = SimpleNamespace(manager=manager, registry=Registry())
    status = _queue_status_function(hass)
    reply = asyncio.run(status(SimpleNamespace(return_response=True)))
    assert reply == {
        "queue_size": 6,
        "active_count": 2,
        "queue_entity_id": "sensor.renamed_greek_oura",
    }
    assert "text_notify" not in str(reply)
    assert "text_tts" not in str(reply)
    assert asyncio.run(status(SimpleNamespace(return_response=False))) is None


def test_status_is_available_when_the_sensor_was_disabled_or_not_registered():
    class Registry:
        def async_get_entity_id(self, *_args):
            return None

    manager = SimpleNamespace(
        entry=SimpleNamespace(entry_id="private-entry"),
        queue_size=4,
        _active_jobs={},
    )
    hass = SimpleNamespace(manager=manager, registry=Registry())
    status = _queue_status_function(hass)
    reply = asyncio.run(status(SimpleNamespace(return_response=True)))
    assert reply == {
        "queue_size": 4, "active_count": 0, "queue_entity_id": None,
    }


def test_status_is_registered_as_read_only_response_service():
    assert 'SERVICE_QUEUE_STATUS: Final = "queue_status"' in CONSTANTS
    assert "queue_status:\n" in SERVICES
    assert "SERVICE_QUEUE_STATUS" in INIT
    block = INIT.split(
        "if not hass.services.has_service(DOMAIN, SERVICE_QUEUE_STATUS):", 1
    )[1].split("if not hass.services.has_service(", 1)[0]
    assert 'hass.services.async_register(' in block
    assert "schema=probatio.Schema({})" in block
    assert "supports_response=SupportsResponse.OPTIONAL" in block
    assert "list_queue" not in block
    assert '"announcement_hub", "queue_status"' in CARD
    assert "entity.platform === \"announcement_hub\"" in CARD
    assert "queue_entity_id" in CARD
    assert 'this._queueServiceCount = reply.queue_size' in CARD
    assert "setInterval" in CARD and "disconnectedCallback" in CARD
