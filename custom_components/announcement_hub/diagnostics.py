"""Diagnostics for Announcement Hub."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CRITICAL_NOTIFY_DATA,
    CONF_NOTIFY_PROFILES,
    CONF_TTS_OPTIONS,
)
from .manager import AnnouncementManager

_TO_REDACT = {
    CONF_CRITICAL_NOTIFY_DATA,
    CONF_NOTIFY_PROFILES,
    CONF_TTS_OPTIONS,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return configuration and queue state without message text or private data."""
    manager: AnnouncementManager = entry.runtime_data
    return {
        "entry_data": async_redact_data(dict(entry.data), _TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), _TO_REDACT),
        "queue": manager.status_dict(),
    }
