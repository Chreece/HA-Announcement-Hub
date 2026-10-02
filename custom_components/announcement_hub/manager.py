"""Persistent serialized announcement queue for Announcement Hub."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from collections import deque
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from copy import deepcopy
from functools import partial
import json
import logging
import math
import re
from typing import Any

from homeassistant.components import tts
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaType,
)
from homeassistant.components.tts.media_source import generate_media_source_id
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import (
    COMPANION_STREAM_DEFAULT,
    CONF_COMPANION_TTS_MEDIA_STREAM,
    CONF_COMPANION_TTS_OUTPUTS,
    CONF_COMPANION_TTS_WPM,
    CONF_CRITICAL_NOTIFY_DATA,
    CONF_DEFAULT_TITLE,
    CONF_DISPATCH_ORDER,
    CONF_FALLBACK_CHECK_DOOR,
    CONF_FALLBACK_ROOM,
    CONF_IDLE_TIMEOUT,
    CONF_NOTIFY_OUTPUTS,
    CONF_NOTIFY_PROFILES,
    CONF_OCCUPANCY_ATTRIBUTE,
    CONF_OCCUPANCY_SENSOR,
    CONF_OUTPUT_AVAILABILITY_TIMEOUT,
    CONF_PLAYBACK_TIMEOUT,
    CONF_POST_PLAY_DELAY,
    CONF_QUEUE_MAX,
    CONF_SNAPCAST_ONLY_SOURCE,
    CONF_SNAPCAST_OUTPUTS,
    CONF_SNAPCAST_RESTORE,
    CONF_SNAPCAST_SETTLE_DELAY,
    CONF_SNAPCAST_SOURCE,
    CONF_SNAPCAST_VERIFY_TIMEOUT,
    CONF_START_TIMEOUT,
    CONF_TTS_CACHE,
    CONF_TTS_ENGINES,
    CONF_TTS_LANGUAGE,
    CONF_TTS_MEDIA_PLAYER,
    CONF_TTS_MIN_LEVEL,
    CONF_TTS_OPTIONS,
    DEFAULT_COMPANION_TTS_MEDIA_STREAM,
    DEFAULT_COMPANION_TTS_WPM,
    DEFAULT_CRITICAL_NOTIFY_DATA,
    DEFAULT_DISPATCH_ORDER,
    DEFAULT_FALLBACK_CHECK_DOOR,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT,
    DEFAULT_PLAYBACK_TIMEOUT,
    DEFAULT_POST_PLAY_DELAY,
    DEFAULT_QUEUE_MAX,
    DEFAULT_SNAPCAST_ONLY_SOURCE,
    DEFAULT_SNAPCAST_RESTORE,
    DEFAULT_SNAPCAST_SETTLE_DELAY,
    DEFAULT_SNAPCAST_SOURCE,
    DEFAULT_SNAPCAST_VERIFY_TIMEOUT,
    DEFAULT_START_TIMEOUT,
    DEFAULT_TITLE,
    DEFAULT_TTS_CACHE,
    DEFAULT_TTS_LANGUAGE,
    DEFAULT_TTS_MIN_LEVEL,
    DEFAULT_TTS_OPTIONS,
    DISPATCH_NOTIFY_THEN_TTS,
    DOMAIN,
    EVENT_CANCELLED,
    EVENT_CHANNEL_FAILED,
    EVENT_CHANNEL_FINISHED,
    EVENT_CHANNEL_STARTED,
    EVENT_FAILED,
    EVENT_FINISHED,
    EVENT_QUEUE_CLEARED,
    EVENT_QUEUED,
    EVENT_STARTED,
    LEVEL_CRITICAL,
    INTEGRATION_MOBILE_APP,
    INTEGRATION_NFANDROIDTV,
    PROFILE_DEFAULT,
    PROFILE_DISPLAY_BUFFER,
    PROFILE_INTEGRATION_DATA,
    PROFILE_MAX_DISPLAY,
    PROFILE_MAX_LENGTH,
    PROFILE_MIN_DISPLAY,
    PROFILE_NF_COLOR,
    PROFILE_NF_FONTSIZE,
    PROFILE_NF_INTERRUPT,
    PROFILE_NF_POSITION,
    PROFILE_NF_TRANSPARENCY,
    PROFILE_PART_GAP,
    PROFILE_READING_WPM,
    PROFILE_REPLACE_PARTS,
    PROFILE_SHOW_PART_NUMBER,
    PROVIDER_ALL_ALIAS,
    PROVIDER_COMPANION_TTS_ALIAS,
    PROVIDER_NOTIFY_ALIAS,
    PROVIDER_SNAPCAST_ALIAS,
    PROVIDER_TTS_ALIAS,
    SIGNAL_UPDATE,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    TARGET_ENTITY_PREFIX,
    TARGET_ENTRY_PREFIX,
    TARGET_INTEGRATION_PREFIX,
    TARGET_SERVICE_PREFIX,
)
from .message_parts import (
    format_part_title,
    normalise_notify_profile,
    reading_seconds,
    resolve_notify_profile,
    split_message,
)
from .models import (
    AnnouncementJob,
    build_delivery_plan,
    tts_allowed_for_level,
    utcnow_iso,
)
from .outputs import (
    CompanionTTSOutput,
    NotifyOutput,
    companion_output_available,
    entity_area_id,
    expand_companion_tts_tokens,
    expand_notify_output_tokens,
    expand_snapcast_output_tokens,
    expand_tts_engine_tokens,
    mobile_app_webhook_id,
    notify_output_available,
    notify_output_legacy_service,
    output_matches_areas,
    resolve_companion_tts_outputs,
    resolve_notify_outputs,
    tts_engine_available,
)

_LOGGER = logging.getLogger(__name__)

_BUSY_STATES = {"playing", "buffering", "paused"}
_TERMINAL_JOB_STATES = {
    "completed",
    "completed_with_errors",
    "failed",
    "cancelled",
}


class JobCancelled(HomeAssistantError):
    """Raised internally when a queued or active job is cancelled."""


class AnnouncementManager:
    """Own the persistent FIFO queue and all output coordination."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}.{entry.entry_id}",
            private=True,
        )
        self._queue: deque[AnnouncementJob] = deque()
        self._current: AnnouncementJob | None = None
        self._last: AnnouncementJob | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._prefetch_tasks: dict[str, asyncio.Task[None]] = {}
        self._wake = asyncio.Event()
        self._running = False
        self._cancel_requested: set[str] = set()
        self._active_tts_player: str | None = None
        self._stop_lock = asyncio.Lock()

    @property
    def settings(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    @property
    def running(self) -> bool:
        return self._running

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def current_job(self) -> AnnouncementJob | None:
        return self._current

    @property
    def last_job(self) -> AnnouncementJob | None:
        return self._last

    def pending_jobs(self) -> list[AnnouncementJob]:
        return list(self._queue)

    def status_dict(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "queue_size": len(self._queue),
            "current": self._current.public_dict() if self._current else None,
            "pending": [job.public_dict() for job in list(self._queue)[:25]],
            "last": self._last.public_dict() if self._last else None,
            "prefetching": sorted(
                job_id
                for job_id, task in self._prefetch_tasks.items()
                if not task.done()
            ),
            "worker_alive": bool(
                self._worker_task is not None and not self._worker_task.done()
            ),
        }

    async def async_start(self) -> None:
        if self._running:
            return
        stored = await self._store.async_load() or {}
        current_snapcast = expand_snapcast_output_tokens(
            self.hass,
            self._ensure_list(self.settings.get(CONF_SNAPCAST_OUTPUTS, [])),
        )
        for raw_job in stored.get("jobs", []):
            legacy_job = "snapcast_clients" not in raw_job
            try:
                job = AnnouncementJob.from_dict(raw_job)
            except (TypeError, ValueError, KeyError) as err:
                _LOGGER.warning("Discarding invalid stored announcement: %s", err)
                continue
            if job.status in _TERMINAL_JOB_STATES:
                continue
            if legacy_job and job.server_tts_enabled and not job.snapcast_clients:
                job.snapcast_clients = current_snapcast
            if job.server_tts_enabled and not job.tts_media_player:
                player_value = self.settings.get(CONF_TTS_MEDIA_PLAYER)
                job.tts_media_player = (
                    str(player_value) if player_value else None
                )
                if job.tts_media_player:
                    job.tts_player_area = entity_area_id(
                        self.hass, job.tts_media_player
                    )
            resolved_notify_outputs = resolve_notify_outputs(
                self.hass, job.notify_outputs
            )
            if not job.notify_output_areas:
                job.notify_output_areas = {
                    output.ref: output.area_id
                    for output in resolved_notify_outputs
                }
            if not job.notify_output_profiles:
                configured_profiles = self.settings.get(CONF_NOTIFY_PROFILES, {})
                if not isinstance(configured_profiles, Mapping):
                    configured_profiles = {}
                job.notify_output_profiles = {
                    output.ref: resolve_notify_profile(
                        configured_profiles, output.integration
                    )
                    for output in resolved_notify_outputs
                }
            if not job.snapcast_client_areas:
                job.snapcast_client_areas = {
                    entity_id: entity_area_id(self.hass, entity_id)
                    for entity_id in job.snapcast_clients
                }
            if not job.companion_tts_entry_areas:
                job.companion_tts_entry_areas = {
                    output.entry_id: output.area_id
                    for output in resolve_companion_tts_outputs(
                        self.hass, job.companion_tts_entries
                    )
                }
            job.status = "pending"
            job.started_at = None
            job.finished_at = None
            job.error = None
            self._queue.append(job)
        if raw_last := stored.get("last"):
            with suppress(TypeError, ValueError, KeyError):
                self._last = AnnouncementJob.from_dict(raw_last)

        self._running = True
        self._ensure_worker()
        for job in self._queue:
            self._schedule_prefetch(job)
        if self._queue:
            self._wake.set()
        self._notify_update()

    def _ensure_worker(self) -> None:
        """Ensure exactly one live queue worker exists while the manager runs."""
        if not self._running:
            return
        if self._worker_task is not None and not self._worker_task.done():
            return

        task = self.entry.async_create_background_task(
            self.hass,
            self._async_worker(),
            f"{DOMAIN} worker",
        )
        self._worker_task = task

        def _worker_done(done_task: asyncio.Task[None]) -> None:
            if self._worker_task is done_task:
                self._worker_task = None
            if done_task.cancelled():
                return
            error = done_task.exception()
            if error is not None:
                _LOGGER.error(
                    "Announcement Hub queue worker stopped unexpectedly",
                    exc_info=(type(error), error, error.__traceback__),
                )
            if self._running:
                # A permanent worker must never leave accepted jobs stranded.
                # Restart on the next loop turn so an unexpected worker failure
                # cannot recurse synchronously.
                self.hass.loop.call_soon(self._ensure_worker)
                if self._queue:
                    self._wake.set()
            self._notify_update()

        task.add_done_callback(_worker_done)

    async def async_stop(self) -> None:
        """Stop all integration-owned tasks and persist the queue exactly once."""
        async with self._stop_lock:
            if (
                not self._running
                and self._worker_task is None
                and not self._prefetch_tasks
            ):
                return

            self._running = False
            self._wake.set()

            # The permanent queue worker is a config-entry background task so it
            # never participates in Home Assistant's startup barrier. We still
            # explicitly cancel and await it here for deterministic unload and
            # shutdown ordering.
            worker_task = self._worker_task
            self._worker_task = None
            if worker_task is not None:
                worker_task.cancel()
                with suppress(asyncio.CancelledError):
                    await worker_task

            # Prefetch operations are also entry-owned background tasks. Cancel
            # and await every one before the queue snapshot is written.
            prefetch_tasks = tuple(self._prefetch_tasks.values())
            self._prefetch_tasks.clear()
            for task in prefetch_tasks:
                task.cancel()
            if prefetch_tasks:
                await asyncio.gather(*prefetch_tasks, return_exceptions=True)

            if self._active_tts_player:
                await self._async_stop_player(self._active_tts_player)
            self._active_tts_player = None

            if self._current and self._current.status == "processing":
                self._current.status = "pending"
                self._current.started_at = None
                self._queue.appendleft(self._current)
                self._current = None

            await self._store.async_save(self._serialize())
            self._notify_update()

    async def async_update_config(self) -> None:
        # Options changes must not leave a dead worker behind. This is cheap
        # when the worker is healthy and self-heals a previously stopped task.
        self._ensure_worker()
        if self._queue:
            self._wake.set()
        self._notify_update()

    def _configured_outputs(
        self,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        return (
            expand_tts_engine_tokens(
                self.hass,
                self._ensure_list(self.settings.get(CONF_TTS_ENGINES, [])),
            ),
            expand_notify_output_tokens(
                self.hass,
                self._ensure_list(self.settings.get(CONF_NOTIFY_OUTPUTS, [])),
            ),
            expand_snapcast_output_tokens(
                self.hass,
                self._ensure_list(self.settings.get(CONF_SNAPCAST_OUTPUTS, [])),
            ),
            expand_companion_tts_tokens(
                self.hass,
                self._ensure_list(
                    self.settings.get(CONF_COMPANION_TTS_OUTPUTS, [])
                ),
            ),
        )

    def _select_requested_outputs(
        self,
        requested: Sequence[str],
        *,
        level: str,
        tts_engines: Sequence[str],
        notify_outputs: Sequence[str],
        snapcast_clients: Sequence[str],
        companion_entries: Sequence[str],
        companion_tts: bool,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        """Resolve optional per-call provider/output restrictions."""
        if level == LEVEL_CRITICAL:
            return (
                tuple(tts_engines),
                tuple(notify_outputs),
                tuple(snapcast_clients),
                tuple(companion_entries),
            )
        if not requested:
            return (
                tuple(tts_engines),
                tuple(notify_outputs),
                tuple(snapcast_clients),
                tuple(companion_entries) if companion_tts else (),
            )

        configured_tts = set(tts_engines)
        configured_notify = set(notify_outputs)
        configured_snapcast = set(snapcast_clients)
        configured_companion = set(companion_entries)
        selected_tts: list[str] = []
        selected_notify: list[str] = []
        selected_snapcast: list[str] = []
        selected_companion: list[str] = []
        invalid: list[str] = []

        def select_server_tts() -> None:
            selected_tts.extend(tts_engines)
            selected_snapcast.extend(snapcast_clients)

        for raw in requested:
            token = str(raw).strip()
            if not token:
                continue
            if token == PROVIDER_ALL_ALIAS:
                select_server_tts()
                selected_notify.extend(notify_outputs)
                selected_companion.extend(companion_entries)
                continue
            if token == PROVIDER_TTS_ALIAS:
                select_server_tts()
                continue
            if token == PROVIDER_NOTIFY_ALIAS:
                selected_notify.extend(notify_outputs)
                continue
            if token == PROVIDER_SNAPCAST_ALIAS:
                selected_tts.extend(tts_engines)
                selected_snapcast.extend(snapcast_clients)
                continue
            if token == PROVIDER_COMPANION_TTS_ALIAS:
                selected_companion.extend(companion_entries)
                continue

            matched = False
            raw_entity = token.removeprefix(TARGET_ENTITY_PREFIX)
            raw_entry = token.removeprefix(TARGET_ENTRY_PREFIX)
            canonical_service = (
                token
                if token.startswith(TARGET_SERVICE_PREFIX)
                else f"{TARGET_SERVICE_PREFIX}{token}"
            )
            canonical_entity = (
                token
                if token.startswith(TARGET_ENTITY_PREFIX)
                else f"{TARGET_ENTITY_PREFIX}{token}"
            )

            if raw_entity in configured_tts:
                selected_tts.append(raw_entity)
                matched = True
            if canonical_entity in configured_notify:
                selected_notify.append(canonical_entity)
                matched = True
            if canonical_service in configured_notify:
                selected_notify.append(canonical_service)
                matched = True
            if raw_entity in configured_snapcast:
                selected_snapcast.append(raw_entity)
                selected_tts.extend(tts_engines)
                matched = True
            if raw_entry in configured_companion and companion_tts:
                selected_companion.append(raw_entry)
                matched = True

            selector_token = token
            if (
                not token.startswith(
                    (
                        TARGET_INTEGRATION_PREFIX,
                        TARGET_ENTRY_PREFIX,
                        TARGET_ENTITY_PREFIX,
                        TARGET_SERVICE_PREFIX,
                    )
                )
                and "." not in token
            ):
                selector_token = f"{TARGET_INTEGRATION_PREFIX}{token}"

            expanded_tts = set(
                expand_tts_engine_tokens(self.hass, [selector_token])
            ) & configured_tts
            expanded_notify = set(
                expand_notify_output_tokens(self.hass, [selector_token])
            ) & configured_notify
            expanded_snapcast = set(
                expand_snapcast_output_tokens(self.hass, [selector_token])
            ) & configured_snapcast
            expanded_companion = set(
                expand_companion_tts_tokens(self.hass, [selector_token])
            ) & configured_companion
            if expanded_tts:
                selected_tts.extend(sorted(expanded_tts))
                matched = True
            if expanded_notify:
                selected_notify.extend(sorted(expanded_notify))
                matched = True
            if expanded_snapcast:
                selected_snapcast.extend(sorted(expanded_snapcast))
                selected_tts.extend(tts_engines)
                matched = True
            # A Mobile App integration/entry/entity token may also identify a
            # configured Companion TTS device, but the separate action opt-in
            # remains authoritative. Without it, the token selects only its
            # normal visual output.
            if expanded_companion and companion_tts:
                selected_companion.extend(sorted(expanded_companion))
                matched = True

            if not matched:
                invalid.append(token)

        if invalid:
            raise ServiceValidationError(
                "These requested services/outputs are not configured: "
                + ", ".join(invalid)
            )

        # The explicit boolean is an opt-in convenience in addition to the
        # service selector. Critical jobs already returned above with every
        # configured Companion App TTS output.
        if companion_tts:
            selected_companion.extend(companion_entries)

        # Selecting a server TTS engine chooses the voice/provider, not a room.
        # Preserve the configured Snapcast physical outputs unless the call also
        # narrowed them to one or more concrete clients/entries.
        if selected_tts and not selected_snapcast:
            selected_snapcast.extend(snapcast_clients)

        return (
            tuple(dict.fromkeys(selected_tts)),
            tuple(dict.fromkeys(selected_notify)),
            tuple(dict.fromkeys(selected_snapcast)),
            tuple(dict.fromkeys(selected_companion)),
        )

    async def async_enqueue(
        self,
        *,
        text_tts: str | None,
        text_notify: str | None,
        outputs: Sequence[str] | str | None,
        requested_services: Sequence[str] | str | None,
        level: str,
        title: str | None,
        notify_data: Mapping[str, Any] | None,
        language: str | None,
        tts_options: Mapping[str, Any] | None,
        companion_tts: bool,
        occupied_only: bool,
    ) -> AnnouncementJob:
        text_tts = text_tts.strip() if text_tts and text_tts.strip() else None
        text_notify = (
            text_notify.strip() if text_notify and text_notify.strip() else None
        )
        if not text_tts and not text_notify:
            raise ServiceValidationError(
                "At least one of text_tts or text_notify must contain text"
            )

        queue_max = int(self.settings.get(CONF_QUEUE_MAX, DEFAULT_QUEUE_MAX))
        if len(self._queue) + (1 if self._current else 0) >= queue_max:
            raise ServiceValidationError(
                f"Announcement queue is full ({queue_max} items)"
            )

        requested_output_area_ids = self._resolve_area_ids(
            self._ensure_list(outputs)
        )
        occupied_area_ids = self._occupied_area_ids() if occupied_only else None
        occupancy_filter_active = occupied_area_ids is not None
        if occupancy_filter_active:
            occupied_set = set(occupied_area_ids)
            output_area_ids = (
                tuple(
                    area_id
                    for area_id in requested_output_area_ids
                    if area_id in occupied_set
                )
                if requested_output_area_ids
                else occupied_area_ids
            )
        else:
            output_area_ids = requested_output_area_ids

        requested = self._ensure_list(requested_services)
        configured = self._configured_outputs()
        selected = self._select_requested_outputs(
            requested,
            level=level,
            tts_engines=configured[0],
            notify_outputs=configured[1],
            snapcast_clients=configured[2],
            companion_entries=configured[3],
            companion_tts=bool(companion_tts),
        )
        minimum_tts_level = str(
            self.settings.get(CONF_TTS_MIN_LEVEL, DEFAULT_TTS_MIN_LEVEL)
        )
        if (
            not tts_allowed_for_level(level, minimum_tts_level)
            and not selected[1]
            and configured[1]
        ):
            # A caller may explicitly request an audible path, but the configured
            # level policy wins. Fall back to the configured visual outputs rather
            # than rejecting or silently dropping the announcement.
            selected = (selected[0], configured[1], selected[2], selected[3])

        player_value = self.settings.get(CONF_TTS_MEDIA_PLAYER)
        player = str(player_value) if player_value else None
        base_selected = selected
        all_notify_records = resolve_notify_outputs(self.hass, base_selected[1])
        all_companion_records = resolve_companion_tts_outputs(
            self.hass, base_selected[3]
        )

        def routed_plan(
            area_ids: tuple[str, ...],
            *,
            filter_by_area: bool,
        ) -> tuple[
            tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]],
            tuple[NotifyOutput, ...],
            tuple[CompanionTTSOutput, ...],
            Any,
        ]:
            if filter_by_area:
                effective_areas = set(area_ids)
                routed_notify = tuple(
                    output
                    for output in all_notify_records
                    if output.area_id is not None
                    and output.area_id in effective_areas
                )
                routed_snapcast = tuple(
                    entity_id
                    for entity_id in base_selected[2]
                    if (
                        area_id := entity_area_id(self.hass, entity_id)
                    ) is not None
                    and area_id in effective_areas
                )
                routed_companion = tuple(
                    output
                    for output in all_companion_records
                    if output.area_id is not None
                    and output.area_id in effective_areas
                )
                routed_selected = (
                    base_selected[0],
                    tuple(output.ref for output in routed_notify),
                    routed_snapcast,
                    tuple(output.entry_id for output in routed_companion),
                )
            else:
                routed_notify = all_notify_records
                routed_companion = all_companion_records
                routed_selected = base_selected

            server_tts_enabled = bool(player and routed_selected[0])
            if filter_by_area and server_tts_enabled:
                if configured[2]:
                    server_tts_enabled = bool(routed_selected[2])
                else:
                    player_area = (
                        entity_area_id(self.hass, player) if player else None
                    )
                    server_tts_enabled = (
                        player_area is not None
                        and player_area in set(area_ids)
                    )

            route_plan = build_delivery_plan(
                text_tts=text_tts,
                text_notify=text_notify,
                level=level,
                minimum_tts_level=minimum_tts_level,
                tts_engines=routed_selected[0],
                notify_outputs=routed_selected[1],
                snapcast_clients=routed_selected[2],
                companion_tts_entries=routed_selected[3],
                server_tts_enabled=server_tts_enabled,
            )
            return (
                routed_selected,
                routed_notify,
                routed_companion,
                route_plan,
            )

        selected, notify_records, companion_records, plan = routed_plan(
            output_area_ids,
            filter_by_area=occupancy_filter_active,
        )

        if occupancy_filter_active and not plan.has_output:
            fallback_area_id = self._fallback_area_id()
            if (
                fallback_area_id
                and self._fallback_door_allows(output_area_ids)
            ):
                (
                    fallback_selected,
                    fallback_notify_records,
                    fallback_companion_records,
                    fallback_plan,
                ) = routed_plan((fallback_area_id,), filter_by_area=True)
                if fallback_plan.has_output:
                    output_area_ids = (fallback_area_id,)
                    selected = fallback_selected
                    notify_records = fallback_notify_records
                    companion_records = fallback_companion_records
                    plan = fallback_plan
                    _LOGGER.debug(
                        "Announcement routed to fallback area %s because the "
                        "occupied area(s) had no candidates",
                        fallback_area_id,
                    )

        notify_output_areas = {
            output.ref: output.area_id for output in notify_records
        }
        configured_profiles = self.settings.get(CONF_NOTIFY_PROFILES, {})
        if not isinstance(configured_profiles, Mapping):
            configured_profiles = {}
        notify_output_profiles = {
            output.ref: resolve_notify_profile(
                configured_profiles, output.integration
            )
            for output in notify_records
        }
        snapcast_client_areas = {
            entity_id: entity_area_id(self.hass, entity_id)
            for entity_id in selected[2]
        }
        companion_tts_entry_areas = {
            output.entry_id: output.area_id for output in companion_records
        }

        if not plan.has_output and not occupancy_filter_active:
            if plan.tts_suppressed_by_level:
                raise ServiceValidationError(
                    "TTS is muted for this level and no selected visual output "
                    "can receive the announcement"
                )
            raise ServiceValidationError(
                "The selected text has no configured matching output"
            )

        effective_title = (
            title
            if title is not None
            else self.settings.get(CONF_DEFAULT_TITLE, DEFAULT_TITLE)
        )
        effective_notify_data = dict(notify_data or {})
        if level == LEVEL_CRITICAL:
            effective_notify_data = self._deep_merge(
                dict(
                    self.settings.get(
                        CONF_CRITICAL_NOTIFY_DATA,
                        DEFAULT_CRITICAL_NOTIFY_DATA,
                    )
                    or {}
                ),
                effective_notify_data,
            )
        effective_language = (
            language
            or self.settings.get(CONF_TTS_LANGUAGE, DEFAULT_TTS_LANGUAGE)
            or None
        )
        effective_tts_options = {
            **dict(self.settings.get(CONF_TTS_OPTIONS, DEFAULT_TTS_OPTIONS) or {}),
            **dict(tts_options or {}),
        }

        job = AnnouncementJob.create(
            text_tts=text_tts,
            text_notify=text_notify,
            outputs=output_area_ids,
            requested_services=requested,
            level=level,
            title=effective_title,
            notify_data=effective_notify_data,
            language=effective_language,
            tts_options=effective_tts_options,
            tts_cache=bool(self.settings.get(CONF_TTS_CACHE, DEFAULT_TTS_CACHE)),
            plan=plan,
            tts_media_player=player,
            tts_player_area=(
                entity_area_id(self.hass, player) if player else None
            ),
            notify_output_areas=notify_output_areas,
            notify_output_profiles=notify_output_profiles,
            snapcast_client_areas=snapcast_client_areas,
            companion_tts_entry_areas=companion_tts_entry_areas,
            companion_tts_media_stream=str(
                self.settings.get(
                    CONF_COMPANION_TTS_MEDIA_STREAM,
                    DEFAULT_COMPANION_TTS_MEDIA_STREAM,
                )
            ),
            companion_tts_words_per_minute=float(
                self.settings.get(
                    CONF_COMPANION_TTS_WPM, DEFAULT_COMPANION_TTS_WPM
                )
            ),
        )
        self._queue.append(job)
        self._schedule_prefetch(job)
        self._schedule_save()
        self._ensure_worker()
        self._wake.set()
        self._fire_event(EVENT_QUEUED, job)
        self._notify_update()
        return job

    async def async_clear_queue(self, *, include_current: bool = False) -> int:
        removed = 0
        while self._queue:
            job = self._queue.popleft()
            removed += 1
            job.status = "cancelled"
            job.finished_at = utcnow_iso()
            task = self._prefetch_tasks.pop(job.job_id, None)
            if task:
                task.cancel()
            self._fire_event(EVENT_CANCELLED, job)
        if include_current and self._current:
            await self.async_cancel(self._current.job_id)
        self._schedule_save()
        self.hass.bus.async_fire(
            EVENT_QUEUE_CLEARED,
            {"removed": removed, "include_current": include_current},
        )
        self._notify_update()
        return removed

    async def async_cancel(self, job_id: str) -> str:
        if self._current and self._current.job_id == job_id:
            self._cancel_requested.add(job_id)
            if self._active_tts_player:
                await self._async_stop_player(self._active_tts_player)
            self._notify_update()
            return "cancelling"

        for job in tuple(self._queue):
            if job.job_id != job_id:
                continue
            self._queue.remove(job)
            job.status = "cancelled"
            job.finished_at = utcnow_iso()
            task = self._prefetch_tasks.pop(job.job_id, None)
            if task:
                task.cancel()
            self._last = job
            self._fire_event(EVENT_CANCELLED, job)
            self._schedule_save()
            self._notify_update()
            return "cancelled"
        raise ServiceValidationError(f"Unknown active or pending job_id: {job_id}")

    async def _async_worker(self) -> None:
        while self._running:
            job = self._next_runnable_job()
            if job is None:
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=0.25)
                except TimeoutError:
                    pass
                continue

            self._queue.remove(job)
            self._current = job
            job.status = "processing"
            job.started_at = utcnow_iso()
            job.error = None
            job.channel_errors.clear()
            job.successful_channels.clear()
            self._schedule_save()
            self._fire_event(EVENT_STARTED, job)
            self._notify_update()

            terminal_event: str | None = None
            requeued = False
            try:
                self._raise_if_cancelled(job)
                await self._async_process_job(job)
            except JobCancelled:
                job.status = "cancelled"
                terminal_event = EVENT_CANCELLED
            except asyncio.CancelledError:
                if not self._running:
                    job.status = "pending"
                    job.started_at = None
                    job.finished_at = None
                    self._queue.appendleft(job)
                    requeued = True
                    raise
                job.status = "cancelled"
                terminal_event = EVENT_CANCELLED
            except Exception as err:  # noqa: BLE001
                job.status = "failed"
                job.error = str(err)
                terminal_event = EVENT_FAILED
                _LOGGER.exception("Announcement %s failed", job.job_id)
            else:
                job.status = (
                    "completed_with_errors" if job.channel_errors else "completed"
                )
                if job.channel_errors:
                    job.error = "; ".join(
                        f"{channel}: {error}"
                        for channel, error in job.channel_errors.items()
                    )
                terminal_event = EVENT_FINISHED
            finally:
                self._cancel_requested.discard(job.job_id)
                self._current = None
                self._active_tts_player = None
                if not requeued:
                    job.finished_at = utcnow_iso()
                    self._prefetch_tasks.pop(job.job_id, None)
                    self._last = job
                    if terminal_event is not None:
                        self._fire_event(terminal_event, job)
                self._schedule_save()
                self._notify_update()

    def _pending_age_seconds(self, job: AnnouncementJob) -> float:
        """Return how long a pending job has been waiting."""
        try:
            created = datetime.fromisoformat(job.created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            return max(0.0, (datetime.now(UTC) - created).total_seconds())
        except (TypeError, ValueError):
            return 0.0

    def _job_has_ready_visual_output(self, job: AnnouncementJob) -> bool:
        if not job.notify_text or not job.notify_outputs:
            return False
        return any(
            notify_output_available(self.hass, output)
            for output in resolve_notify_outputs(self.hass, job.notify_outputs)
            if output_matches_areas(
                job.notify_output_areas.get(output.ref, output.area_id),
                job.outputs,
            )
        )

    def _job_has_ready_companion_tts(self, job: AnnouncementJob) -> bool:
        if not job.tts_text or not job.companion_tts_entries:
            return False
        return any(
            companion_output_available(self.hass, output)
            for output in resolve_companion_tts_outputs(
                self.hass, job.companion_tts_entries
            )
            if output_matches_areas(
                job.companion_tts_entry_areas.get(
                    output.entry_id, output.area_id
                ),
                job.outputs,
            )
        )

    def _job_has_ready_server_tts(self, job: AnnouncementJob) -> bool:
        """Check global TTS infrastructure plus area-bound physical outputs.

        TTS engines and the shared TTS media player are global infrastructure;
        only Snapcast clients are room outputs and participate in area routing.
        """
        if (
            not job.tts_text
            or not job.server_tts_enabled
            or not job.tts_engines
            or not job.tts_media_player
        ):
            return False
        player = self.hass.states.get(job.tts_media_player)
        if player is None or player.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            return False
        if not any(
            tts_engine_available(self.hass, engine)
            for engine in job.tts_engines
        ):
            return False
        if not job.snapcast_clients:
            return True
        return any(
            self._snapcast_output_available(entity_id)
            for entity_id in job.snapcast_clients
            if not job.outputs
            or job.snapcast_client_areas.get(
                entity_id, entity_area_id(self.hass, entity_id)
            )
            in set(job.outputs)
        )

    def _job_runnable_now(self, job: AnnouncementJob) -> bool:
        """Return whether at least one frozen delivery channel can run now."""
        return (
            self._job_has_ready_visual_output(job)
            or self._job_has_ready_server_tts(job)
            or self._job_has_ready_companion_tts(job)
        )

    def _expire_waiting_job(self, job: AnnouncementJob) -> None:
        """Finish a never-runnable pending job silently after its wait window."""
        if job not in self._queue:
            return
        self._queue.remove(job)
        job.status = "completed"
        job.finished_at = utcnow_iso()
        job.error = None
        self._prefetch_tasks.pop(job.job_id, None)
        self._last = job
        self._fire_event(EVENT_FINISHED, job)
        _LOGGER.debug(
            "Announcement %s expired after waiting %ss for a runnable output",
            job.job_id,
            f"{self._availability_timeout:g}",
        )
        self._schedule_save()
        self._notify_update()

    def _next_runnable_job(self) -> AnnouncementJob | None:
        """Pick the oldest runnable job without letting waiters block the queue."""
        timeout = self._availability_timeout
        for job in tuple(self._queue):
            if self._job_runnable_now(job):
                return job
            if timeout <= 0 or self._pending_age_seconds(job) >= timeout:
                self._expire_waiting_job(job)
        return None

    async def _async_process_job(self, job: AnnouncementJob) -> None:
        order = self.settings.get(CONF_DISPATCH_ORDER, DEFAULT_DISPATCH_ORDER)
        if order == DISPATCH_NOTIFY_THEN_TTS:
            await self._async_send_notifications(job)
            await self._async_send_tts(job)
        else:
            await self._async_send_tts(job)
            await self._async_send_notifications(job)

        self._raise_if_cancelled(job)
        # A job whose configured outputs all stayed unavailable is a valid
        # no-op after the availability window. Only actual recorded channel
        # errors can turn a no-delivery job into a failure.
        if not job.successful_channels and job.channel_errors:
            detail = "; ".join(
                f"{channel}: {error}"
                for channel, error in job.channel_errors.items()
            )
            raise HomeAssistantError(
                "No configured delivery channel succeeded"
                + (f": {detail}" if detail else "")
            )

    @property
    def _availability_timeout(self) -> float:
        return float(
            self.settings.get(
                CONF_OUTPUT_AVAILABILITY_TIMEOUT,
                DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT,
            )
        )

    async def _async_send_notifications(self, job: AnnouncementJob) -> None:
        if not job.notify_text or not job.notify_outputs:
            return
        outputs = [
            output
            for output in resolve_notify_outputs(self.hass, job.notify_outputs)
            if output_matches_areas(
                job.notify_output_areas.get(output.ref, output.area_id),
                job.outputs,
            )
        ]
        if not outputs:
            self._record_channel_failure(
                job,
                "notify",
                "No configured visual output matches the requested area",
            )
            return

        await self._deliver_available_then_wait(
            job,
            outputs,
            is_available=lambda item: notify_output_available(self.hass, item),
            deliver=lambda item: self._async_deliver_notification(job, item),
            channel=lambda item: item.ref,
            parallel=True,
        )

    async def _async_deliver_notification(
        self, job: AnnouncementJob, output: NotifyOutput
    ) -> None:
        channel = output.ref
        self._raise_if_cancelled(job)
        self._fire_channel_event(EVENT_CHANNEL_STARTED, job, channel)
        integration = output.integration or PROFILE_DEFAULT
        profile = normalise_notify_profile(
            job.notify_output_profiles.get(output.ref), integration
        )
        parts = split_message(
            job.notify_text or "", int(profile[PROFILE_MAX_LENGTH])
        )
        if not parts:
            raise HomeAssistantError("Notification text is empty after normalisation")

        try:
            for index, part in enumerate(parts, start=1):
                self._raise_if_cancelled(job)
                hold_seconds = reading_seconds(
                    part,
                    words_per_minute=float(profile[PROFILE_READING_WPM]),
                    minimum_seconds=float(profile[PROFILE_MIN_DISPLAY]),
                    maximum_seconds=float(profile[PROFILE_MAX_DISPLAY]),
                    buffer_seconds=float(profile[PROFILE_DISPLAY_BUFFER]),
                )
                if output.integration == INTEGRATION_NFANDROIDTV:
                    # Android TV accepts whole-second durations. Keep the queue
                    # locked for the same rounded-up value so adjacent parts do
                    # not overlap at the display boundary.
                    hold_seconds = float(max(1, math.ceil(hold_seconds)))
                title = format_part_title(
                    job.title,
                    index=index,
                    total=len(parts),
                    show_part_number=bool(profile[PROFILE_SHOW_PART_NUMBER]),
                )
                await self._async_deliver_notification_part(
                    job,
                    output,
                    profile=profile,
                    message=part,
                    title=title,
                    hold_seconds=hold_seconds,
                    part_index=index,
                    part_count=len(parts),
                )
                await self._async_reading_hold(job, hold_seconds)
                if index < len(parts):
                    gap = float(profile[PROFILE_PART_GAP])
                    if gap > 0:
                        await self._async_reading_hold(job, gap)
        except JobCancelled:
            raise
        except asyncio.CancelledError:
            raise
        else:
            self._record_channel_success(job, channel)

    async def _async_deliver_notification_part(
        self,
        job: AnnouncementJob,
        output: NotifyOutput,
        *,
        profile: Mapping[str, Any],
        message: str,
        title: str | None,
        hold_seconds: float,
        part_index: int,
        part_count: int,
    ) -> None:
        integration_data = profile.get(PROFILE_INTEGRATION_DATA, {})
        provider_data = self._deep_merge(
            dict(integration_data) if isinstance(integration_data, Mapping) else {},
            job.notify_data,
        )

        if output.integration == INTEGRATION_NFANDROIDTV:
            # The integration's advanced placement/style options are available
            # only through its legacy notify.<name> action.
            provider_data.update(
                {
                    "duration": max(1, int(hold_seconds + 0.999)),
                    "position": profile[PROFILE_NF_POSITION],
                    "fontsize": profile[PROFILE_NF_FONTSIZE],
                    "color": profile[PROFILE_NF_COLOR],
                    "transparency": profile[PROFILE_NF_TRANSPARENCY],
                    "interrupt": bool(profile[PROFILE_NF_INTERRUPT]),
                }
            )

        legacy_service = notify_output_legacy_service(self.hass, output)
        if output.integration == INTEGRATION_NFANDROIDTV:
            # Prefer Home Assistant's provider action when it exists because it
            # also supports image/icon loading. Modern config-entry installs can
            # expose only the NotifyEntity, though, so use the integration's
            # already-connected runtime client as the advanced fallback.
            if legacy_service:
                await self._async_call_legacy_notify(
                    legacy_service,
                    message=message,
                    title=title,
                    data=provider_data,
                )
                return
            if await self._async_send_nfandroidtv_runtime(
                output,
                message=message,
                title=title,
                data=provider_data,
            ):
                return
            raise HomeAssistantError(
                "Notifications for Android TV has no active advanced delivery "
                "path; position/style data cannot be applied"
            )

        if output.service:
            await self._async_call_legacy_notify(
                output.service,
                message=message,
                title=title,
                data=provider_data,
            )
            return

        if not output.entity_id:
            raise HomeAssistantError("Notification output has no target")

        if (
            output.integration == INTEGRATION_MOBILE_APP
            and output.config_entry_id
            and self.hass.services.has_service("notify", "mobile_app")
            and (
                webhook_id := mobile_app_webhook_id(
                    self.hass, output.config_entry_id
                )
            )
        ):
            if part_count > 1 and bool(profile.get(PROFILE_REPLACE_PARTS, True)):
                provider_data.setdefault(
                    "tag",
                    f"announcement_hub_{job.job_id}_{output.config_entry_id}",
                )
            data: dict[str, Any] = {
                "target": [webhook_id],
                "message": message,
            }
            if title:
                data["title"] = title
            if provider_data:
                data["data"] = provider_data
            await self.hass.services.async_call(
                "notify", "mobile_app", data, blocking=True
            )
            return

        # Modern NotifyEntity actions accept title and message. Provider-specific
        # data is used whenever a compatible legacy action is available above.
        data = {
            ATTR_ENTITY_ID: output.entity_id,
            "message": message,
        }
        if title:
            data["title"] = title
        await self.hass.services.async_call(
            "notify", "send_message", data, blocking=True
        )

    async def _async_send_nfandroidtv_runtime(
        self,
        output: NotifyOutput,
        *,
        message: str,
        title: str | None,
        data: Mapping[str, Any],
    ) -> bool:
        "Send through NFAndroidTV's live config-entry client."
        if not output.config_entry_id:
            return False
        entry = self.hass.config_entries.async_get_entry(output.config_entry_id)
        if entry is None or entry.domain != INTEGRATION_NFANDROIDTV:
            return False
        client = getattr(entry, "runtime_data", None)
        send = getattr(client, "send", None)
        if not callable(send):
            return False

        duration_value = data.get("duration")
        duration = int(duration_value) if duration_value is not None else None
        await self.hass.async_add_executor_job(
            partial(
                send,
                message,
                title=title,
                duration=duration,
                fontsize=data.get("fontsize"),
                position=data.get("position"),
                bkgcolor=data.get("bkgcolor", data.get("color")),
                transparency=data.get("transparency"),
                interrupt=bool(data.get("interrupt", False)),
            )
        )
        return True

    async def _async_call_legacy_notify(
        self,
        service_ref: str,
        *,
        message: str,
        title: str | None,
        data: Mapping[str, Any],
    ) -> None:
        domain, separator, service = service_ref.partition(".")
        if not separator or not service:
            raise HomeAssistantError(
                f"Invalid notification service: {service_ref}"
            )
        payload: dict[str, Any] = {"message": message}
        if title:
            payload["title"] = title
        if data:
            payload["data"] = deepcopy(dict(data))
        await self.hass.services.async_call(
            domain, service, payload, blocking=True
        )

    async def _async_reading_hold(
        self, job: AnnouncementJob, seconds: float
    ) -> None:
        """Hold the queue while still reacting promptly to cancellation."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, float(seconds))
        while loop.time() < deadline:
            self._raise_if_cancelled(job)
            await asyncio.sleep(min(0.25, max(0.0, deadline - loop.time())))

    async def _deliver_available_then_wait(
        self,
        job: AnnouncementJob,
        items: Sequence[Any],
        *,
        is_available: Callable[[Any], bool],
        deliver: Callable[[Any], Awaitable[None]],
        channel: Callable[[Any], str],
        parallel: bool = False,
    ) -> None:
        """Deliver ready outputs, wait once, then silently skip unavailable ones."""
        pending = list(items)
        last_errors: dict[str, str] = {}

        async def attempt(item: Any) -> bool:
            channel_name = channel(item)
            try:
                await deliver(item)
            except JobCancelled:
                raise
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                last_errors[channel_name] = str(err)
                return False
            last_errors.pop(channel_name, None)
            return True

        async def attempt_ready(ready_items: Sequence[Any]) -> None:
            if not ready_items:
                return
            if parallel:
                results = await asyncio.gather(
                    *(attempt(item) for item in ready_items)
                )
            else:
                results = []
                for item in ready_items:
                    results.append(await attempt(item))
            for item, succeeded in zip(ready_items, results, strict=True):
                if succeeded and item in pending:
                    pending.remove(item)

        # Never make an already usable output wait behind an unavailable one.
        await attempt_ready(
            tuple(item for item in pending if is_available(item))
        )

        timeout = self._availability_timeout
        if pending and timeout > 0:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            while pending and loop.time() < deadline:
                self._raise_if_cancelled(job)
                await asyncio.sleep(min(0.5, max(0.0, deadline - loop.time())))
                await attempt_ready(
                    tuple(item for item in pending if is_available(item))
                )

        # Remaining items are unavailable outputs, not announcement errors.
        # Keep this at debug level for diagnostics without creating Repairs/log
        # warnings or marking the job completed_with_errors.
        if pending:
            skipped = {
                channel(item): last_errors.get(channel(item), "unavailable")
                for item in pending
            }
            _LOGGER.debug(
                "Announcement %s skipped unavailable output(s) after %ss: %s",
                job.job_id,
                f"{timeout:g}",
                skipped,
            )

    async def _async_send_tts(self, job: AnnouncementJob) -> None:
        if not job.tts_text:
            return

        if job.server_tts_enabled and job.tts_engines:
            try:
                await self._async_send_server_tts(job)
            except JobCancelled:
                raise
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                # A failed shared player, TTS engine, or Snapcast route must not
                # prevent a separately selected Companion App TTS output.
                self._record_channel_failure(job, "server_tts", err)

        if job.companion_tts_entries:
            await self._async_send_companion_tts(job)

    async def _async_send_server_tts(self, job: AnnouncementJob) -> None:
        player = job.tts_media_player
        if not player:
            self._record_channel_failure(
                job, "server_tts", "No TTS media player is configured"
            )
            return
        self._active_tts_player = player
        await self._await_prefetch(job)

        matching_clients = [
            entity_id
            for entity_id in job.snapcast_clients
            if not job.outputs
            or job.snapcast_client_areas.get(
                entity_id, entity_area_id(self.hass, entity_id)
            )
            in set(job.outputs)
        ]
        if job.snapcast_clients and not matching_clients:
            self._record_channel_failure(
                job,
                "snapcast",
                "No selected Snapcast output belongs to the requested area",
            )
            return

        if not job.snapcast_clients:
            player_area = job.tts_player_area
            if job.outputs and player_area is not None and player_area not in set(
                job.outputs
            ):
                self._record_channel_failure(
                    job,
                    f"player:{player}",
                    "The TTS media player does not belong to the requested area",
                )
                return
            if not await self._async_wait_player_available(player, job):
                return
            await self._async_play_server_round(
                job, player, selected_clients=(), target_clients=()
            )
            return

        ready = [
            entity_id
            for entity_id in matching_clients
            if self._snapcast_output_available(entity_id)
        ]
        pending = [
            entity_id for entity_id in matching_clients if entity_id not in ready
        ]

        if ready:
            await self._async_play_server_round(
                job,
                player,
                selected_clients=job.snapcast_clients,
                target_clients=ready,
            )

        timeout = self._availability_timeout
        if pending and timeout > 0:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            while pending and loop.time() < deadline:
                self._raise_if_cancelled(job)
                newly_ready = [
                    entity_id
                    for entity_id in pending
                    if self._snapcast_output_available(entity_id)
                ]
                if newly_ready:
                    for entity_id in newly_ready:
                        pending.remove(entity_id)
                    await self._async_play_server_round(
                        job,
                        player,
                        selected_clients=job.snapcast_clients,
                        target_clients=newly_ready,
                    )
                if pending:
                    await asyncio.sleep(min(0.1, max(0.0, deadline - loop.time())))

        if pending:
            _LOGGER.debug(
                "Announcement %s skipped unavailable Snapcast output(s) after %ss: %s",
                job.job_id,
                f"{timeout:g}",
                pending,
            )

    async def _async_play_server_round(
        self,
        job: AnnouncementJob,
        player: str,
        *,
        selected_clients: Sequence[str],
        target_clients: Sequence[str],
    ) -> None:
        self._raise_if_cancelled(job)
        if not await self._async_wait_player_available(player, job):
            return

        idle_timeout = float(
            self.settings.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT)
        )
        await self._wait_audio_path_idle(
            player, idle_timeout, job, selected_clients
        )

        route_snapshot: dict[str, bool] | None = None
        route_targets: tuple[str, ...] = ()
        if target_clients:
            route_snapshot, route_targets = await self._async_apply_snapcast_route(
                job,
                selected_clients=selected_clients,
                target_clients=target_clients,
            )

        try:
            engines = await self._async_available_tts_engines(job)
            if not engines:
                return
            errors: list[str] = []
            for engine in engines:
                channel = f"server_tts:{engine}"
                self._fire_channel_event(EVENT_CHANNEL_STARTED, job, channel)
                try:
                    media_source_id = job.media_source_ids.get(engine)
                    if not media_source_id:
                        media_source_id = self._build_media_source_id(job, engine)
                        job.media_source_ids[engine] = media_source_id
                    await self._async_play_media_source(
                        job, player, media_source_id, route_targets
                    )
                except JobCancelled:
                    raise
                except asyncio.CancelledError:
                    raise
                except Exception as err:  # noqa: BLE001
                    errors.append(f"{engine}: {err}")
                    await self._async_stop_player(player)
                    self._record_channel_failure(job, channel, err)
                    continue
                self._record_channel_success(job, channel)
                break
            else:
                raise HomeAssistantError(
                    "Every selected TTS engine failed: " + "; ".join(errors)
                )

            post_delay = float(
                self.settings.get(CONF_POST_PLAY_DELAY, DEFAULT_POST_PLAY_DELAY)
            )
            if post_delay > 0:
                await asyncio.sleep(post_delay)
        finally:
            if route_snapshot is not None and self.settings.get(
                CONF_SNAPCAST_RESTORE, DEFAULT_SNAPCAST_RESTORE
            ):
                try:
                    await self._async_restore_snapcast(route_snapshot)
                except asyncio.CancelledError:
                    raise
                except Exception as err:  # noqa: BLE001
                    self._record_channel_failure(job, "snapcast_restore", err)

    async def _async_available_tts_engines(
        self, job: AnnouncementJob
    ) -> tuple[str, ...]:
        ready = [
            engine
            for engine in job.tts_engines
            if tts_engine_available(self.hass, engine)
        ]
        if ready or self._availability_timeout <= 0:
            return tuple(ready)
        available = await self._wait_for(
            lambda: any(
                tts_engine_available(self.hass, engine)
                for engine in job.tts_engines
            ),
            timeout=self._availability_timeout,
            job=job,
            interval=0.1,
        )
        if not available:
            return ()
        return tuple(
            engine
            for engine in job.tts_engines
            if tts_engine_available(self.hass, engine)
        )

    async def _async_wait_player_available(
        self, player: str, job: AnnouncementJob
    ) -> bool:
        def available() -> bool:
            state = self.hass.states.get(player)
            return state is not None and state.state not in {
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            }

        if available():
            return True
        if self._availability_timeout <= 0:
            return False
        return await self._wait_for(
            available,
            timeout=self._availability_timeout,
            job=job,
            interval=0.1,
        )

    async def _async_send_companion_tts(self, job: AnnouncementJob) -> None:
        outputs = [
            output
            for output in resolve_companion_tts_outputs(
                self.hass, job.companion_tts_entries
            )
            if output_matches_areas(
                job.companion_tts_entry_areas.get(
                    output.entry_id, output.area_id
                ),
                job.outputs,
            )
        ]
        if not outputs:
            self._record_channel_failure(
                job,
                "companion_tts",
                "No selected Companion App TTS output matches the requested area",
            )
            return

        await self._deliver_available_then_wait(
            job,
            outputs,
            is_available=lambda item: companion_output_available(self.hass, item),
            deliver=lambda item: self._async_deliver_companion_tts(job, item),
            channel=lambda item: f"companion_tts:{item.entry_id}",
        )

    async def _async_deliver_companion_tts(
        self, job: AnnouncementJob, output: CompanionTTSOutput
    ) -> None:
        channel = f"companion_tts:{output.entry_id}"
        self._raise_if_cancelled(job)
        self._fire_channel_event(EVENT_CHANNEL_STARTED, job, channel)
        try:
            webhook_id = mobile_app_webhook_id(self.hass, output.entry_id)
            if not webhook_id:
                raise HomeAssistantError(
                    f"Companion App entry {output.title} has no webhook target"
                )
            data: dict[str, Any] = {
                "target": [webhook_id],
                "message": "TTS",
                "data": {"tts_text": job.tts_text},
            }
            stream = job.companion_tts_media_stream
            if stream != COMPANION_STREAM_DEFAULT:
                data["data"]["media_stream"] = stream
            await self.hass.services.async_call(
                "notify", "mobile_app", data, blocking=True
            )
            await asyncio.sleep(
                self._companion_tts_hold_time(
                    job.tts_text or "",
                    job.companion_tts_words_per_minute,
                )
            )
        except JobCancelled:
            raise
        except asyncio.CancelledError:
            raise
        else:
            self._record_channel_success(job, channel)

    def _companion_tts_hold_time(self, text: str, configured_wpm: float) -> float:
        words = max(1, len(text.split()))
        wpm = max(1.0, float(configured_wpm))
        estimate = words / wpm * 60.0 + 0.75
        playback_timeout = float(
            self.settings.get(CONF_PLAYBACK_TIMEOUT, DEFAULT_PLAYBACK_TIMEOUT)
        )
        return min(max(estimate, 1.0), playback_timeout)

    async def _async_play_media_source(
        self,
        job: AnnouncementJob,
        player: str,
        media_source_id: str,
        route_targets: Sequence[str] = (),
    ) -> None:
        self._raise_if_cancelled(job)
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            "play_media",
            {
                ATTR_ENTITY_ID: player,
                ATTR_MEDIA_CONTENT_ID: media_source_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_ANNOUNCE: True,
            },
            blocking=True,
        )

        start_timeout = float(
            self.settings.get(CONF_START_TIMEOUT, DEFAULT_START_TIMEOUT)
        )
        started = await self._wait_for(
            lambda: self._is_player_busy(player)
            or self._any_snapcast_busy(route_targets),
            timeout=start_timeout,
            job=job,
        )
        if not started:
            raise HomeAssistantError(
                f"TTS playback did not start on {player} or its routed "
                f"Snapcast clients within {start_timeout}s"
            )

        playback_timeout = float(
            self.settings.get(CONF_PLAYBACK_TIMEOUT, DEFAULT_PLAYBACK_TIMEOUT)
        )
        finished = await self._wait_for(
            lambda: not self._is_player_busy(player)
            and not self._any_snapcast_busy(route_targets),
            timeout=playback_timeout,
            job=job,
        )
        if not finished:
            await self._async_stop_player(player)
            raise HomeAssistantError(
                f"TTS playback exceeded {playback_timeout}s on {player}"
            )

    def _snapcast_output_available(self, entity_id: str) -> bool:
        """Return whether a client can be routed on the configured TTS source."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {
            STATE_OFF,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        }:
            return False
        if state.attributes.get("is_volume_muted") is None:
            return False
        source = str(
            self.settings.get(CONF_SNAPCAST_SOURCE, DEFAULT_SNAPCAST_SOURCE) or ""
        )
        source_only = bool(
            self.settings.get(
                CONF_SNAPCAST_ONLY_SOURCE, DEFAULT_SNAPCAST_ONLY_SOURCE
            )
        )
        return not (
            source_only
            and source
            and state.attributes.get("source") != source
        )

    def _routable_snapcast_snapshot(
        self, selected_clients: Sequence[str]
    ) -> dict[str, bool]:
        # Selected clients are eligible announcement targets. Every currently
        # known Snapcast client on the managed announcement source is part of the
        # route snapshot so an unselected client cannot leak the same TTS stream.
        all_snapcast_clients = expand_snapcast_output_tokens(
            self.hass, [f"{TARGET_INTEGRATION_PREFIX}snapcast"]
        )
        route_scope = tuple(
            dict.fromkeys((*selected_clients, *all_snapcast_clients))
        )
        source = str(
            self.settings.get(CONF_SNAPCAST_SOURCE, DEFAULT_SNAPCAST_SOURCE) or ""
        )
        source_only = bool(
            self.settings.get(
                CONF_SNAPCAST_ONLY_SOURCE, DEFAULT_SNAPCAST_ONLY_SOURCE
            )
        )
        snapshot: dict[str, bool] = {}
        for entity_id in route_scope:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in {
                STATE_OFF,
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            }:
                continue
            muted = state.attributes.get("is_volume_muted")
            if muted is None:
                continue
            if source_only and source and state.attributes.get("source") != source:
                continue
            snapshot[entity_id] = bool(muted)
        return snapshot

    async def _async_apply_snapcast_route(
        self,
        job: AnnouncementJob,
        *,
        selected_clients: Sequence[str],
        target_clients: Sequence[str],
    ) -> tuple[dict[str, bool], tuple[str, ...]]:
        snapshot = self._routable_snapcast_snapshot(selected_clients)
        if not snapshot:
            raise HomeAssistantError(
                "No selected Snapcast client is currently routable"
            )
        target = [entity_id for entity_id in target_clients if entity_id in snapshot]
        if not target:
            raise HomeAssistantError(
                "No requested Snapcast client is currently routable"
            )

        target_set = set(target)
        desired = {
            entity_id: entity_id not in target_set for entity_id in snapshot
        }
        route_changed = False
        try:
            await self._async_set_mute_states(desired)
            route_changed = True
            settle = float(
                self.settings.get(
                    CONF_SNAPCAST_SETTLE_DELAY, DEFAULT_SNAPCAST_SETTLE_DELAY
                )
            )
            if settle > 0:
                await asyncio.sleep(settle)

            verify_timeout = float(
                self.settings.get(
                    CONF_SNAPCAST_VERIFY_TIMEOUT,
                    DEFAULT_SNAPCAST_VERIFY_TIMEOUT,
                )
            )
            verified = await self._wait_for(
                lambda: self._mute_states_match(desired),
                timeout=verify_timeout,
                job=job,
            )
            if not verified:
                raise HomeAssistantError(
                    "Snapcast clients did not reach the requested mute state"
                )
            return snapshot, tuple(target)
        except asyncio.CancelledError:
            if route_changed:
                with suppress(asyncio.CancelledError, Exception):
                    await self._async_restore_snapcast(snapshot)
            raise
        except Exception:
            if route_changed:
                with suppress(asyncio.CancelledError, Exception):
                    await self._async_restore_snapcast(snapshot)
            raise

    async def _async_restore_snapcast(self, snapshot: Mapping[str, bool]) -> None:
        if not snapshot:
            return
        await self._async_set_mute_states(snapshot)
        settle = float(
            self.settings.get(
                CONF_SNAPCAST_SETTLE_DELAY, DEFAULT_SNAPCAST_SETTLE_DELAY
            )
        )
        if settle > 0:
            await asyncio.sleep(settle)

    async def _async_set_mute_states(
        self, desired: Mapping[str, bool]
    ) -> None:
        errors: list[str] = []
        for muted in (True, False):
            for entity_id, should_mute in desired.items():
                if should_mute is not muted:
                    continue
                state = self.hass.states.get(entity_id)
                if state is None:
                    errors.append(f"{entity_id}: entity is missing")
                    continue
                current = state.attributes.get("is_volume_muted")
                if current is not None and bool(current) == muted:
                    continue
                try:
                    await self.hass.services.async_call(
                        MEDIA_PLAYER_DOMAIN,
                        "volume_mute",
                        {
                            ATTR_ENTITY_ID: entity_id,
                            "is_volume_muted": muted,
                        },
                        blocking=True,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as err:  # noqa: BLE001
                    errors.append(f"{entity_id}: {err}")
        if errors:
            raise HomeAssistantError(
                "Could not update every Snapcast mute state: "
                + "; ".join(errors)
            )

    def _mute_states_match(self, desired: Mapping[str, bool]) -> bool:
        for entity_id, expected in desired.items():
            state = self.hass.states.get(entity_id)
            if state is None:
                return False
            current = state.attributes.get("is_volume_muted")
            if current is None or bool(current) != expected:
                return False
        return True

    async def _wait_audio_path_idle(
        self,
        player: str,
        timeout: float,
        job: AnnouncementJob,
        selected_clients: Sequence[str] = (),
    ) -> None:
        snapcast_clients = tuple(
            self._routable_snapcast_snapshot(selected_clients)
        )
        idle = await self._wait_for(
            lambda: not self._is_player_busy(player)
            and not self._any_snapcast_busy(snapcast_clients),
            timeout=timeout,
            job=job,
        )
        if not idle:
            raise HomeAssistantError(
                f"The TTS audio path ({player} and selected Snapcast clients) "
                f"remained busy for {timeout}s"
            )

    async def _wait_for(
        self,
        predicate: Callable[[], bool],
        *,
        timeout: float,
        job: AnnouncementJob,
        interval: float = 0.05,
    ) -> bool:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(timeout, 0)
        while True:
            self._raise_if_cancelled(job)
            if predicate():
                return True
            if loop.time() >= deadline:
                return False
            await asyncio.sleep(interval)

    def _player_state(self, entity_id: str) -> str | None:
        state = self.hass.states.get(entity_id)
        return state.state if state else None

    def _is_player_busy(self, entity_id: str) -> bool:
        return self._player_state(entity_id) in _BUSY_STATES

    def _any_snapcast_busy(self, entity_ids: Sequence[str]) -> bool:
        return any(self._is_player_busy(entity_id) for entity_id in entity_ids)

    async def _async_stop_player(self, player: str) -> None:
        with suppress(asyncio.CancelledError, HomeAssistantError, Exception):
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                "media_stop",
                {ATTR_ENTITY_ID: player},
                blocking=True,
            )

    def _schedule_prefetch(self, job: AnnouncementJob) -> None:
        if not job.tts_text or not job.server_tts_enabled or not job.tts_engines:
            return
        if not job.tts_cache or job.job_id in self._prefetch_tasks:
            return
        task = self.entry.async_create_background_task(
            self.hass,
            self._async_prefetch(job),
            f"{DOMAIN} prefetch {job.job_id}",
        )
        self._prefetch_tasks[job.job_id] = task

        def _done(done_task: asyncio.Task[None]) -> None:
            if done_task.cancelled():
                return
            if error := done_task.exception():
                _LOGGER.debug("TTS prefetch task failed: %s", error)
            self._schedule_save()
            self._wake.set()
            self._notify_update()

        task.add_done_callback(_done)

    async def _async_prefetch(self, job: AnnouncementJob) -> None:
        async def prefetch_engine(engine: str) -> None:
            try:
                media_source_id = self._build_media_source_id(job, engine)
                job.media_source_ids[engine] = media_source_id
                await tts.async_get_media_source_audio(self.hass, media_source_id)
                job.prefetch_errors.pop(engine, None)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                job.prefetch_errors[engine] = str(err)
                _LOGGER.warning(
                    "Could not pre-generate TTS for %s using %s: %s",
                    job.job_id,
                    engine,
                    err,
                )

        await asyncio.gather(
            *(prefetch_engine(engine) for engine in job.tts_engines)
        )

    async def _await_prefetch(self, job: AnnouncementJob) -> None:
        task = self._prefetch_tasks.get(job.job_id)
        if task is not None:
            with suppress(asyncio.CancelledError):
                await task

    def _build_media_source_id(self, job: AnnouncementJob, engine: str) -> str:
        return generate_media_source_id(
            self.hass,
            message=job.tts_text or "",
            engine=engine,
            language=job.language,
            options=job.tts_options,
            cache=job.tts_cache,
        )

    def _fallback_area_id(self) -> str | None:
        """Return the configured fallback room as an area ID."""
        value = str(self.settings.get(CONF_FALLBACK_ROOM, "") or "").strip()
        if not value:
            return None
        registry = ar.async_get(self.hass)
        if registry.async_get_area(value):
            return value
        if area := registry.async_get_area_by_name(value):
            return area.id
        _LOGGER.debug("Configured fallback room %s is not a known area", value)
        return None

    def _fallback_door_allows(self, occupied_area_ids: Sequence[str]) -> bool:
        """Allow fallback when door checking is disabled or an occupied door is open."""
        if not bool(
            self.settings.get(
                CONF_FALLBACK_CHECK_DOOR,
                DEFAULT_FALLBACK_CHECK_DOOR,
            )
        ):
            return True

        occupied = set(occupied_area_ids)
        if not occupied:
            return False

        found_door = False
        for state in self.hass.states.async_all("binary_sensor"):
            if state.attributes.get("device_class") != "door":
                continue
            if entity_area_id(self.hass, state.entity_id) not in occupied:
                continue
            found_door = True
            if state.state == STATE_ON:
                return True

        if not found_door:
            _LOGGER.debug(
                "Fallback blocked: no door binary sensor belongs to occupied area(s) %s",
                sorted(occupied),
            )
        else:
            _LOGGER.debug(
                "Fallback blocked: every occupied-area door is closed or unavailable"
            )
        return False

    def _occupied_area_ids(self) -> tuple[str, ...] | None:
        """Resolve occupied areas from the configured sensor state or attribute."""
        sensor = str(self.settings.get(CONF_OCCUPANCY_SENSOR, "") or "").strip()
        if not sensor:
            return None
        state = self.hass.states.get(sensor)
        if state is None or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            _LOGGER.debug("Occupancy sensor %s is unavailable", sensor)
            return ()

        attribute = str(
            self.settings.get(CONF_OCCUPANCY_ATTRIBUTE, "") or ""
        ).strip()
        raw: Any = state.attributes.get(attribute) if attribute else state.state
        values = self._occupancy_values(raw)
        if not values:
            return ()

        registry = ar.async_get(self.hass)
        areas = registry.async_list_areas()
        by_name = {area.name.casefold(): area.id for area in areas}
        by_alias = {
            alias.casefold(): area.id
            for area in areas
            for alias in (area.aliases or set())
        }
        resolved: list[str] = []
        unknown: list[str] = []
        for value in values:
            if registry.async_get_area(value):
                resolved.append(value)
                continue
            key = value.casefold()
            if area_id := by_name.get(key) or by_alias.get(key):
                resolved.append(area_id)
            else:
                unknown.append(value)

        if unknown:
            _LOGGER.debug(
                "Occupancy source %s reported unknown area value(s): %s",
                sensor,
                unknown,
            )
        return tuple(dict.fromkeys(resolved))

    @staticmethod
    def _occupancy_values(raw: Any) -> list[str]:
        """Normalise a state/attribute into area names or IDs."""
        if raw is None:
            return []
        if isinstance(raw, Mapping):
            return [
                str(key).strip()
                for key, enabled in raw.items()
                if enabled and str(key).strip()
            ]
        if isinstance(raw, (list, tuple, set)):
            return [str(item).strip() for item in raw if str(item).strip()]

        value = str(raw).strip()
        if not value:
            return []
        if value.startswith("[") and value.endswith("]"):
            try:
                decoded = json.loads(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                decoded = None
            if isinstance(decoded, list):
                return [
                    str(item).strip()
                    for item in decoded
                    if str(item).strip()
                ]
        return [
            part.strip().strip("'\"")
            for part in re.split(r"[,;\n]+", value)
            if part.strip().strip("'\"")
        ]

    def _resolve_area_ids(self, values: Sequence[str]) -> tuple[str, ...]:
        if not values:
            return ()
        registry = ar.async_get(self.hass)
        resolved: list[str] = []
        unknown: list[str] = []
        for value in values:
            if registry.async_get_area(value):
                resolved.append(value)
                continue
            if area := registry.async_get_area_by_name(value):
                resolved.append(area.id)
                continue
            alias_match = next(
                (
                    area
                    for area in registry.async_list_areas()
                    if value.casefold()
                    in {alias.casefold() for alias in (area.aliases or set())}
                ),
                None,
            )
            if alias_match:
                resolved.append(alias_match.id)
            else:
                unknown.append(value)
        if unknown:
            raise ServiceValidationError(
                "Unknown output area(s): " + ", ".join(unknown)
            )
        return tuple(dict.fromkeys(resolved))

    def _raise_if_cancelled(self, job: AnnouncementJob) -> None:
        if job.job_id in self._cancel_requested:
            raise JobCancelled(f"Announcement {job.job_id} was cancelled")

    @staticmethod
    def _ensure_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value if item]

    @staticmethod
    def _deep_merge(
        base: dict[str, Any], override: Mapping[str, Any]
    ) -> dict[str, Any]:
        result = deepcopy(base)
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, Mapping)
            ):
                result[key] = AnnouncementManager._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    def _serialize(self) -> dict[str, Any]:
        jobs = [job.to_dict() for job in self._queue]
        if self._current and self._current.status not in _TERMINAL_JOB_STATES:
            jobs.insert(0, self._current.to_dict())
        return {
            "jobs": jobs,
            "last": self._last.to_dict() if self._last else None,
        }

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._serialize, 0.5)

    def _notify_update(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    def _record_channel_success(self, job: AnnouncementJob, channel: str) -> None:
        if channel not in job.successful_channels:
            job.successful_channels.append(channel)
        job.channel_errors.pop(channel, None)
        self._fire_channel_event(EVENT_CHANNEL_FINISHED, job, channel)
        self._schedule_save()
        self._notify_update()

    def _record_channel_failure(
        self, job: AnnouncementJob, channel: str, error: Exception | str
    ) -> None:
        job.channel_errors[channel] = str(error)
        self._fire_channel_event(EVENT_CHANNEL_FAILED, job, channel)
        _LOGGER.warning(
            "Announcement %s channel %s failed: %s",
            job.job_id,
            channel,
            error,
        )
        self._schedule_save()
        self._notify_update()

    def _fire_event(self, event_type: str, job: AnnouncementJob) -> None:
        self.hass.bus.async_fire(event_type, job.public_dict(include_text=False))

    def _fire_channel_event(
        self, event_type: str, job: AnnouncementJob, channel: str
    ) -> None:
        data = job.public_dict(include_text=False)
        data["channel"] = channel
        self.hass.bus.async_fire(event_type, data)
