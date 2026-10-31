"""Bounded, in-memory reuse of identical completed AI requests.

Only successful generations are eligible. No source prompts, generated output,
AI credentials, or result-cache state are persisted or logged. Each queued
announcement retains its own recipients, routing, and delivery receipts.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class CachedAIResult:
    """A completed response for one exact, context-qualified AI request."""

    tts: str | None
    notify: str | None
    title: str | None
    agent_used: str | None


def fingerprint(
    *,
    original_tts: str | None,
    original_notify: str | None,
    requested_agent: str | None,
    fallback_agent: str | None,
    mode: str,
    language: str | None,
    generate_title: bool,
    prompt_templates: Any,
    ha_language: str | None = None,
) -> str:
    """Digest exact generation inputs so prompts are never cache keys."""
    payload = {
        "tts": original_tts,
        "notify": original_notify,
        "agent": requested_agent,
        "backup": fallback_agent,
        "mode": mode,
        "language": language,
        "title": bool(generate_title),
        "styles": prompt_templates,
        "ha_language": ha_language,
    }
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AIResultCache:
    """Use only verified completed results with bounded TTL and entry count."""

    def __init__(
        self, *, max_entries: int = 128, ttl_seconds: float = 900.0
    ) -> None:
        self._cache: OrderedDict[str, tuple[float, CachedAIResult]] = OrderedDict()
        self._max_entries = max(1, int(max_entries))
        self._ttl = max(1.0, float(ttl_seconds))

    def get(self, key: str) -> CachedAIResult | None:
        now = time.monotonic()
        record = self._cache.get(key)
        if record is None:
            return None
        created, result = record
        if now - created > self._ttl:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return result

    def put(self, key: str, result: CachedAIResult) -> None:
        self._cache[key] = (time.monotonic(), result)
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()
