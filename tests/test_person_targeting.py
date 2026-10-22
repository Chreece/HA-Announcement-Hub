"""Fail-closed person targeting and group routing regression coverage."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub"
spec = importlib.util.spec_from_file_location(
    "announcement_hub_person_targeting_test", COMPONENT / "person_targeting.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
resolve_person_rooms = module.resolve_person_rooms
PersonTargetError = module.PersonTargetError


class FakeStates:
    def __init__(self, records):
        self.records = records

    def async_all(self, domain=None):
        return [
            value for key, value in self.records.items()
            if domain is None or key.startswith(domain + ".")
        ]

    def get(self, entity_id):
        return self.records.get(entity_id)


def state(entity_id, value, **attributes):
    return SimpleNamespace(
        entity_id=entity_id, state=value, attributes=attributes
    )


def household():
    return SimpleNamespace(states=FakeStates({
        "person.john": state("person.john", "home", friendly_name="John", source="device_tracker.john"),
        "person.alice": state("person.alice", "home", friendly_name="Alice"),
        "device_tracker.john": state("device_tracker.john", "home", room="Küche"),
        "sensor.alice_room": state("sensor.alice_room", "Living Room"),
    }))


def test_named_and_entity_people_with_duplicate_deduplication():
    assert resolve_person_rooms(
        household(), ["John, person.alice, person.john"],
        {"person.alice": {"tracker": "sensor.alice_room"}},
    ) == [
        ("person.john", "Küche"),
        ("person.alice", "Living Room"),
    ]


def test_wrong_missing_or_ambiguous_person_never_selects_another_room():
    hass = household()
    with pytest.raises(PersonTargetError, match="Unknown or ambiguous"):
        resolve_person_rooms(hass, ["Missing"])
    with pytest.raises(PersonTargetError, match="target_person is empty"):
        resolve_person_rooms(hass, [])
    hass.states.records["person.jane"] = state(
        "person.jane", "home", friendly_name="John"
    )
    with pytest.raises(PersonTargetError, match="ambiguous"):
        resolve_person_rooms(hass, "John")


def test_unavailable_configured_sensor_does_not_use_fallback_source():
    hass = household()
    hass.states.records["sensor.bad"] = state("sensor.bad", "unavailable", room="Kitchen")
    with pytest.raises(PersonTargetError, match="No current room"):
        resolve_person_rooms(
            hass, "person.john", {"person.john": {"tracker": "sensor.bad"}}
        )


def test_away_person_is_not_announced_without_explicit_opt_in():
    hass = household()
    hass.states.records["person.john"].state = "not_home"
    with pytest.raises(PersonTargetError, match="not home"):
        resolve_person_rooms(hass, "person.john")
    assert resolve_person_rooms(hass, "person.john", {
        "person.john": {"ignore_home": True}
    }) == [("person.john", "Küche")]


def test_person_with_no_current_room_fails_closed():
    hass = household()
    hass.states.records["device_tracker.john"].attributes.clear()
    with pytest.raises(PersonTargetError, match="No current room"):
        resolve_person_rooms(hass, "person.john")


def test_person_routing_never_inherits_general_or_fallback_paths():
    manager = (COMPONENT / "manager.py").read_text()
    service = (COMPONENT / "__init__.py").read_text()
    assert "and not _person_targeted" in manager
    assert "strict_targets=bool(requested) or _person_targeted" in manager
    assert "explicit_targeting = bool(requested) or bool(channel_tokens) or _person_targeted" in manager
    assert 'local["_person_targeted"] = True' in service
    assert 'room_people.setdefault(area_id, []).append(person_id)' in service
    assert 'for pending_job in created:' in service
    assert 'if (call.data.get(ATTR_MANUAL_TARGETS) or any(' in service
