"""Separate recipient selection from the requested delivery service.

Areas are a dynamic, room-fallback preference. Integrations, devices and
entities select exact authorized recipients. Service determines channel type;
it must never introduce a recipient not present in the selected target set.
This module deliberately has no Home Assistant imports so its safety contract
can be tested independently.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

# A service is a *channel*, not an integration or a recipient selector.
VISUAL = "notification"
SPEECH = "tts"
SNAPCAST = "snapcast"
COMPANION = "companion_tts"
CHANNELS = frozenset((VISUAL, SPEECH, SNAPCAST, COMPANION))

_ALIASES = {
    "notification": frozenset((VISUAL,)),
    "notify": frozenset((VISUAL,)),
    "visual": frozenset((VISUAL,)),
    "tts": frozenset((SPEECH, SNAPCAST, COMPANION)),
    "speech": frozenset((SPEECH, SNAPCAST, COMPANION)),
    "snapcast": frozenset((SNAPCAST,)),
    "companion_tts": frozenset((COMPANION,)),
    "all": CHANNELS,
    "both": CHANNELS,
}


def channel_selection(services: Sequence[str]) -> frozenset[str]:
    """Return the union of explicit channel classes, or all if omitted.

    A typo or old integration/provider alias must never accidentally broaden
    a request to all outputs. Callers wrap ValueError in HA validation errors.
    """
    if not services:
        return CHANNELS
    result: set[str] = set()
    for service in services:
        key = str(service).strip().casefold()
        selection = _ALIASES.get(key)
        if selection is None:
            raise ValueError(
                f"Unknown service channel {service!r}. Choose notification, "
                "tts, snapcast, companion_tts or all; use integration/ "
                "device/ entity to choose recipients."
            )
        result.update(selection)
    return frozenset(result)


def filter_selected_outputs(
    selected: tuple[Sequence[str], Sequence[str], Sequence[str],
                    Sequence[str], Sequence[str]],
    services: Sequence[str],
) -> tuple[tuple[str, ...], ...]:
    """Drop unwanted channels but never append unselected devices.

    TTS engines are infrastructure only: retain one solely when an eligible
    direct or Snapcast physical recipient survives the channel filter.
    """
    allowed = channel_selection(services)
    engine, visual, direct, snapcast, companion = selected
    chosen_visual = tuple(visual) if VISUAL in allowed else ()
    chosen_direct = tuple(direct) if SPEECH in allowed else ()
    chosen_snapcast = tuple(snapcast) if SNAPCAST in allowed else ()
    chosen_companion = tuple(companion) if COMPANION in allowed else ()
    chosen_engine = (
        tuple(engine)[:1] if chosen_direct or chosen_snapcast else ()
    )
    return (
        chosen_engine, chosen_visual, chosen_direct, chosen_snapcast,
        chosen_companion,
    )


def physical_keys(
    selected: tuple[Sequence[str], Sequence[str], Sequence[str],
                    Sequence[str], Sequence[str]],
) -> tuple[str, ...]:
    """Canonical recipient keys for deduplication between union branches."""
    _, notify, direct, snapcast, companion = selected
    return tuple(dict.fromkeys((
        *(f"notify:{ref}" for ref in notify),
        *(f"room_tts:{id_}" for id_ in direct),
        *(f"snapcast:{id_}" for id_ in snapcast),
        *(f"companion_tts:{id_}" for id_ in companion),
    )))


def restrict_physical_keys(
    selected: tuple[Sequence[str], Sequence[str], Sequence[str],
                    Sequence[str], Sequence[str]],
    excluded: Iterable[str],
) -> tuple[tuple[str, ...], ...]:
    """Preserve all permitted recipients except static/room overlaps."""
    blocked = set(excluded)
    engine, notify, direct, snapcast, companion = selected
    kept_notify = tuple(x for x in notify if f"notify:{x}" not in blocked)
    kept_direct = tuple(x for x in direct if f"room_tts:{x}" not in blocked)
    kept_snap = tuple(x for x in snapcast if f"snapcast:{x}" not in blocked)
    kept_comp = tuple(x for x in companion if f"companion_tts:{x}" not in blocked)
    return (
        tuple(engine)[:1] if kept_direct or kept_snap else (),
        kept_notify, kept_direct, kept_snap, kept_comp,
    )
