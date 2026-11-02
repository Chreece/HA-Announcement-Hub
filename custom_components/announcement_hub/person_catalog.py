"""Person-scoped output discovery and strict owned-output selection.

Only outputs explicitly mapped in a person's Hub profile are eligible. A
platform selection never expands to all outputs of that integration.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _assigned_entities(profile: Mapping[str, Any]) -> tuple[str, ...]:
    slots = profile.get("destinations") or {}
    if not isinstance(slots, Mapping):
        return ()
    return tuple(dict.fromkeys(
        entity
        for slot, values in slots.items()
        if slot in {"mobile", "watch", "tablet", "other"}
        and isinstance(values, (list, tuple))
        for entity in values
        if isinstance(entity, str)
        and entity.startswith(("notify.", "media_player."))
    ))


def without_room_when_owned(
    destinations: Sequence[str],
    *,
    integrations: Sequence[str] = (),
    devices: Sequence[str] = (),
) -> tuple[str, ...]:
    """Exact person-owned selections replace room routing (including defaults).

    Legacy named destination aliases stay intact when no new owned selection
    is requested, so existing automations keep their original behavior.
    """
    names = tuple(dict.fromkeys(destinations))
    return tuple(name for name in names if name != "room") if (
        integrations or devices
    ) else names


def owned_person_catalog(
    profiles: Mapping[str, Any],
    metadata: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> dict[str, dict[str, list[dict[str, str]]]]:
    """List only integrations/devices with active, profile-assigned endpoints.

    `metadata` is built from HA's enabled entity/device registries; it contains
    no credentials, unassigned devices or other people's personal endpoints.
    """
    result: dict[str, dict[str, list[dict[str, str]]]] = {}
    for person_id, profile in profiles.items():
        if not isinstance(profile, Mapping) or not profile.get("enabled", True):
            continue
        owned = metadata.get(person_id, {})
        integrations: dict[str, str] = {}
        devices: dict[str, str] = {}
        for entity_id in _assigned_entities(profile):
            detail = owned.get(entity_id) or {}
            integration = str(detail.get("integration") or "")
            device = str(detail.get("device") or "")
            if integration:
                integrations[integration] = integration.replace("_", " ").title()
            if device:
                devices[device] = str(detail.get("device_label") or device)
        result[person_id] = {
            "integrations": [
                {"value": value, "label": label}
                for value, label in sorted(integrations.items(), key=lambda item: (item[1].casefold(), item[0]))
            ],
            "devices": [
                {"value": value, "label": label}
                for value, label in sorted(devices.items(), key=lambda item: (item[1].casefold(), item[0]))
            ],
        }
    return result


def resolve_owned_person_outputs(
    profile: Mapping[str, Any],
    metadata: Mapping[str, Mapping[str, str]],
    *,
    integrations: Sequence[str] = (),
    devices: Sequence[str] = (),
) -> dict[str, tuple[str, ...]]:
    """Return exact assigned entities for each requested owned group.

    Unmatched groups are returned empty for multi-person requests, where an
    integration or device can belong to one person but not another. The caller
    must reject globally unmatched groups before enqueuing any delivery.
    """
    assigned = _assigned_entities(profile)
    result: dict[str, tuple[str, ...]] = {}
    for value in dict.fromkeys(integrations):
        result["integration:" + value] = tuple(
            entity_id for entity_id in assigned
            if str((metadata.get(entity_id) or {}).get("integration") or "") == value
        )
    for value in dict.fromkeys(devices):
        result["device:" + value] = tuple(
            entity_id for entity_id in assigned
            if str((metadata.get(entity_id) or {}).get("device") or "") == value
        )
    return result
