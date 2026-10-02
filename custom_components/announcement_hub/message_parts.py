
"""Per-integration visual profiles, safe message splitting, and read timing."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping

from .const import (
    DEFAULT_MOBILE_APP_MAX_LENGTH,
    DEFAULT_NFANDROIDTV_COLOR,
    DEFAULT_NFANDROIDTV_FONTSIZE,
    DEFAULT_NFANDROIDTV_INTERRUPT,
    DEFAULT_NFANDROIDTV_MAX_LENGTH,
    DEFAULT_NFANDROIDTV_POSITION,
    DEFAULT_NFANDROIDTV_TRANSPARENCY,
    DEFAULT_NOTIFY_DISPLAY_BUFFER,
    DEFAULT_NOTIFY_MAX_DISPLAY,
    DEFAULT_NOTIFY_MAX_LENGTH,
    DEFAULT_NOTIFY_MIN_DISPLAY,
    DEFAULT_NOTIFY_PART_GAP,
    DEFAULT_NOTIFY_READING_WPM,
    DEFAULT_NOTIFY_REPLACE_PARTS,
    DEFAULT_NOTIFY_SHOW_PART_NUMBER,
    INTEGRATION_MOBILE_APP,
    INTEGRATION_NFANDROIDTV,
    NFANDROIDTV_COLORS,
    NFANDROIDTV_FONTSIZES,
    NFANDROIDTV_POSITIONS,
    NFANDROIDTV_TRANSPARENCIES,
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
)

_WORD_RE = re.compile(r"[^\W_]+(?:[’'\-][^\W_]+)*", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")
_SENTENCE_ENDINGS = frozenset(".!?")
_CLAUSE_ENDINGS = frozenset(",;:")


def integration_label(integration: str) -> str:
    """Return a friendly name for a profile key."""
    if integration == INTEGRATION_NFANDROIDTV:
        return "Notifications for Android TV / Fire TV"
    if integration == INTEGRATION_MOBILE_APP:
        return "Home Assistant Companion App"
    if integration == PROFILE_DEFAULT:
        return "Other / generic notification outputs"
    return integration.replace("_", " ").title()


def default_notify_profile(integration: str) -> dict[str, Any]:
    """Return provider-aware defaults without sharing mutable dictionaries."""
    max_length = DEFAULT_NOTIFY_MAX_LENGTH
    if integration == INTEGRATION_NFANDROIDTV:
        max_length = DEFAULT_NFANDROIDTV_MAX_LENGTH
    elif integration == INTEGRATION_MOBILE_APP:
        max_length = DEFAULT_MOBILE_APP_MAX_LENGTH

    profile: dict[str, Any] = {
        PROFILE_MAX_LENGTH: max_length,
        PROFILE_READING_WPM: DEFAULT_NOTIFY_READING_WPM,
        PROFILE_MIN_DISPLAY: DEFAULT_NOTIFY_MIN_DISPLAY,
        PROFILE_MAX_DISPLAY: DEFAULT_NOTIFY_MAX_DISPLAY,
        PROFILE_DISPLAY_BUFFER: DEFAULT_NOTIFY_DISPLAY_BUFFER,
        PROFILE_PART_GAP: DEFAULT_NOTIFY_PART_GAP,
        PROFILE_SHOW_PART_NUMBER: DEFAULT_NOTIFY_SHOW_PART_NUMBER,
        PROFILE_INTEGRATION_DATA: {},
    }
    if integration == INTEGRATION_NFANDROIDTV:
        profile.update(
            {
                PROFILE_NF_POSITION: DEFAULT_NFANDROIDTV_POSITION,
                PROFILE_NF_FONTSIZE: DEFAULT_NFANDROIDTV_FONTSIZE,
                PROFILE_NF_COLOR: DEFAULT_NFANDROIDTV_COLOR,
                PROFILE_NF_TRANSPARENCY: DEFAULT_NFANDROIDTV_TRANSPARENCY,
                PROFILE_NF_INTERRUPT: DEFAULT_NFANDROIDTV_INTERRUPT,
            }
        )
    elif integration == INTEGRATION_MOBILE_APP:
        profile[PROFILE_REPLACE_PARTS] = DEFAULT_NOTIFY_REPLACE_PARTS
    return profile


def _number(value: Any, default: float, *, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(value))
    except (TypeError, ValueError):
        return float(default)


def normalise_notify_profile(
    profile: Mapping[str, Any] | None,
    integration: str,
) -> dict[str, Any]:
    """Merge and validate one profile into a durable JSON-compatible dict."""
    result = default_notify_profile(integration)
    if profile:
        for key, value in profile.items():
            result[str(key)] = deepcopy(value)

    result[PROFILE_MAX_LENGTH] = max(
        0, int(_number(result.get(PROFILE_MAX_LENGTH), 0))
    )
    result[PROFILE_READING_WPM] = _number(
        result.get(PROFILE_READING_WPM), DEFAULT_NOTIFY_READING_WPM, minimum=1
    )
    result[PROFILE_MIN_DISPLAY] = _number(
        result.get(PROFILE_MIN_DISPLAY), DEFAULT_NOTIFY_MIN_DISPLAY
    )
    result[PROFILE_MAX_DISPLAY] = max(
        result[PROFILE_MIN_DISPLAY],
        _number(result.get(PROFILE_MAX_DISPLAY), DEFAULT_NOTIFY_MAX_DISPLAY),
    )
    result[PROFILE_DISPLAY_BUFFER] = _number(
        result.get(PROFILE_DISPLAY_BUFFER), DEFAULT_NOTIFY_DISPLAY_BUFFER
    )
    result[PROFILE_PART_GAP] = _number(
        result.get(PROFILE_PART_GAP), DEFAULT_NOTIFY_PART_GAP
    )
    result[PROFILE_SHOW_PART_NUMBER] = bool(
        result.get(PROFILE_SHOW_PART_NUMBER, DEFAULT_NOTIFY_SHOW_PART_NUMBER)
    )
    integration_data = result.get(PROFILE_INTEGRATION_DATA, {})
    result[PROFILE_INTEGRATION_DATA] = (
        deepcopy(dict(integration_data))
        if isinstance(integration_data, Mapping)
        else {}
    )

    if integration == INTEGRATION_NFANDROIDTV:
        if result.get(PROFILE_NF_POSITION) not in NFANDROIDTV_POSITIONS:
            result[PROFILE_NF_POSITION] = DEFAULT_NFANDROIDTV_POSITION
        if result.get(PROFILE_NF_FONTSIZE) not in NFANDROIDTV_FONTSIZES:
            result[PROFILE_NF_FONTSIZE] = DEFAULT_NFANDROIDTV_FONTSIZE
        if result.get(PROFILE_NF_COLOR) not in NFANDROIDTV_COLORS:
            result[PROFILE_NF_COLOR] = DEFAULT_NFANDROIDTV_COLOR
        if result.get(PROFILE_NF_TRANSPARENCY) not in NFANDROIDTV_TRANSPARENCIES:
            result[PROFILE_NF_TRANSPARENCY] = DEFAULT_NFANDROIDTV_TRANSPARENCY
        result[PROFILE_NF_INTERRUPT] = bool(
            result.get(PROFILE_NF_INTERRUPT, DEFAULT_NFANDROIDTV_INTERRUPT)
        )
    elif integration == INTEGRATION_MOBILE_APP:
        result[PROFILE_REPLACE_PARTS] = bool(
            result.get(PROFILE_REPLACE_PARTS, DEFAULT_NOTIFY_REPLACE_PARTS)
        )
    return result


def resolve_notify_profile(
    profiles: Mapping[str, Any] | None,
    integration: str | None,
) -> dict[str, Any]:
    """Resolve an integration profile with a generic fallback."""
    key = integration or PROFILE_DEFAULT
    raw: Mapping[str, Any] | None = None
    if isinstance(profiles, Mapping):
        candidate = profiles.get(key)
        if not isinstance(candidate, Mapping) and key != PROFILE_DEFAULT:
            candidate = profiles.get(PROFILE_DEFAULT)
        if isinstance(candidate, Mapping):
            raw = candidate
    return normalise_notify_profile(raw, key)


def normalise_visual_text(text: str) -> str:
    """Collapse transport-hostile whitespace while preserving punctuation."""
    value = str(text).replace("\\n", " ").replace("\\r", " ")
    return _SPACE_RE.sub(" ", value).strip()


def _last_boundary(text: str, limit: int, endings: frozenset[str]) -> int | None:
    """Return the end index immediately after the last punctuation boundary."""
    upper = min(limit, len(text))
    for index in range(upper, 0, -1):
        if text[index - 1] not in endings:
            continue
        if index == len(text) or text[index].isspace():
            return index
    return None


def _last_whitespace(text: str, limit: int) -> int | None:
    upper = min(limit, len(text))
    for index in range(upper, 0, -1):
        if text[index - 1].isspace():
            return index - 1
    return None


def split_message(text: str, max_length: int) -> list[str]:
    """Split text without cutting words when a natural boundary is available.

    Sentence endings are preferred, then commas/clauses, then whitespace. A
    hard character cut is used only for a single token longer than the limit.
    """
    remaining = normalise_visual_text(text)
    if not remaining:
        return []
    limit = int(max_length or 0)
    if limit <= 0 or len(remaining) <= limit:
        return [remaining]

    parts: list[str] = []
    while len(remaining) > limit:
        split_at = _last_boundary(remaining, limit, _SENTENCE_ENDINGS)
        if split_at is None:
            split_at = _last_boundary(remaining, limit, _CLAUSE_ENDINGS)
        if split_at is None:
            split_at = _last_whitespace(remaining, limit)
        if split_at is None or split_at <= 0:
            split_at = limit

        part = remaining[:split_at].strip()
        if not part:
            split_at = min(limit, len(remaining))
            part = remaining[:split_at]
        parts.append(part)
        remaining = remaining[split_at:].lstrip()

    if remaining:
        parts.append(remaining)
    return parts


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(str(text)))


def reading_seconds(
    text: str,
    *,
    words_per_minute: float,
    minimum_seconds: float,
    maximum_seconds: float,
    buffer_seconds: float,
) -> float:
    """Estimate reading time from words and clamp it to configured bounds."""
    words = max(1, word_count(text))
    wpm = max(1.0, float(words_per_minute))
    estimate = words / wpm * 60.0 + max(0.0, float(buffer_seconds))
    minimum = max(0.0, float(minimum_seconds))
    maximum = max(minimum, float(maximum_seconds))
    return min(max(estimate, minimum), maximum)


def format_part_title(
    title: str | None,
    *,
    index: int,
    total: int,
    show_part_number: bool,
) -> str | None:
    if total <= 1 or not show_part_number:
        return title
    suffix = f"{index}/{total}"
    return f"{title} · {suffix}" if title else suffix
