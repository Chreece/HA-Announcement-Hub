"""Output discovery, expansion, area mapping, and availability helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from homeassistant.components import tts
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import (
    TARGET_ENTITY_PREFIX,
    TARGET_ENTRY_PREFIX,
    TARGET_INTEGRATION_PREFIX,
    TARGET_SERVICE_PREFIX,
)

_NOTIFY_BASE_SERVICES = {
    "notify",
    "persistent_notification",
    "reload",
    "send_message",
}


@dataclass(frozen=True, slots=True)
class NotifyOutput:
    """One concrete visual notification output."""

    ref: str
    entity_id: str | None = None
    service: str | None = None
    integration: str | None = None
    config_entry_id: str | None = None
    area_id: str | None = None


@dataclass(frozen=True, slots=True)
class CompanionTTSOutput:
    """One concrete Companion App device used as an audible output."""

    entry_id: str
    entity_id: str | None
    area_id: str | None
    title: str


@dataclass(frozen=True, slots=True)
class SelectOption:
    """Dynamic select option shown by a config flow."""

    value: str
    label: str

    def as_dict(self) -> dict[str, str]:
        return {"value": self.value, "label": self.label}


def _entries(hass: HomeAssistant) -> list[Any]:
    return list(hass.config_entries.async_entries())


def _entry(hass: HomeAssistant, entry_id: str | None) -> Any | None:
    if not entry_id:
        return None
    return hass.config_entries.async_get_entry(entry_id)


def _registry_entries(hass: HomeAssistant) -> list[Any]:
    registry = er.async_get(hass)
    return list(registry.entities.values())


def _is_android_companion_entry(entry: Any) -> bool:
    """Return whether a mobile_app entry can use Android push TTS."""
    app_id = str(entry.data.get("app_id", "")).casefold()
    os_version = str(entry.data.get("os_version", "")).casefold()
    manufacturer = str(entry.data.get("manufacturer", "")).casefold()
    return (
        "android" in app_id
        or "android" in os_version
        or manufacturer in {"google", "samsung", "xiaomi", "oneplus", "amazon"}
    )


def _entity_domain(entity_id: str) -> str:
    return entity_id.partition(".")[0]


def _entity_config_entry_id(reg_entry: Any) -> str | None:
    return getattr(reg_entry, "config_entry_id", None)


def entity_integration(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the integration domain that owns an entity."""
    reg_entry = er.async_get(hass).async_get(entity_id)
    if reg_entry is None:
        return None
    if platform := getattr(reg_entry, "platform", None):
        return str(platform)
    if entry := _entry(hass, _entity_config_entry_id(reg_entry)):
        return str(entry.domain)
    return None


def entity_config_entry_id(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the config entry ID linked to an entity."""
    reg_entry = er.async_get(hass).async_get(entity_id)
    if reg_entry is None:
        return None
    return _entity_config_entry_id(reg_entry)


def entity_area_id(hass: HomeAssistant, entity_id: str) -> str | None:
    """Resolve an entity's own area or its device's area."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    reg_entry = entity_registry.async_get(entity_id)
    if reg_entry is None:
        return None
    if area_id := getattr(reg_entry, "area_id", None):
        return str(area_id)
    if device_id := getattr(reg_entry, "device_id", None):
        if device := device_registry.async_get(device_id):
            return device.area_id
    return None


def entry_area_id(hass: HomeAssistant, entry_id: str) -> str | None:
    """Resolve an entry area from the devices/entities that belong to it."""
    entity_registry = er.async_get(hass)
    areas = {
        entity_area_id(hass, item.entity_id)
        for item in entity_registry.entities.values()
        if _entity_config_entry_id(item) == entry_id
    }
    areas.discard(None)
    if len(areas) == 1:
        return next(iter(areas))

    device_registry = dr.async_get(hass)
    device_areas = {
        device.area_id
        for device in device_registry.devices.values()
        if entry_id in getattr(device, "config_entries", set())
        and device.area_id is not None
    }
    if len(device_areas) == 1:
        return next(iter(device_areas))
    return None


def area_name(hass: HomeAssistant, area_id: str | None) -> str:
    """Return a friendly area suffix."""
    if not area_id:
        return "Global / no area"
    if area := ar.async_get(hass).async_get_area(area_id):
        return area.name
    return area_id


def entity_device_name(hass: HomeAssistant, entity_id: str) -> str:
    """Return the device/config-entry name behind an entity."""
    reg_entry = er.async_get(hass).async_get(entity_id)
    if reg_entry is None:
        return "No device"
    if device_id := getattr(reg_entry, "device_id", None):
        if device := dr.async_get(hass).async_get(device_id):
            return str(
                getattr(device, "name_by_user", None)
                or getattr(device, "name", None)
                or entity_id
            )
    if entry := _entry(hass, _entity_config_entry_id(reg_entry)):
        return str(entry.title)
    return "No device"


def concrete_entity_options(
    hass: HomeAssistant,
    *,
    entity_domain: str,
    integration: str | None = None,
) -> list[SelectOption]:
    """Return only concrete supported entities with integration/device/entity labels."""
    options: list[SelectOption] = []
    for item in _enabled_registry_entries(
        hass, entity_domain=entity_domain, integration=integration
    ):
        entity_id = item.entity_id
        owner = _integration_for_registry_entry(hass, item) or "unknown"
        options.append(
            SelectOption(
                f"{TARGET_ENTITY_PREFIX}{entity_id}",
                f"{owner.replace('_', ' ').title()} · "
                f"{entity_device_name(hass, entity_id)} · "
                f"{entity_name(hass, entity_id)}",
            )
        )
    return sorted(options, key=lambda item: item.label.casefold())


def tts_engine_languages(
    hass: HomeAssistant,
    engine_ids: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Return languages advertised by concrete TTS entities."""
    component = hass.data.get(getattr(tts, "DATA_COMPONENT", "tts_entity_component"))
    wanted = set(engine_ids or ())
    languages: list[str] = []
    for item in _enabled_registry_entries(hass, entity_domain="tts"):
        entity_id = item.entity_id
        if wanted and entity_id not in wanted:
            continue
        entity = component.get_entity(entity_id) if component is not None else None
        if entity is None:
            continue
        with suppress(Exception):
            languages.extend(str(value) for value in (entity.supported_languages or []))
    return tuple(dict.fromkeys(languages))


def tts_default_language(
    hass: HomeAssistant,
    engine_ids: Sequence[str] | None = None,
) -> str | None:
    """Return a compatible preferred/default TTS language."""
    component = hass.data.get(getattr(tts, "DATA_COMPONENT", "tts_entity_component"))
    ids = tuple(engine_ids or ())
    default_engine = tts_default_engine(hass)
    ordered = (
        ((default_engine,) if default_engine else ())
        + tuple(entity_id for entity_id in ids if entity_id != default_engine)
    )
    for entity_id in ordered:
        if not entity_id:
            continue
        entity = component.get_entity(entity_id) if component is not None else None
        if entity is None:
            continue
        with suppress(Exception):
            language = str(entity.default_language or "")
            if language:
                return language
    available = tts_engine_languages(hass, ids)
    if hass.config.language in available:
        return str(hass.config.language)
    return available[0] if available else None


def tts_default_engine(hass: HomeAssistant) -> str | None:
    """Return Home Assistant's preferred/default concrete TTS entity."""
    try:
        engine = tts.async_default_engine(hass)
    except (KeyError, AttributeError):
        return None
    return str(engine) if engine and str(engine).startswith("tts.") else None


def tts_media_player_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return non-Snapcast media players capable of direct play-media TTS."""
    result: list[SelectOption] = []
    for item in _enabled_registry_entries(hass, entity_domain="media_player"):
        if _integration_for_registry_entry(hass, item) == "snapcast":
            continue
        state = hass.states.get(item.entity_id)
        if state is None:
            continue
        features = int(state.attributes.get("supported_features", 0) or 0)
        if not features & int(MediaPlayerEntityFeature.PLAY_MEDIA):
            continue
        owner = _integration_for_registry_entry(hass, item) or "unknown"
        result.append(
            SelectOption(
                item.entity_id,
                f"{owner.replace('_', ' ').title()} · "
                f"{entity_device_name(hass, item.entity_id)} · "
                f"{entity_name(hass, item.entity_id)} · "
                f"{area_name(hass, entity_area_id(hass, item.entity_id))}",
            )
        )
    return [item.as_dict() for item in sorted(result, key=lambda x: x.label.casefold())]


def entity_name(hass: HomeAssistant, entity_id: str) -> str:
    """Return a stable friendly entity label."""
    if state := hass.states.get(entity_id):
        if friendly := state.attributes.get("friendly_name"):
            return str(friendly)
    if reg_entry := er.async_get(hass).async_get(entity_id):
        return str(
            getattr(reg_entry, "name", None)
            or getattr(reg_entry, "original_name", None)
            or entity_id
        )
    return entity_id


def _integration_for_registry_entry(
    hass: HomeAssistant, reg_entry: Any
) -> str | None:
    if platform := getattr(reg_entry, "platform", None):
        return str(platform)
    if entry := _entry(hass, _entity_config_entry_id(reg_entry)):
        return str(entry.domain)
    return None


def _enabled_registry_entries(
    hass: HomeAssistant,
    *,
    entity_domain: str,
    integration: str | None = None,
) -> list[Any]:
    result: list[Any] = []
    for item in _registry_entries(hass):
        if _entity_domain(item.entity_id) != entity_domain:
            continue
        if getattr(item, "disabled_by", None) is not None:
            continue
        owner = _integration_for_registry_entry(hass, item)
        if integration is not None and owner != integration:
            continue
        result.append(item)
    return sorted(result, key=lambda item: item.entity_id)


def _options_for_entities(
    hass: HomeAssistant,
    *,
    entity_domain: str,
    integration: str | None = None,
    include_integrations: bool = True,
    include_entries: bool = True,
) -> list[SelectOption]:
    entities = _enabled_registry_entries(
        hass, entity_domain=entity_domain, integration=integration
    )
    options: dict[str, SelectOption] = {}

    if include_integrations:
        integrations = sorted(
            {
                owner
                for item in entities
                if (owner := _integration_for_registry_entry(hass, item))
            }
        )
        for owner in integrations:
            options[f"{TARGET_INTEGRATION_PREFIX}{owner}"] = SelectOption(
                f"{TARGET_INTEGRATION_PREFIX}{owner}",
                f"Integration · {owner.replace('_', ' ').title()} · all outputs",
            )

    if include_entries:
        entry_ids = sorted(
            {
                entry_id
                for item in entities
                if (entry_id := _entity_config_entry_id(item))
            }
        )
        for entry_id in entry_ids:
            entry = _entry(hass, entry_id)
            if entry is None:
                continue
            options[f"{TARGET_ENTRY_PREFIX}{entry_id}"] = SelectOption(
                f"{TARGET_ENTRY_PREFIX}{entry_id}",
                f"Entry · {entry.title} [{entry.domain}] · "
                f"{area_name(hass, entry_area_id(hass, entry_id))}",
            )

    for item in entities:
        entity_id = item.entity_id
        owner = _integration_for_registry_entry(hass, item) or "unknown"
        options[f"{TARGET_ENTITY_PREFIX}{entity_id}"] = SelectOption(
            f"{TARGET_ENTITY_PREFIX}{entity_id}",
            f"Entity · {entity_name(hass, entity_id)} [{owner}] · "
            f"{area_name(hass, entity_area_id(hass, entity_id))}",
        )

    return sorted(options.values(), key=lambda item: item.label.casefold())


def notify_output_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return concrete recognised notification entities only."""
    return [
        option.as_dict()
        for option in concrete_entity_options(hass, entity_domain="notify")
    ]



def snapcast_output_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return concrete Snapcast client entities only."""
    return [
        option.as_dict()
        for option in concrete_entity_options(
            hass,
            entity_domain="media_player",
            integration="snapcast",
        )
        if "group" not in option.value.casefold()
    ]



def companion_tts_output_options(
    hass: HomeAssistant,
) -> list[dict[str, str]]:
    """Return Android Companion App entry and notify-entity choices."""
    eligible_entries = {
        entry.entry_id: entry
        for entry in hass.config_entries.async_entries("mobile_app")
        if _is_android_companion_entry(entry)
    }
    options: dict[str, SelectOption] = {}
    notify_entities = _enabled_registry_entries(
        hass, entity_domain="notify", integration="mobile_app"
    )
    notify_entity_by_entry: dict[str, str] = {}
    for item in notify_entities:
        if entry_id := _entity_config_entry_id(item):
            notify_entity_by_entry.setdefault(entry_id, item.entity_id)

    if eligible_entries:
        value = f"{TARGET_INTEGRATION_PREFIX}mobile_app"
        options[value] = SelectOption(
            value, "Integration · Companion App (Android) · all TTS outputs"
        )

    for entry_id, entry in sorted(
        eligible_entries.items(), key=lambda item: item[1].title.casefold()
    ):
        value = f"{TARGET_ENTRY_PREFIX}{entry_id}"
        notify_entity = notify_entity_by_entry.get(entry_id)
        resolved_area = (
            entity_area_id(hass, notify_entity)
            if notify_entity
            else entry_area_id(hass, entry_id)
        )
        options[value] = SelectOption(
            value,
            f"Entry · {entry.title} [mobile_app] · "
            f"{area_name(hass, resolved_area)}",
        )

    for item in notify_entities:
        entry_id = _entity_config_entry_id(item)
        if entry_id not in eligible_entries:
            continue
        entity_id = item.entity_id
        value = f"{TARGET_ENTITY_PREFIX}{entity_id}"
        options[value] = SelectOption(
            value,
            f"Entity · {entity_name(hass, entity_id)} [mobile_app TTS] · "
            f"{area_name(hass, entity_area_id(hass, entity_id))}",
        )

    return [
        option.as_dict()
        for option in sorted(
            options.values(), key=lambda item: item.label.casefold()
        )
    ]


def tts_engine_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return concrete TTS engines with their advertised languages."""
    component = hass.data.get(getattr(tts, "DATA_COMPONENT", "tts_entity_component"))
    options: list[SelectOption] = []
    for item in _enabled_registry_entries(hass, entity_domain="tts"):
        entity_id = item.entity_id
        owner = _integration_for_registry_entry(hass, item) or "unknown"
        languages: list[str] = []
        default_language: str | None = None
        entity = component.get_entity(entity_id) if component is not None else None
        if entity is not None:
            with suppress(Exception):
                languages = list(entity.supported_languages or [])
            with suppress(Exception):
                default_language = str(entity.default_language or "") or None
        language_label = ""
        if languages:
            shown = [
                f"{lang}*" if lang == default_language else str(lang)
                for lang in languages
            ]
            language_label = " · " + ", ".join(shown)
        options.append(
            SelectOption(
                entity_id,
                f"{owner.replace('_', ' ').title()} · "
                f"{entity_name(hass, entity_id)}{language_label}",
            )
        )
    return [item.as_dict() for item in sorted(options, key=lambda x: x.label.casefold())]



def _expand_entity_tokens(
    hass: HomeAssistant,
    tokens: Sequence[str],
    *,
    entity_domain: str,
    integration: str | None = None,
) -> tuple[str, ...]:
    registry_entries = _enabled_registry_entries(
        hass, entity_domain=entity_domain, integration=integration
    )
    by_entry: dict[str, list[str]] = {}
    by_integration: dict[str, list[str]] = {}
    valid_entities: set[str] = set()
    for item in registry_entries:
        valid_entities.add(item.entity_id)
        if entry_id := _entity_config_entry_id(item):
            by_entry.setdefault(entry_id, []).append(item.entity_id)
        if owner := _integration_for_registry_entry(hass, item):
            by_integration.setdefault(owner, []).append(item.entity_id)

    result: list[str] = []
    for token in tokens:
        value = str(token).strip()
        if not value:
            continue
        if value.startswith(TARGET_ENTITY_PREFIX):
            entity_id = value.removeprefix(TARGET_ENTITY_PREFIX)
            if entity_id in valid_entities:
                result.append(entity_id)
            continue
        if value.startswith(TARGET_ENTRY_PREFIX):
            result.extend(
                by_entry.get(value.removeprefix(TARGET_ENTRY_PREFIX), [])
            )
            continue
        if value.startswith(TARGET_INTEGRATION_PREFIX):
            result.extend(
                by_integration.get(
                    value.removeprefix(TARGET_INTEGRATION_PREFIX), []
                )
            )
            continue
        if value in valid_entities:
            result.append(value)
    return tuple(dict.fromkeys(result))


def expand_tts_engine_tokens(
    hass: HomeAssistant, tokens: Sequence[str]
) -> tuple[str, ...]:
    return _expand_entity_tokens(hass, tokens, entity_domain="tts")


def expand_media_player_tokens(
    hass: HomeAssistant, tokens: Sequence[str]
) -> tuple[str, ...]:
    """Expand integration/entry/entity selectors to media-player entities."""
    return _expand_entity_tokens(hass, tokens, entity_domain="media_player")


def expand_snapcast_output_tokens(
    hass: HomeAssistant, tokens: Sequence[str]
) -> tuple[str, ...]:
    return tuple(
        entity_id
        for entity_id in _expand_entity_tokens(
            hass,
            tokens,
            entity_domain="media_player",
            integration="snapcast",
        )
        if "group" not in entity_id.casefold()
    )


def expand_notify_output_tokens(
    hass: HomeAssistant, tokens: Sequence[str]
) -> tuple[str, ...]:
    """Expand configured output selectors into canonical entity/service refs."""
    entity_tokens = [
        token
        for token in tokens
        if not str(token).startswith(TARGET_SERVICE_PREFIX)
    ]
    entities = _expand_entity_tokens(
        hass, entity_tokens, entity_domain="notify"
    )
    result = [f"{TARGET_ENTITY_PREFIX}{entity_id}" for entity_id in entities]
    for token in tokens:
        value = str(token).strip()
        if not value.startswith(TARGET_SERVICE_PREFIX):
            continue
        service = value.removeprefix(TARGET_SERVICE_PREFIX)
        if service.startswith("notify."):
            result.append(f"{TARGET_SERVICE_PREFIX}{service}")
    return tuple(dict.fromkeys(result))


def expand_companion_tts_tokens(
    hass: HomeAssistant, tokens: Sequence[str]
) -> tuple[str, ...]:
    """Expand Companion App selectors into concrete mobile_app entry IDs."""
    mobile_entries = {
        entry.entry_id: entry
        for entry in hass.config_entries.async_entries("mobile_app")
        if _is_android_companion_entry(entry)
    }
    entity_entries: dict[str, str] = {}
    for item in _enabled_registry_entries(
        hass, entity_domain="notify", integration="mobile_app"
    ):
        if entry_id := _entity_config_entry_id(item):
            entity_entries[item.entity_id] = entry_id

    result: list[str] = []
    for token in tokens:
        value = str(token).strip()
        if not value:
            continue
        if value == f"{TARGET_INTEGRATION_PREFIX}mobile_app":
            result.extend(sorted(mobile_entries))
            continue
        if value.startswith(TARGET_ENTRY_PREFIX):
            entry_id = value.removeprefix(TARGET_ENTRY_PREFIX)
            if entry_id in mobile_entries:
                result.append(entry_id)
            continue
        if value.startswith(TARGET_ENTITY_PREFIX):
            entity_id = value.removeprefix(TARGET_ENTITY_PREFIX)
            if entry_id := entity_entries.get(entity_id):
                result.append(entry_id)
            continue
        if value in mobile_entries:
            result.append(value)
        elif entry_id := entity_entries.get(value):
            result.append(entry_id)
    return tuple(dict.fromkeys(result))


def resolve_notify_outputs(
    hass: HomeAssistant, refs: Sequence[str]
) -> tuple[NotifyOutput, ...]:
    """Resolve canonical refs into concrete, area-aware visual outputs."""
    result: list[NotifyOutput] = []
    for ref in refs:
        if ref.startswith(TARGET_ENTITY_PREFIX):
            entity_id = ref.removeprefix(TARGET_ENTITY_PREFIX)
            if _entity_domain(entity_id) != "notify":
                continue
            result.append(
                NotifyOutput(
                    ref=ref,
                    entity_id=entity_id,
                    integration=entity_integration(hass, entity_id),
                    config_entry_id=entity_config_entry_id(hass, entity_id),
                    area_id=entity_area_id(hass, entity_id),
                )
            )
        elif ref.startswith(TARGET_SERVICE_PREFIX):
            service = ref.removeprefix(TARGET_SERVICE_PREFIX)
            if service.startswith("notify."):
                object_id = service.partition(".")[2]
                matching_entity = f"notify.{object_id}"
                integration = entity_integration(hass, matching_entity)
                config_entry_id = entity_config_entry_id(hass, matching_entity)
                resolved_area = entity_area_id(hass, matching_entity)

                # A legacy notify action and its modern NotifyEntity are not
                # guaranteed to have the same object ID. NFAndroidTV names its
                # legacy action from the config-entry title, so recover the
                # owning entry when a user selected the service directly.
                if config_entry_id is None:
                    for entry in _entries(hass):
                        if slugify(str(entry.title)) != object_id:
                            continue
                        if not (
                            entry.domain == "nfandroidtv"
                            or f"{entry.domain}.notify" in hass.config.components
                        ):
                            continue
                        integration = str(entry.domain)
                        config_entry_id = str(entry.entry_id)
                        resolved_area = entry_area_id(hass, entry.entry_id)
                        break

                result.append(
                    NotifyOutput(
                        ref=ref,
                        service=service,
                        integration=integration,
                        config_entry_id=config_entry_id,
                        area_id=resolved_area,
                    )
                )
    return tuple(result)


def resolve_companion_tts_outputs(
    hass: HomeAssistant, entry_ids: Sequence[str]
) -> tuple[CompanionTTSOutput, ...]:
    """Resolve mobile_app entry IDs into area-aware output records."""
    notify_entity_by_entry: dict[str, str] = {}
    for item in _enabled_registry_entries(
        hass, entity_domain="notify", integration="mobile_app"
    ):
        if entry_id := _entity_config_entry_id(item):
            notify_entity_by_entry.setdefault(entry_id, item.entity_id)

    result: list[CompanionTTSOutput] = []
    for entry_id in dict.fromkeys(entry_ids):
        entry = _entry(hass, entry_id)
        if (
            entry is None
            or entry.domain != "mobile_app"
            or not _is_android_companion_entry(entry)
        ):
            continue
        notify_entity = notify_entity_by_entry.get(entry_id)
        result.append(
            CompanionTTSOutput(
                entry_id=entry_id,
                entity_id=notify_entity,
                area_id=(
                    entity_area_id(hass, notify_entity)
                    if notify_entity
                    else entry_area_id(hass, entry_id)
                ),
                title=entry.title,
            )
        )
    return tuple(result)


def output_matches_areas(
    output_area_id: str | None, requested_areas: Sequence[str]
) -> bool:
    """Global outputs match every request; area-bound outputs are filtered."""
    return not requested_areas or output_area_id is None or output_area_id in set(
        requested_areas
    )


def notify_output_legacy_service(
    hass: HomeAssistant, output: NotifyOutput
) -> str | None:
    """Return the provider's advanced legacy notify action, when available.

    Modern ``notify.send_message`` accepts only message and title. Providers such
    as NFAndroidTV expose placement, duration, and styling through their legacy
    ``notify.<name>`` action. The entity object ID is not guaranteed to equal that
    service name, so also resolve it from the owning config-entry title—the exact
    name Home Assistant uses when registering NFAndroidTV's legacy action.
    """
    if output.service:
        return output.service

    if output.entity_id:
        object_id = output.entity_id.partition(".")[2]
        if object_id and hass.services.has_service("notify", object_id):
            return f"notify.{object_id}"

    if output.config_entry_id:
        entry = _entry(hass, output.config_entry_id)
        if entry is not None:
            service_name = slugify(str(entry.title))
            if service_name and hass.services.has_service("notify", service_name):
                return f"notify.{service_name}"

    return None


def notify_output_available(hass: HomeAssistant, output: NotifyOutput) -> bool:
    """Return whether a visual output can currently be attempted."""
    if output.entity_id:
        state = hass.states.get(output.entity_id)
        # NotifyEntity has an unknown state before its first message; that does
        # not mean the transport is unavailable.
        return state is not None and state.state != STATE_UNAVAILABLE
    if output.service:
        domain, separator, service = output.service.partition(".")
        return bool(
            separator
            and service
            and hass.services.has_service(domain, service)
        )
    return False


def snapcast_output_available(hass: HomeAssistant, entity_id: str) -> bool:
    """Return whether a selected Snapcast client is currently routable."""
    state = hass.states.get(entity_id)
    if state is None or state.state in {STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN}:
        return False
    return state.attributes.get("is_volume_muted") is not None


def tts_engine_available(hass: HomeAssistant, entity_id: str) -> bool:
    """Return whether a configured TTS engine can be attempted.

    Home Assistant TextToSpeechEntity deliberately has no meaningful state
    before its first generated utterance. Requiring a live state here creates a
    first-use deadlock: the scheduler refuses to run the job that would create
    that first state. Treat registration + loaded owning config entry as
    availability, while still respecting an explicitly unavailable state.
    """
    reg_entry = er.async_get(hass).async_get(entity_id)
    if reg_entry is None or getattr(reg_entry, "disabled_by", None) is not None:
        return False

    if entry_id := _entity_config_entry_id(reg_entry):
        entry = _entry(hass, entry_id)
        if entry is None:
            return False
        entry_state = getattr(getattr(entry, "state", None), "value", None)
        if entry_state is not None and entry_state != "loaded":
            return False

    state = hass.states.get(entity_id)
    return state is None or state.state != STATE_UNAVAILABLE


def companion_output_available(
    hass: HomeAssistant, output: CompanionTTSOutput
) -> bool:
    """Return whether a Companion App entry has a loaded push transport."""
    entry = _entry(hass, output.entry_id)
    if entry is None:
        return False
    state_value = getattr(getattr(entry, "state", None), "value", None)
    if state_value is not None and state_value != "loaded":
        return False
    if not hass.services.has_service("notify", "mobile_app"):
        return False
    if output.entity_id:
        state = hass.states.get(output.entity_id)
        if state is not None and state.state == STATE_UNAVAILABLE:
            return False
    return True


def mobile_app_webhook_id(hass: HomeAssistant, entry_id: str) -> str | None:
    entry = _entry(hass, entry_id)
    if entry is None or entry.domain != "mobile_app":
        return None
    value = entry.data.get("webhook_id")
    return str(value) if value else None


def unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))
