"""Resolve one shared announcement text into spoken and visual variants.

The new primary `text` field is the fallback for each channel. Existing
automations that supply only text_tts and/or text_notify remain valid, and
preserve their original channel-specific semantics.
"""

from __future__ import annotations


def _nonempty(value: str | None) -> str | None:
    """Trim whitespace and treat empty optional overrides as absent."""
    if not isinstance(value, str):
        return None
    return value.strip() or None


def resolve_channel_texts(
    text: str | None,
    text_tts: str | None,
    text_notify: str | None,
) -> tuple[str | None, str | None]:
    """Use optional channel variants first, then fall back to common text.

    A single `text` becomes the source for both eligible channels. When an
    override is supplied, it replaces the common source only in that channel.
    With no common text the historic channel-only behavior is unchanged.
    The delivery planner still controls which physical outputs may be used.
    """
    common = _nonempty(text)
    return _nonempty(text_tts) or common, _nonempty(text_notify) or common
