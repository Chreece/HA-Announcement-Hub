"""Persistence-safe, ordered room announcement fallback decisions.

Missing configured targets advance immediately; unavailable configured
targets retain priority for the configured grace period. Exhausted tiers
leave the announcement queued until a compatible output becomes available.
"""

from __future__ import annotations

from datetime import UTC, datetime

STAGES = ("explicit", "occupied", "fallback_room", "general", "waiting")


def next_stage(stage: str) -> str:
    """Advance one tier without wrapping or jumping to unrelated rooms."""
    try:
        index = STAGES.index(stage)
    except ValueError:
        return STAGES[0]
    return STAGES[min(index + 1, len(STAGES) - 1)]


def elapsed_seconds(since: str | None, now: datetime | None = None) -> float:
    """Duration elapsed on the current routing tier; survives restarts."""
    if not since:
        return 0.0
    try:
        begin = datetime.fromisoformat(since)
        if begin.tzinfo is None:
            begin = begin.replace(tzinfo=UTC)
        return max(0.0, ((now or datetime.now(UTC)) - begin).total_seconds())
    except (ValueError, TypeError):
        return 0.0


def remaining_grace(since: str | None, timeout: float) -> float:
    """Nonnegative seconds left for the current tier."""
    return max(0.0, max(0.0, timeout) - elapsed_seconds(since))
