"""Announcement Hub integration."""

from __future__ import annotations

from typing import Any

import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HassJob,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_COMPANION_TTS,
    ATTR_INCLUDE_CURRENT,
    ATTR_JOB_ID,
    ATTR_LANGUAGE,
    ATTR_LEVEL,
    ATTR_NOTIFY_DATA,
    ATTR_OCCUPIED_ONLY,
    ATTR_OUTPUT,
    ATTR_SERVICE,
    ATTR_TEXT_NOTIFY,
    ATTR_TEXT_TTS,
    ATTR_TITLE,
    ATTR_TTS_OPTIONS,
    COMPANION_STREAM_DEFAULT,
    CONF_COMPANION_TTS_MEDIA_STREAM,
    CONF_COMPANION_TTS_OUTPUTS,
    CONF_COMPANION_TTS_WPM,
    CONF_NOTIFY_OUTPUTS,
    CONF_NOTIFY_POLICIES,
    CONF_NOTIFY_PROFILES,
    CONF_TTS_PLAYER_POLICIES,
    CONF_OUTPUT_AVAILABILITY_TIMEOUT,
    CONF_SNAPCAST_OUTPUTS,
    CONF_TTS_ENGINES,
    CONF_TTS_MIN_LEVEL,
    CONF_TTS_ROOM_PLAYERS,
    DEFAULT_COMPANION_TTS_WPM,
    DEFAULT_OCCUPIED_ONLY,
    DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT,
    DEFAULT_TTS_MIN_LEVEL,
    DOMAIN,
    LEGACY_CONF_ALLOWED_NOTIFY_ENTITIES,
    LEGACY_CONF_ALLOWED_NOTIFY_SERVICES,
    LEGACY_CONF_ALLOWED_TTS,
    LEGACY_CONF_DEFAULT_NOTIFY_ENTITIES,
    LEGACY_CONF_DEFAULT_NOTIFY_SERVICES,
    LEGACY_CONF_DEFAULT_TTS,
    LEGACY_CONF_SNAPCAST_CLIENTS,
    LEGACY_CONF_SNAPCAST_ENABLED,
    LEVEL_INFO,
    LEVELS,
    PLATFORMS,
    SERVICE_CANCEL,
    SERVICE_CLEAR_QUEUE,
    SERVICE_SEND,
    TARGET_ENTITY_PREFIX,
    TARGET_SERVICE_PREFIX,
)
from .manager import AnnouncementManager
from .outputs import area_name


def _validate_send_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Require at least one non-empty text field."""
    if not str(data.get(ATTR_TEXT_TTS, "")).strip() and not str(
        data.get(ATTR_TEXT_NOTIFY, "")
    ).strip():
        raise probatio.Invalid(
            "At least one of text_tts or text_notify is required"
        )
    return data


SEND_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Optional(ATTR_TEXT_TTS): cv.string,
            probatio.Optional(ATTR_TEXT_NOTIFY): cv.string,
            probatio.Optional(ATTR_OUTPUT): probatio.All(
                probatio.EnsureList(), [cv.string]
            ),
            probatio.Optional(ATTR_SERVICE): probatio.All(
                probatio.EnsureList(), [cv.string]
            ),
            probatio.Optional(ATTR_LEVEL, default=LEVEL_INFO): probatio.In(
                LEVELS
            ),
            probatio.Optional(ATTR_TITLE): cv.string,
            probatio.Optional(ATTR_NOTIFY_DATA): dict,
            probatio.Optional(ATTR_LANGUAGE): cv.string,
            probatio.Optional(ATTR_TTS_OPTIONS): dict,
            probatio.Optional(ATTR_COMPANION_TTS, default=False): bool,
            probatio.Optional(ATTR_OCCUPIED_ONLY, default=DEFAULT_OCCUPIED_ONLY): bool,
        }
    ),
    _validate_send_payload,
)

CLEAR_QUEUE_SCHEMA = probatio.Schema(
    {probatio.Optional(ATTR_INCLUDE_CURRENT, default=False): bool}
)
CANCEL_SCHEMA = probatio.Schema({probatio.Required(ATTR_JOB_ID): cv.string})


def _get_manager(hass: HomeAssistant) -> AnnouncementManager:
    manager = hass.data.get(DOMAIN, {}).get("manager")
    if not isinstance(manager, AnnouncementManager) or not manager.running:
        raise ServiceValidationError(
            "Announcement Hub is not configured or is not loaded"
        )
    return manager


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item) for item in value if str(item).strip()]


def _entity_refs(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return []
    result: list[str] = []
    for value in values:
        entity_id = str(value).strip()
        if not entity_id:
            continue
        result.append(
            entity_id
            if entity_id.startswith(TARGET_ENTITY_PREFIX)
            else f"{TARGET_ENTITY_PREFIX}{entity_id}"
        )
    return _unique(result)


def _service_refs(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return []
    result: list[str] = []
    for value in values:
        service = str(value).strip()
        if not service:
            continue
        result.append(
            service
            if service.startswith(TARGET_SERVICE_PREFIX)
            else f"{TARGET_SERVICE_PREFIX}{service}"
        )
    return _unique(result)


def _migrate_v1_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Convert the former allowed/default layout to output selections."""
    migrated = dict(settings)

    # All previously permitted outputs remain selected. The new model deliberately
    # has no second default subset: an omitted output uses every selected output.
    tts_entities = _unique(
        [
            *_strings(settings.get(LEGACY_CONF_ALLOWED_TTS)),
            *_strings(settings.get(LEGACY_CONF_DEFAULT_TTS)),
        ]
    )
    notify_entities = _unique(
        [
            *_strings(settings.get(LEGACY_CONF_ALLOWED_NOTIFY_ENTITIES)),
            *_strings(settings.get(LEGACY_CONF_DEFAULT_NOTIFY_ENTITIES)),
        ]
    )
    notify_services = _unique(
        [
            *_strings(settings.get(LEGACY_CONF_ALLOWED_NOTIFY_SERVICES)),
            *_strings(settings.get(LEGACY_CONF_DEFAULT_NOTIFY_SERVICES)),
        ]
    )
    snapcast_entities: list[str] = []
    if settings.get(LEGACY_CONF_SNAPCAST_ENABLED, False):
        snapcast_entities = _strings(
            settings.get(LEGACY_CONF_SNAPCAST_CLIENTS)
        )

    migrated[CONF_TTS_ENGINES] = _entity_refs(tts_entities)
    migrated[CONF_NOTIFY_OUTPUTS] = [
        *_entity_refs(notify_entities),
        *_service_refs(notify_services),
    ]
    migrated[CONF_SNAPCAST_OUTPUTS] = _entity_refs(snapcast_entities)
    migrated.setdefault(CONF_COMPANION_TTS_OUTPUTS, [])
    migrated.setdefault(CONF_TTS_ROOM_PLAYERS, [])
    migrated.setdefault(CONF_NOTIFY_POLICIES, {})
    migrated.setdefault(CONF_NOTIFY_PROFILES, {})
    migrated.setdefault(CONF_TTS_PLAYER_POLICIES, {})
    migrated.setdefault(CONF_TTS_MIN_LEVEL, DEFAULT_TTS_MIN_LEVEL)
    migrated.setdefault(
        CONF_OUTPUT_AVAILABILITY_TIMEOUT,
        DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT,
    )
    migrated.setdefault(
        CONF_COMPANION_TTS_MEDIA_STREAM, COMPANION_STREAM_DEFAULT
    )
    migrated.setdefault(CONF_COMPANION_TTS_WPM, DEFAULT_COMPANION_TTS_WPM)

    for key in (
        LEGACY_CONF_ALLOWED_TTS,
        LEGACY_CONF_DEFAULT_TTS,
        LEGACY_CONF_ALLOWED_NOTIFY_ENTITIES,
        LEGACY_CONF_DEFAULT_NOTIFY_ENTITIES,
        LEGACY_CONF_ALLOWED_NOTIFY_SERVICES,
        LEGACY_CONF_DEFAULT_NOTIFY_SERVICES,
        LEGACY_CONF_SNAPCAST_ENABLED,
        LEGACY_CONF_SNAPCAST_CLIENTS,
    ):
        migrated.pop(key, None)

    return migrated


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register integration-level actions."""
    hass.data.setdefault(DOMAIN, {})

    async def async_send(call: ServiceCall) -> ServiceResponse:
        manager = _get_manager(hass)
        job = await manager.async_enqueue(
            text_tts=call.data.get(ATTR_TEXT_TTS),
            text_notify=call.data.get(ATTR_TEXT_NOTIFY),
            outputs=call.data.get(ATTR_OUTPUT),
            requested_services=call.data.get(ATTR_SERVICE),
            level=call.data[ATTR_LEVEL],
            title=call.data.get(ATTR_TITLE),
            notify_data=call.data.get(ATTR_NOTIFY_DATA),
            language=call.data.get(ATTR_LANGUAGE),
            tts_options=call.data.get(ATTR_TTS_OPTIONS),
            companion_tts=call.data[ATTR_COMPANION_TTS],
            occupied_only=call.data[ATTR_OCCUPIED_ONLY],
        )
        pending = manager.pending_jobs()
        position = next(
            (
                index
                for index, queued in enumerate(pending, start=1)
                if queued.job_id == job.job_id
            ),
            0,
        )
        response: ServiceResponse = {
            "accepted": True,
            "job_id": job.job_id,
            "status": job.status,
            "queue_position": position,
            "queue_size": manager.queue_size,
            "outputs": [area_name(hass, area_id) for area_id in job.outputs],
            "output_area_ids": list(job.outputs),
            "tts_engines": list(job.tts_engines),
            "notify_outputs": list(job.notify_outputs),
            "room_tts_players": list(job.room_tts_players),
            "snapcast_clients": list(job.snapcast_clients),
            "companion_tts_entries": list(job.companion_tts_entries),
            "tts_suppressed_by_level": job.tts_suppressed_by_level,
        }
        return response if call.return_response else None

    async def async_clear_queue(call: ServiceCall) -> ServiceResponse:
        manager = _get_manager(hass)
        removed = await manager.async_clear_queue(
            include_current=call.data[ATTR_INCLUDE_CURRENT]
        )
        response: ServiceResponse = {
            "cleared": removed,
            "current_cancel_requested": bool(
                call.data[ATTR_INCLUDE_CURRENT] and manager.current_job
            ),
            "queue_size": manager.queue_size,
        }
        return response if call.return_response else None

    async def async_cancel(call: ServiceCall) -> ServiceResponse:
        manager = _get_manager(hass)
        status = await manager.async_cancel(call.data[ATTR_JOB_ID])
        response: ServiceResponse = {
            "job_id": call.data[ATTR_JOB_ID],
            "status": status,
            "queue_size": manager.queue_size,
        }
        return response if call.return_response else None

    if not hass.services.has_service(DOMAIN, SERVICE_SEND):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND,
            async_send,
            schema=SEND_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_QUEUE,
            async_clear_queue,
            schema=CLEAR_QUEUE_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_CANCEL,
            async_cancel,
            schema=CANCEL_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Migrate legacy provider settings and add v0.3 visual profiles."""
    if entry.version > 3:
        return False
    if entry.version < 3:
        effective = {**entry.data, **entry.options}
        migrated = (
            _migrate_v1_settings(effective)
            if entry.version < 2
            else dict(effective)
        )
        migrated.setdefault(CONF_NOTIFY_POLICIES, {})
        migrated.setdefault(CONF_NOTIFY_PROFILES, {})
        migrated.setdefault(CONF_TTS_PLAYER_POLICIES, {})
        hass.config_entries.async_update_entry(
            entry,
            data=migrated,
            options={},
            version=3,
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Announcement Hub from a config entry."""
    manager = AnnouncementManager(hass, entry)
    entry.runtime_data = manager
    hass.data.setdefault(DOMAIN, {})["manager"] = manager

    try:
        await manager.async_start()

        # Run graceful queue shutdown before Home Assistant cancels background
        # tasks. The returned remover is tied to config-entry unload so a normal
        # reload does not leave a stale global shutdown job behind.
        entry.async_on_unload(
            hass.async_add_shutdown_job(
                HassJob(manager.async_stop, f"{DOMAIN} shutdown")
            )
        )

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await manager.async_stop()
        if hass.data.get(DOMAIN, {}).get("manager") is manager:
            hass.data[DOMAIN].pop("manager", None)
        raise

    async def async_options_updated(
        hass: HomeAssistant, updated_entry: ConfigEntry
    ) -> None:
        await manager.async_update_config()

    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload Announcement Hub."""
    manager: AnnouncementManager = entry.runtime_data
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if not unload_ok:
        return False
    await manager.async_stop()
    if hass.data.get(DOMAIN, {}).get("manager") is manager:
        hass.data[DOMAIN].pop("manager", None)
    return True
