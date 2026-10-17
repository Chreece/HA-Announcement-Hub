"""Resolve optional per-action AI overrides without losing integration defaults.

When 'use_ai' is omitted, it is None; explicit False disables AI only for
that announcement. Normalize legacy textual config values without treating
the string "false" as truthy.
"""

from __future__ import annotations

from typing import Any


def resolve_ai_enabled(
    configured: Any, override: bool | None
) -> tuple[bool, str]:
    """Return effective AI enablement and its configuration origin."""
    if override is not None:
        return override, "action"
    if isinstance(configured, bool):
        return configured, "integration"
    if isinstance(configured, str):
        return configured.strip().casefold() in {
            "1", "true", "yes", "on"
        }, "integration"
    return bool(configured) if configured is not None else False, "integration"
