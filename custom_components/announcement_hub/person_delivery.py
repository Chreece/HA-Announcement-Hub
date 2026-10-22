"""Strict per-person delivery choices, identity greetings and presence policy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

def personalized_text(value: str | None, name: str, *, prepend: bool = False) -> str | None:
    """Replace only documented literal tokens, never render HA templates."""
    if value is None:
        return None
    safe_name = str(name or "").strip().replace("\n", " ")[:80]
    has_placeholder = "{{ name }}" in value or "{{name}}" in value
    translated = value.replace("{{ name }}", safe_name).replace("{{name}}", safe_name)
    if prepend and not has_placeholder and safe_name and translated.strip():
        translated = f"{safe_name}, {translated}"
    return translated

def person_is_enabled(profile: Any) -> bool:
    return not isinstance(profile, Mapping) or profile.get("enabled", True) is not False

def presence_confirmed(states: Any, sensor_id: str | None) -> bool:
    """Only a positive on value verifies presence; stale/missing fails closed."""
    if not sensor_id:
        return False
    state = states.get(sensor_id)
    return state is not None and str(state.state).casefold() in {"on", "home", "occupied", "true"}

def allowed_person_ai(
    *,
    requested_enabled: bool | None,
    configured_rewrite: bool,
    should_translate: bool,
) -> tuple[bool | None, str]:
    """Action overrides > profile: keep translation independent of rewriting."""
    if requested_enabled is False:
        return False, "rewrite"
    if requested_enabled is True:
        return True, "rewrite"
    if should_translate and not configured_rewrite:
        return True, "translate"
    if configured_rewrite:
        return True, "rewrite"
    return None, "rewrite"
