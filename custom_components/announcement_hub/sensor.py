"""Queue status sensor for Announcement Hub."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SIGNAL_UPDATE
from .manager import AnnouncementManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the queue sensor."""
    async_add_entities([AnnouncementQueueSensor(entry.runtime_data, entry.entry_id)])


class AnnouncementQueueSensor(SensorEntity):
    """Expose queue length and current/last job diagnostics."""

    _attr_has_entity_name = True
    _attr_translation_key = "queue"
    _attr_icon = "mdi:message-processing-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "announcements"

    def __init__(self, manager: AnnouncementManager, entry_id: str) -> None:
        self._manager = manager
        self._attr_unique_id = f"{entry_id}_queue"

    @property
    def available(self) -> bool:
        return self._manager.running

    @property
    def native_value(self) -> int:
        return self._manager.queue_size

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._manager.status_dict()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE, self._async_handle_update
            )
        )

    @callback
    def _async_handle_update(self) -> None:
        self.async_write_ha_state()
