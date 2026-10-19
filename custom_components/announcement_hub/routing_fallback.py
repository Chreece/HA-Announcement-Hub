"""Pure, fail-open routing policy for room-aware announcements.

The manager supplies Home Assistant's *configured* and authorized targets.
This module never discovers arbitrary entities, alters output selections,
chooses an unrequested service or uses availability to bypass a priority tier.
An availability timeout moves to the next tier; it never completes a job.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable, Sequence

STAGES = ("primary", "occupied", "fallback", "general")


@dataclass(frozen=True, slots=True)
class StageTargets:
    """Eligible physical destinations at one routing stage."""

    notify: tuple[str, ...] = ()
    room_tts: tuple[str, ...] = ()
    snapcast: tuple[str, ...] = ()
    companion_tts: tuple[str, ...] = ()

    @property
    def has_output(self) -> bool:
        return bool(self.notify or self.room_tts or self.snapcast or self.companion_tts)

    @property
    def has_audio(self) -> bool:
        return bool(self.room_tts or self.snapcast or self.companion_tts)


def prioritize_stage_targets(
    *,
    stage: str,
    candidates: StageTargets,
    normal_speech_allowed: bool,
    visual_ready: bool,
    audio_ready: bool,
    audio_retry: bool = False,
) -> StageTargets:
    """Prioritize *in-room* receipt over a soft TTS severity preference.

    Below the configured minimum TTS level, a ready visual endpoint suppresses
    speech in the requested room. If visual delivery is not currently possible,
    use that same room's ready speaker. In other occupied/door-gated fallback
    rooms, spoken delivery wins so occupants can hear the announcement.
    Unready room devices remain candidates for the stage's availability grace.

    "Never" is a separate hard user opt-out; the caller must not include speech
    candidates at all when that is configured (except Critical).
    """
    if stage == "general":
        return candidates
    audio = StageTargets(
        room_tts=candidates.room_tts,
        snapcast=candidates.snapcast,
        companion_tts=candidates.companion_tts,
    )
    visual = StageTargets(notify=candidates.notify)

    # A delivery provider may have acknowledged no output. Retry a different
    # channel in the *same room* before escalating to another room.
    if audio_retry:
        return audio
    if normal_speech_allowed:
        return candidates
    if stage == "primary":
        if visual_ready:
            return visual
        if audio_ready:
            return audio
        return candidates

    # Once a message has moved away from the explicitly requested room,
    # audible delivery is the preferred way to reach the person.
    if audio_ready:
        return audio
    if visual_ready:
        return visual
    return candidates


def next_stage(stage: str) -> str:
    """Advance a route priority without ever skipping past general outputs."""
    try:
        index = STAGES.index(stage)
    except ValueError:
        return STAGES[0]
    return STAGES[min(index + 1, len(STAGES) - 1)]


def select_stage_targets(
    *,
    stage: str,
    areas: Sequence[str],
    level_priority: int,
    notifications: Iterable[tuple[str, str | None, str, int]],
    room_tts: Iterable[tuple[str, str | None, str]],
    snapcast: Iterable[tuple[str, str | None]],
    companion_tts: Iterable[tuple[str, str | None]],
    speech_allowed: bool,
) -> StageTargets:
    """Respect each output's room/general scope and minimum notification level.

    Room tiers never include general/unassigned devices or unrelated rooms.
    General tier never includes room-bound devices, even when they are ready.
    The manager may relax its *soft* TTS minimum for room-local delivery when
    no visual output can receive the message. "Never" remains a hard opt-out
    except for Critical. Unavailable outputs remain candidates for the worker's
    availability grace window.
    """
    is_general = stage == "general"
    area_set = set(areas)

    def matches(area_id: str | None, scope: str) -> bool:
        if is_general:
            return scope == "general"
        return bool(area_id and area_id in area_set and scope == "room")

    notify = tuple(dict.fromkeys(
        ref
        for ref, area_id, scope, minimum in notifications
        if matches(area_id, scope) and level_priority >= minimum
    ))
    room_audio = tuple(dict.fromkeys(
        entity_id
        for entity_id, area_id, scope in room_tts
        if speech_allowed and matches(area_id, scope)
    ))
    # Every Snapcast client is physical/room-bound. Never play the shared
    # server TTS path without an explicitly selected target Snapcast client.
    snap_audio = tuple(dict.fromkeys(
        entity_id for entity_id, area_id in snapcast
        if speech_allowed and not is_general
        and area_id is not None and area_id in area_set
    ))
    companion = tuple(dict.fromkeys(
        entry_id for entry_id, area_id in companion_tts
        if speech_allowed and (
            (is_general and area_id is None)
            or (not is_general and area_id is not None and area_id in area_set)
        )
    ))
    return StageTargets(notify, room_audio, snap_audio, companion)
