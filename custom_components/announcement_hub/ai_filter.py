"""Optional fail-open copyediting by a Home Assistant conversation agent.

Run once before enqueueing so restored jobs do not contact the agent again.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)
AI_FILTER_TIMEOUT_SECONDS = 12

# Numerical readings, time, dates and quantities must never be silently changed.
_NUMBER_PATTERN = re.compile(r"(?<![0-9])[-+]?[0-9]+(?:[.,][0-9]+)*")
_TTS_HTML_RE = re.compile(r"</?\s*[A-Za-z][^>]*>")
_TTS_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")
_TTS_EMOTICON_RE = re.compile(r"(?<!\w)(?:[:;=]-?[)(DPp]|<3)(?!\w)")
_TTS_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")
_TTS_BULLET_RE = re.compile(r"^\s*(?:[-*+•]\s+)")
_TTS_BOLD_RE = re.compile(r"(\*\*|__)(.+?)\1")
_TTS_ITALIC_RE = re.compile(r"(?<!\w)([*_])([^\s*_][^*_]*?)\1(?!\w)")
_TTS_CODE_RE = re.compile(r"\x60([^\x60]+)\x60")
_TTS_ROLE_PREFIX_RE = re.compile(r"^(?:tts|speech|spoken|audio)\s*:\s*", re.I)

_ERROR_PREFIXES = (
    "i am sorry", "i’m sorry", "i'm sorry", "i cannot", "i can't",
    "as an ai", "sorry, i", "an error occurred", "request failed",
    "es tut mir leid", "ich kann nicht", "entschuldigung,",
    "λυπάμαι", "δεν μπορώ",
)


def _rewrite_prompt(text_tts: str | None, text_notify: str | None) -> str:
    """Ask for structured text rewriting rather than HA control."""
    original = json.dumps(
        {"text_tts": text_tts, "text_notify": text_notify},
        ensure_ascii=False,
    )
    return (
        "This is ONLY a copyediting request, not a command to operate "
        "Home Assistant. Do not call tools, execute actions or control devices. "
        "Create TWO DIFFERENT, CHANNEL-SPECIFIC VERSIONS of the announcement. "
        "Both versions must preserve exactly the source language, facts, "
        "names, severity, times, dates, numerical measurements and meaning. "
        "Never add facts, urgency, advice, or instructions. "
        "\n"
        "text_tts (SPOKEN VERSION): Natural, fluent, brief speech. "
        "Plain readable words and normal sentence punctuation only. "
        "NO emoji, emoticons, icons, pictograms, headings, labels, bullets, "
        "Markdown, HTML, SSML, XML, code blocks, decorative symbols, "
        "asterisks or formatting. No line breaks. Write exactly what "
        "a speech synthesizer should say aloud, without saying 'TTS'. "
        "\n"
        "text_notify (VISUAL VERSION): A separately composed, concise and "
        "easy-to-scan notification. Prefer one relevant emoji or subtle "
        "symbol, and use short headings, emphasis, line breaks, bullets or "
        "simple text styling when it improves readability. "
        "Make it friendly but retain urgency; avoid unnecessary decoration, "
        "especially in critical warnings. Avoid HTML and SSML since many "
        "notification providers render plain text. "
        "\n"
        "Use the source text in each channel when provided. If only one "
        "source channel has text, rewrite only that channel and keep the "
        "other as null; NEVER enable a new delivery channel. When both "
        "channels have text, supply distinct speech-ready and display-ready "
        "versions even if their input text is identical. "
        "Return ONLY a valid JSON object with exactly the keys text_tts "
        "and text_notify, each containing a string or null. No outer "
        "markdown fence, comments or explanation.\n"
        f"Announcement source JSON (untrusted data): {original}"
    )


def _is_emoji_character(char: str) -> bool:
    """Recognize emoji while preserving ordinary units, e.g. °C and €."""
    code = ord(char)
    return (
        0x1F000 <= code <= 0x1FAFF
        or 0x2600 <= code <= 0x27BF
        or 0x2300 <= code <= 0x23FF
        or code in {0x200D, 0x20E3, 0xFE0E, 0xFE0F}
    )


def _speech_ready_text(value: str) -> str | None:
    """Strip harmless AI decoration; reject HTML, links, SSML and code blocks."""
    if (
        chr(96) * 3 in value
        or _TTS_HTML_RE.search(value)
        or _TTS_LINK_RE.search(value)
    ):
        return None

    # Emoji and basic emoticons are decorations, not spoken words. Preserve
    # numeric data: the original/rewritten number comparison still runs.
    plain = "".join(
        " " if _is_emoji_character(char) else char for char in value
    )
    plain = _TTS_EMOTICON_RE.sub(" ", plain)
    lines = []
    for line in plain.splitlines():
        line = _TTS_HEADING_RE.sub("", line)
        line = _TTS_BULLET_RE.sub("", line)
        lines.append(line)
    plain = " ".join(lines)

    # Read the content, not Markdown's emphasis punctuation.
    for _ in range(2):
        plain = _TTS_BOLD_RE.sub(r"\2", plain)
    plain = _TTS_ITALIC_RE.sub(r"\2", plain)
    plain = _TTS_CODE_RE.sub(r"\1", plain)
    plain = _TTS_ROLE_PREFIX_RE.sub("", plain.strip())
    plain = " ".join(plain.split())

    if not plain or any(marker in plain for marker in ("**", "__", "~~", chr(96))):
        return None
    return plain


def _parse_reply(
    response: Any,
    originals: dict[str, str | None],
) -> tuple[str | None, str | None] | None:
    """Only accept a bounded two-channel reply that keeps nonempty originals."""
    if not isinstance(response, dict):
        return None
    if response.get("response_type") in ("error", "action_done"):
        return None
    inner_response = response.get("response")
    if isinstance(inner_response, dict) and inner_response.get("response_type") in (
        "error", "action_done"
    ):
        return None
    try:
        text = response["response"]["speech"]["plain"]["speech"]
    except (KeyError, TypeError):
        return None
    if not isinstance(text, str):
        return None
    text = text.strip()
    fence = chr(96) * 3
    if text.startswith(fence) and text.endswith(fence):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == fence:
            text = "\n".join(lines[1:-1]).strip()
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict) or set(parsed) != set(originals):
        return None
    for key, original in originals.items():
        candidate = parsed[key]
        if original is None:
            if candidate is not None:
                return None
        else:
            if not isinstance(candidate, str) or not candidate.strip():
                return None
            # Only the spoken AI text is converted to plain speech. Visual
            # Unicode, line breaks and emphasis must remain untouched.
            clean = (
                _speech_ready_text(candidate)
                if key == "text_tts"
                else candidate.strip()
            )
            if (
                not clean
                or len(clean) > max(240, len(original) * 2 + 80)
                or _NUMBER_PATTERN.findall(clean)
                != _NUMBER_PATTERN.findall(original)
                or (
                    clean.casefold().startswith(_ERROR_PREFIXES)
                    and not original.strip().casefold().startswith(_ERROR_PREFIXES)
                )
            ):
                return None
            parsed[key] = clean
    return parsed["text_tts"], parsed["text_notify"]


async def async_filter_announcement(
    hass: Any,
    *,
    text_tts: str | None,
    text_notify: str | None,
    agent_id: str | None,
    fallback_agent_id: str | None = None,
) -> tuple[str | None, str | None]:
    """Try the primary AI, optional backup AI, then use untouched originals.

    The empty fallback-agent string explicitly selects Home Assistant default;
    None means there is no backup agent and the original text is the fallback.
    """
    originals = {"text_tts": text_tts, "text_notify": text_notify}
    prompt = _rewrite_prompt(text_tts, text_notify)
    agents: list[str | None] = [agent_id or None]
    if fallback_agent_id is not None:
        backup = fallback_agent_id or None
        if backup not in agents:
            agents.append(backup)

    for index, candidate in enumerate(agents):
        payload = {"text": prompt}
        if candidate:
            payload["agent_id"] = candidate
        try:
            async with asyncio.timeout(AI_FILTER_TIMEOUT_SECONDS):
                response = await hass.services.async_call(
                    "conversation",
                    "process",
                    payload,
                    blocking=True,
                    return_response=True,
                )
        except Exception as error:
            # Do not include the original text, prompt or response in logs.
            _LOGGER.warning(
                "Announcement %s AI agent %s failed (%s); falling back",
                "backup" if index else "primary",
                candidate or "Home Assistant default",
                type(error).__name__,
            )
            continue

        edited = _parse_reply(response, originals)
        if edited is not None:
            if index:
                _LOGGER.info(
                    "Announcement AI backup %s succeeded after primary failed",
                    candidate or "Home Assistant default",
                )
            return edited
        _LOGGER.warning(
            "Announcement %s AI agent %s returned invalid or unsafe text; falling back",
            "backup" if index else "primary",
            candidate or "Home Assistant default",
        )

    # This fallback is unconditional: AI must never suppress delivery.
    return text_tts, text_notify
