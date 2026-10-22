"""Per-person and per-room announcement enable controls.

Values live in the Home Assistant config entry so they persist across restarts,
and the scheduler reads them again before delivery of queued messages.
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_UPDATE


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Expose people and room switches and discover later config additions."""
    seen: set[tuple[str, str]] = set()

    def refresh() -> None:
        manager = entry.runtime_data
        profiles = manager.settings.get("person_profiles", {}) or {}
        areas = ar.async_get(hass).areas
        candidates = [
            ("person", person_id, person_id) for person_id in profiles
        ] + [
            ("area", area_id, area.name)
            for area_id, area in areas.items()
        ]
        new = []
        for kind, key, label in candidates:
            if (kind, key) in seen:
                continue
            seen.add((kind, key))
            new.append(AnnouncementEnableSwitch(hass, entry, kind, key, label))
        if new:
            async_add_entities(new)

    refresh()
    entry.async_on_unload(async_dispatcher_connect(
        hass, SIGNAL_UPDATE, refresh,
    ))


class AnnouncementEnableSwitch(SwitchEntity):
    """Individual, persistent permission gate, not an output itself."""

    _attr_has_entity_name = True

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry,
        kind: str, key: str, label: str,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.kind = kind
        self.key = key
        self._attr_unique_id = f"{entry.entry_id}:{kind}:{key}:enabled"
        self._attr_name = f"Announcements {label}"
        self._attr_icon = "mdi:account-voice" if kind == "person" else "mdi:volume-high"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Announcement Hub",
            "manufacturer": "Custom",
            "model": "Announcement Hub",
        }

    @property
    def is_on(self) -> bool:
        options = {**self.entry.data, **self.entry.options}
        if self.kind == "person":
            profiles = options.get("person_profiles", {}) or {}
            return (profiles.get(self.key, {}) or {}).get("enabled", True) is not False
        enabled = options.get("person_area_enabled", {}) or {}
        return enabled.get(self.key, True) is not False

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_enabled(False)

    async def _set_enabled(self, enabled: bool) -> None:
        options = dict(self.entry.options)
        current = {**self.entry.data, **self.entry.options}
        if self.kind == "person":
            profiles = {
                person: dict(profile)
                for person, profile in (current.get("person_profiles", {}) or {}).items()
            }
            if self.key not in profiles:
                return
            profiles[self.key]["enabled"] = enabled
            options["person_profiles"] = profiles
        else:
            area_enabled = dict(current.get("person_area_enabled", {}) or {})
            area_enabled[self.key] = enabled
            options["person_area_enabled"] = area_enabled
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self.async_write_ha_state()
