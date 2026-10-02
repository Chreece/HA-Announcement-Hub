"""Persistent job models and level-aware delivery planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .const import (
    LEVEL_CRITICAL,
    LEVEL_INFO,
    LEVEL_PRIORITY,
    PROFILE_INTEGRATION_DATA,
    TTS_LEVEL_NEVER,
)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def utcnow_iso() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC).isoformat()


def tts_allowed_for_level(level: str, minimum_level: str) -> bool:
    """Return whether audible delivery is enabled for this severity.

    Critical always remains audible because the public service contract defines it
    as delivery through every configured output. Success intentionally shares the
    same severity weight as information.
    """
    if level == LEVEL_CRITICAL:
        return True
    if minimum_level == TTS_LEVEL_NEVER:
        return False
    return LEVEL_PRIORITY.get(level, LEVEL_PRIORITY[LEVEL_INFO]) >= LEVEL_PRIORITY.get(
        minimum_level, 0
    )


@dataclass(slots=True)
class DeliveryPlan:
    """Frozen physical outputs and channel texts for one queued job."""

    tts_engines: tuple[str, ...] = ()
    notify_outputs: tuple[str, ...] = ()
    room_tts_players: tuple[str, ...] = ()
    snapcast_clients: tuple[str, ...] = ()
    companion_tts_entries: tuple[str, ...] = ()
    tts_text: str | None = None
    notify_text: str | None = None
    server_tts_enabled: bool = False
    tts_suppressed_by_level: bool = False

    @property
    def has_visual_output(self) -> bool:
        return bool(self.notify_text and self.notify_outputs)

    @property
    def has_audible_output(self) -> bool:
        if not self.tts_text:
            return False
        return bool(
            self.room_tts_players
            or (self.server_tts_enabled and self.tts_engines)
            or self.companion_tts_entries
        )

    @property
    def has_output(self) -> bool:
        return self.has_visual_output or self.has_audible_output


def build_delivery_plan(
    *,
    text_tts: str | None,
    text_notify: str | None,
    level: str,
    minimum_tts_level: str,
    tts_engines: Sequence[str],
    notify_outputs: Sequence[str],
    room_tts_players: Sequence[str] = (),
    snapcast_clients: Sequence[str],
    companion_tts_entries: Sequence[str],
    server_tts_enabled: bool,
) -> DeliveryPlan:
    """Apply critical and audible-threshold semantics to selected outputs."""
    audible = tts_allowed_for_level(level, minimum_tts_level)

    if level == LEVEL_CRITICAL:
        tts_text = text_tts or text_notify
        notify_text = text_notify or text_tts
    elif audible:
        tts_text = text_tts
        notify_text = text_notify
    else:
        # Below the audible threshold, spoken-only messages become visual rather
        # than disappearing. Explicit written text still takes precedence.
        tts_text = None
        notify_text = text_notify or text_tts

    return DeliveryPlan(
        tts_engines=_unique(tuple(tts_engines)),
        notify_outputs=_unique(tuple(notify_outputs)),
        room_tts_players=_unique(tuple(room_tts_players)),
        snapcast_clients=_unique(tuple(snapcast_clients)),
        companion_tts_entries=_unique(tuple(companion_tts_entries)),
        tts_text=tts_text,
        notify_text=notify_text,
        server_tts_enabled=bool(server_tts_enabled),
        tts_suppressed_by_level=bool(text_tts and not audible),
    )


@dataclass(slots=True)
class AnnouncementJob:
    """One persistent, fully resolved queue item."""

    job_id: str
    created_at: str
    text_tts: str | None
    text_notify: str | None
    outputs: tuple[str, ...]
    requested_services: tuple[str, ...]
    level: str
    title: str | None
    notify_data: dict[str, Any]
    language: str | None
    tts_options: dict[str, Any]
    tts_cache: bool
    tts_engines: tuple[str, ...]
    notify_outputs: tuple[str, ...]
    room_tts_players: tuple[str, ...]
    snapcast_clients: tuple[str, ...]
    companion_tts_entries: tuple[str, ...]
    tts_text: str | None
    notify_text: str | None
    server_tts_enabled: bool
    tts_media_player: str | None = None
    tts_player_area: str | None = None
    room_tts_player_areas: dict[str, str | None] = field(default_factory=dict)
    notify_output_areas: dict[str, str | None] = field(default_factory=dict)
    notify_output_profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    snapcast_client_areas: dict[str, str | None] = field(default_factory=dict)
    companion_tts_entry_areas: dict[str, str | None] = field(default_factory=dict)
    companion_tts_media_stream: str = "default"
    companion_tts_words_per_minute: float = 150.0
    tts_suppressed_by_level: bool = False
    media_source_ids: dict[str, str] = field(default_factory=dict)
    prefetch_errors: dict[str, str] = field(default_factory=dict)
    channel_errors: dict[str, str] = field(default_factory=dict)
    successful_channels: list[str] = field(default_factory=list)
    status: str = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None

    @classmethod
    def create(
        cls,
        *,
        text_tts: str | None,
        text_notify: str | None,
        outputs: Sequence[str],
        requested_services: Sequence[str],
        level: str,
        title: str | None,
        notify_data: Mapping[str, Any] | None,
        language: str | None,
        tts_options: Mapping[str, Any] | None,
        tts_cache: bool,
        plan: DeliveryPlan,
        tts_media_player: str | None = None,
        tts_player_area: str | None = None,
        room_tts_player_areas: Mapping[str, str | None] | None = None,
        notify_output_areas: Mapping[str, str | None] | None = None,
        notify_output_profiles: Mapping[str, Mapping[str, Any]] | None = None,
        snapcast_client_areas: Mapping[str, str | None] | None = None,
        companion_tts_entry_areas: Mapping[str, str | None] | None = None,
        companion_tts_media_stream: str = "default",
        companion_tts_words_per_minute: float = 150.0,
    ) -> "AnnouncementJob":
        return cls(
            job_id=uuid4().hex,
            created_at=utcnow_iso(),
            text_tts=text_tts,
            text_notify=text_notify,
            outputs=_unique(tuple(outputs)),
            requested_services=_unique(tuple(requested_services)),
            level=level or LEVEL_INFO,
            title=title,
            notify_data=dict(notify_data or {}),
            language=language or None,
            tts_options=dict(tts_options or {}),
            tts_cache=bool(tts_cache),
            tts_engines=plan.tts_engines,
            notify_outputs=plan.notify_outputs,
            room_tts_players=plan.room_tts_players,
            snapcast_clients=plan.snapcast_clients,
            companion_tts_entries=plan.companion_tts_entries,
            tts_text=plan.tts_text,
            notify_text=plan.notify_text,
            server_tts_enabled=plan.server_tts_enabled,
            tts_media_player=tts_media_player or None,
            tts_player_area=tts_player_area or None,
            room_tts_player_areas=dict(room_tts_player_areas or {}),
            notify_output_areas=dict(notify_output_areas or {}),
            notify_output_profiles={
                str(key): dict(value)
                for key, value in (notify_output_profiles or {}).items()
            },
            snapcast_client_areas=dict(snapcast_client_areas or {}),
            companion_tts_entry_areas=dict(companion_tts_entry_areas or {}),
            companion_tts_media_stream=companion_tts_media_stream or "default",
            companion_tts_words_per_minute=float(
                companion_tts_words_per_minute
            ),
            tts_suppressed_by_level=plan.tts_suppressed_by_level,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in (
            "outputs",
            "requested_services",
            "tts_engines",
            "notify_outputs",
            "room_tts_players",
            "snapcast_clients",
            "companion_tts_entries",
        ):
            data[key] = list(data[key])
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AnnouncementJob":
        """Restore current jobs and best-effort migrate v0.1 queue records."""
        payload = dict(data)

        if "tts_engines" not in payload:
            payload["tts_engines"] = payload.pop("tts_providers", [])
        if "notify_outputs" not in payload:
            entities = [
                f"entity:{entity_id}"
                for entity_id in payload.pop("notify_entities", [])
            ]
            services = [
                f"service:{service}"
                for service in payload.pop("notify_services", [])
            ]
            payload["notify_outputs"] = [*entities, *services]
        payload.setdefault("room_tts_players", [])
        payload.setdefault("snapcast_clients", [])
        payload.setdefault("companion_tts_entries", [])
        payload.setdefault("server_tts_enabled", bool(payload.get("tts_engines")))
        payload.setdefault("tts_media_player", None)
        payload.setdefault("tts_player_area", None)
        payload.setdefault("room_tts_player_areas", {})
        payload.setdefault("notify_output_areas", {})
        payload.setdefault("notify_output_profiles", {})
        payload.setdefault("snapcast_client_areas", {})
        payload.setdefault("companion_tts_entry_areas", {})
        payload.setdefault("companion_tts_media_stream", "default")
        payload.setdefault("companion_tts_words_per_minute", 150.0)
        payload.setdefault("tts_suppressed_by_level", False)

        for key in (
            "outputs",
            "requested_services",
            "tts_engines",
            "notify_outputs",
            "room_tts_players",
            "snapcast_clients",
            "companion_tts_entries",
        ):
            payload[key] = tuple(payload.get(key, ()))
        payload.setdefault("media_source_ids", {})
        payload.setdefault("prefetch_errors", {})
        payload.setdefault("channel_errors", {})
        payload.setdefault("successful_channels", [])
        payload.setdefault("notify_data", {})
        payload.setdefault("tts_options", {})
        payload.setdefault("tts_cache", True)
        payload.setdefault("status", "pending")
        payload.setdefault("started_at", None)
        payload.setdefault("finished_at", None)
        payload.setdefault("error", None)
        return cls(**payload)

    def public_dict(self, *, include_text: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "job_id": self.job_id,
            "created_at": self.created_at,
            "status": self.status,
            "level": self.level,
            "outputs": list(self.outputs),
            "requested_services": list(self.requested_services),
            "tts_engines": list(self.tts_engines),
            "notify_outputs": list(self.notify_outputs),
            "room_tts_players": list(self.room_tts_players),
            "snapcast_clients": list(self.snapcast_clients),
            "companion_tts_entries": list(self.companion_tts_entries),
            "tts_media_player": self.tts_media_player,
            "output_area_bindings": {
                "room_tts": dict(self.room_tts_player_areas),
                "notify": dict(self.notify_output_areas),
                "snapcast": dict(self.snapcast_client_areas),
                "companion_tts": dict(self.companion_tts_entry_areas),
            },
            "notify_output_profiles": {
                key: {
                    profile_key: profile_value
                    for profile_key, profile_value in value.items()
                    if profile_key != PROFILE_INTEGRATION_DATA
                }
                for key, value in self.notify_output_profiles.items()
            },
            "tts_suppressed_by_level": self.tts_suppressed_by_level,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "prefetch_errors": dict(self.prefetch_errors),
            "channel_errors": dict(self.channel_errors),
            "successful_channels": list(self.successful_channels),
        }
        if include_text:
            result["title"] = self.title
            result["text_tts"] = self.text_tts
            result["text_notify"] = self.text_notify
        return result
