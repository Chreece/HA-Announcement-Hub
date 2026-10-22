"""Resolve explicit person recipients to rooms without broadening their audience.

Person routing is intentionally opt-in. A stale, ambiguous, away, or missing
room source fails closed: it can never silently turn into an all-room send.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class PersonTargetError(ValueError):
    """The requested person cannot be safely located."""


_INVALID_ROOMS = frozenset({
    "", "unknown", "unavailable", "none", "null", "home", "not_home",
    "away", "on", "off", "true", "false",
})


def _room_from_state(state: Any, *, allow_state: bool = True) -> str | None:
    if state is None:
        return None
    if str(getattr(state, "state", "")).strip().casefold() in {
        "unknown", "unavailable",
    }:
        return None
    attributes = getattr(state, "attributes", {}) or {}
    if isinstance(attributes, Mapping):
        for key in ("area_id", "room", "area", "room_name"):
            value = attributes.get(key)
            if isinstance(value, str) and value.strip().casefold() not in _INVALID_ROOMS:
                return value.strip()
    if allow_state:
        value = str(getattr(state, "state", "") or "").strip()
        if value.casefold() not in _INVALID_ROOMS:
            return value
    return None


def _tokens(requested: Sequence[str] | str) -> list[str]:
    values = [requested] if isinstance(requested, str) else requested
    return [
        value.strip()
        for raw in values
        for value in str(raw).split(",")
        if value.strip()
    ]


def resolve_person_ids(hass: Any, requested: Sequence[str] | str) -> list[str]:
    """Find exact Home Assistant person identities without room/home restrictions."""
    people = {item.entity_id: item for item in hass.states.async_all("person")}
    tokens = _tokens(requested)
    if not tokens:
        raise PersonTargetError("target_person is empty")
    result: list[str] = []
    for token in tokens:
        exact = people.get(token)
        if exact is None:
            matches = [
                item for item in people.values()
                if str(item.attributes.get("friendly_name", "")).casefold()
                == token.casefold()
            ]
            if len(matches) != 1:
                raise PersonTargetError(
                    f"Unknown or ambiguous person {token!r}; use person.entity_id"
                )
            exact = matches[0]
        if exact.entity_id not in result:
            result.append(exact.entity_id)
    return result


PERSON_DESTINATIONS = ("room", "mobile", "watch", "tablet", "other")


def selected_person_destinations(
    profile: Mapping[str, Any], requested: Sequence[str] | str,
) -> dict[str, tuple[str, ...]]:
    """Map friendly destination types to explicitly configured HA entities."""
    names = _tokens(requested)
    if not names or any(name not in PERSON_DESTINATIONS for name in names):
        raise PersonTargetError("Invalid person destination; choose room, mobile, watch, tablet or other")
    configured = profile.get("destinations") or {}
    if not isinstance(configured, Mapping):
        configured = {}
    result: dict[str, tuple[str, ...]] = {}
    for name in dict.fromkeys(names):
        if name == "room":
            result[name] = ()
            continue
        value = configured.get(name, [])
        if not isinstance(value, (list, tuple)):
            value = ()
        entries = tuple(dict.fromkeys(
            str(entity).strip() for entity in value
            if isinstance(entity, str) and str(entity).startswith(("notify.", "media_player."))
        ))
        if not entries:
            raise PersonTargetError(
                f"Destination {name!r} is not configured for this person"
            )
        result[name] = entries
    return result


def resolve_person_rooms(
    hass: Any,
    requested: Sequence[str] | str,
    profiles: Mapping[str, Any] | None = None,
) -> list[tuple[str, str]]:
    """Return (person entity ID, room name/ID), deduplicated in input order.

    The caller must resolve each returned room using Home Assistant's area
    registry, and send only to that area's configured outputs. Never use
    occupancy fallback for these explicit person recipients.
    """
    people = {
        item.entity_id: item for item in hass.states.async_all("person")
    }
    profiles = profiles if isinstance(profiles, Mapping) else {}
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    tokens = _tokens(requested)
    if not tokens:
        raise PersonTargetError("target_person is empty")
    for token in tokens:
        exact = people.get(token)
        if exact is None:
            matching = [
                item for item in people.values()
                if str(item.attributes.get("friendly_name", "")).casefold()
                == token.casefold()
            ]
            if len(matching) != 1:
                raise PersonTargetError(
                    f"Unknown or ambiguous person {token!r}; use person.entity_id"
                )
            exact = matching[0]
        entity_id = exact.entity_id
        if entity_id in seen:
            continue
        seen.add(entity_id)
        profile = profiles.get(entity_id, {})
        if not isinstance(profile, Mapping):
            profile = {}
        if exact.state != "home" and not profile.get("ignore_home", False):
            raise PersonTargetError(
                f"{entity_id} is not home; explicit person announcements "
                "will not fall back to another room"
            )

        configured_tracker = str(profile.get("tracker") or "").strip()
        if configured_tracker:
            room = _room_from_state(hass.states.get(configured_tracker))
            # A configured source is authoritative: do not use stale fallback
            # person attributes when it is unavailable or has no room.
        else:
            room = _room_from_state(exact, allow_state=False)
            if room is None:
                automatic_source = exact.attributes.get("source")
                if isinstance(automatic_source, str):
                    room = _room_from_state(hass.states.get(automatic_source))
        if room is None:
            raise PersonTargetError(
                f"No current room for {entity_id}; configure a room tracker "
                "in Announcement Hub > Configure > People"
            )
        found.append((entity_id, room))
    return found
