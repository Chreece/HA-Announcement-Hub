"""Optional fail-open copyediting by Home Assistant conversation or AI Task.

Run once before enqueueing so restored jobs do not contact the agent again.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)
# Advisory log interval only: model cold starts are not AI failures.
# Home Assistant conversation.process has no portable generation-progress API.
AI_FILTER_SLOW_REQUEST_SECONDS = 60.0

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


def _generate_prompt(
    text_tts: str | None,
    text_notify: str | None,
    *,
    generate_title: bool = False,
) -> str:
    """Create actual announcements and, when requested, a short visual title."""
    original = json.dumps(
        {"text_tts": text_tts, "text_notify": text_notify},
        ensure_ascii=False,
    )
    title_rule = (
        "Also write a descriptive notification title in the same language, "
        "with ONE TO THREE WORDS maximum, without emoji, markdown, links, "
        "or labels. Include it in the JSON as the string key title. "
        if generate_title else ""
    )
    output_keys = (
        "text_tts, text_notify and title"
        if generate_title else "text_tts and text_notify"
    )
    return (
        "You are WRITING THE ANNOUNCEMENT described by the input, not "
        "copyediting an existing message. The input contains writing "
        "INSTRUCTIONS, NOT words to read aloud. NEVER operate Home Assistant, "
        "invoke tools or perform any action. Only draft text. "
        "Use only the supplied data, including real device readings and events. "
        "Do not invent facts, times, measurements, people or emergencies. "
        "Respect the source language and requested tone; for serious warnings "
        "avoid humor. Preserve essential factual details. "
        "For text_tts: natural concise spoken prose only, no emoji, markdown, "
        "formatting, HTML or links. "
        "For text_notify: independently composed, readable visual notification "
        "with restrained emoji/styling when useful. "
        "If a source channel is null, output null for it too. NEVER enable an "
        "unrequested channel. Do not include phrases such as 'write a summary', "
        "'tell the user', or 'here is the announcement': output the finished "
        "content, not an explanation of the instruction. "
        f"{title_rule}"
        f"Return ONLY valid JSON with exactly these keys: {output_keys}. "
        "text_tts and text_notify must each be a string or null. "
        "No code fence or other text. "
        f"Untrusted writing instructions JSON: {original}"
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


def _short_generated_title(value: Any) -> str | None:
    """Keep generated titles plain, compact and at most three words.

    Never use a model title as markup or a link. Truncate an otherwise
    acceptable longer title rather than losing the generated announcement.
    Unicode whitespace separation supports the installed Greek/German voices.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    clean = _speech_ready_text(value)
    if not clean or "://" in clean or clean.startswith("www."):
        return None
    words = clean.strip(" :;|-").split()
    if not words:
        return None
    title = " ".join(words[:3])
    return title if len(title) <= 90 else None


def _parse_reply(
    response: Any,
    originals: dict[str, str | None],
    *,
    generate: bool = False,
    title_result: dict[str, str] | None = None,
) -> tuple[str | None, str | None] | None:
    """Only accept a bounded two-channel reply that keeps nonempty originals."""
    if not isinstance(response, dict):
        return None
    if response.get("response_type") in ("error", "action_done"):
        return None
    inner_response = response.get("response")
    if isinstance(inner_response, dict):
        kind = inner_response.get("response_type")
        if kind == "error":
            return None
        if kind == "action_done":
            # HA's IntentResponse defaults to action_done even when an LLM
            # only sets speech. A response with no successful/failed action
            # targets may still be a valid text-only AI answer.
            data = inner_response.get("data")
            if (
                not isinstance(data, dict)
                or set(data) - {"success", "failed"}
                or data.get("success")
                or data.get("failed")
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
    expected_keys = set(originals)
    if not isinstance(parsed, dict):
        return None
    if (
        set(parsed) != expected_keys
        and not (
            generate
            and title_result is not None
            and set(parsed) == expected_keys | {"title"}
        )
    ):
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
                or len(clean) > (
                    min(4000, max(400, len(original) * 3 + 160))
                    if generate else max(240, len(original) * 2 + 80)
                )
                or (
                    not generate
                    and _NUMBER_PATTERN.findall(clean)
                    != _NUMBER_PATTERN.findall(original)
                )
                or (
                    clean.casefold().startswith(_ERROR_PREFIXES)
                    and not original.strip().casefold().startswith(_ERROR_PREFIXES)
                )
            ):
                return None
            parsed[key] = clean
    if generate and title_result is not None:
        title = _short_generated_title(parsed.get("title"))
        if title:
            title_result["title"] = title
    return parsed["text_tts"], parsed["text_notify"]


def _failure_reason(response: Any) -> str:
    """Classify expected HA intent errors without revealing response content."""
    if not isinstance(response, dict):
        return "invalid_response"
    details = response.get("response")
    if not isinstance(details, dict):
        return "invalid_response"
    kind = details.get("response_type")
    if kind == "action_done":
        return "action_response_not_allowed"
    if kind == "error":
        payload = details.get("data")
        if isinstance(payload, dict) and payload.get("code") in {
            "no_intent_match",
            "no_valid_targets",
            "failed_to_handle",
        }:
            return str(payload["code"])
        return "agent_error_response"
    return "invalid_response"


# A selected "default" means the preferred Assist pipeline, not the built-in
# conversation.process default, which handles commands but not freeform rewriting.
PREFERRED_ASSIST_AGENT = "default"
HOME_ASSISTANT_INTENT_AGENT = "conversation.home_assistant"


def resolve_preferred_assist_agent(
    hass: Any,
) -> tuple[str | None, str | None, str | None]:
    """Resolve the current preferred Assist pipeline's conversation engine.

    The preferred pipeline can change without reconfiguring Announcement Hub.
    Never silently call conversation.process without an agent_id when the
    user requested the preferred agent: omitted agent_id targets the built-in
    intent-only Home Assistant agent, NOT the pipeline's configured LLM.
    """
    try:
        from homeassistant.components.assist_pipeline import async_get_pipeline

        pipeline = async_get_pipeline(hass)
    except Exception as error:  # noqa: BLE001
        _LOGGER.debug(
            "Announcement AI preferred Assist pipeline cannot be resolved (%s)",
            type(error).__name__,
        )
        return None, None, "preferred_assist_pipeline_unavailable"

    engine = getattr(pipeline, "conversation_engine", None)
    if not isinstance(engine, str) or not engine:
        return None, None, "preferred_assist_agent_unavailable"
    if engine == HOME_ASSISTANT_INTENT_AGENT:
        return None, None, "preferred_assist_agent_not_generative"
    language = getattr(pipeline, "conversation_language", None)
    if not isinstance(language, str) or not language.strip():
        language = None
    return engine, language, None


async def async_filter_announcement(
    hass: Any,
    *,
    text_tts: str | None,
    text_notify: str | None,
    agent_id: str | None,
    fallback_agent_id: str | None = None,
    diagnostics: dict[str, Any] | None = None,
    mode: str = "rewrite",
    title_result: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    """Try the configured AI, optional backup AI, then untouched originals.

    The string "default" follows the preferred Assist pipeline at send time.
    A legacy None or empty string still targets the built-in conversation
    agent for compatibility with direct helper callers; the manager no longer
    passes None when the default dropdown is selected.
    """
    if mode not in {"rewrite", "generate"}:
        raise ValueError("AI mode must be rewrite or generate")
    originals = {"text_tts": text_tts, "text_notify": text_notify}
    if title_result is not None:
        title_result.clear()
    # Status goes into the action response, never raw prompts or message text.
    if diagnostics is not None:
        diagnostics.update(
            {
                "attempted": False,
                "status": "fallback_original",
                "agent_used": None,
                "attempts": [],
                "failure_reason": None,
            }
        )
    prompt = (
        _generate_prompt(
            text_tts, text_notify, generate_title=title_result is not None
        )
        if mode == "generate"
        else _rewrite_prompt(text_tts, text_notify)
    )
    agents: list[str | None] = [agent_id or None]
    if fallback_agent_id is not None:
        backup = fallback_agent_id or None
        if backup not in agents:
            agents.append(backup)

    called_agents: set[str | None] = set()
    for index, chosen_agent in enumerate(agents):
        candidate = chosen_agent
        preferred_language: str | None = None
        if chosen_agent == PREFERRED_ASSIST_AGENT:
            candidate, preferred_language, resolve_error = (
                resolve_preferred_assist_agent(hass)
            )
            if resolve_error:
                if diagnostics is not None:
                    diagnostics["attempts"].append(
                        {"agent": "Preferred Assist pipeline", "outcome": resolve_error}
                    )
                    diagnostics["failure_reason"] = resolve_error
                    if index == 0:
                        diagnostics["agent"] = "Preferred Assist pipeline"
                _LOGGER.warning(
                    "Announcement %s AI cannot resolve a generative agent from "
                    "the preferred Assist pipeline (%s); using fallback",
                    "backup" if index else "primary",
                    resolve_error,
                )
                continue

        # A backup pointing to the same effective agent is not a useful retry.
        if candidate in called_agents:
            continue
        called_agents.add(candidate)
        agent_label = candidate or "Home Assistant built-in"
        if diagnostics is not None:
            diagnostics["attempted"] = True
            if index == 0:
                diagnostics["agent"] = agent_label
        is_ai_task = isinstance(candidate, str) and candidate.startswith("ai_task.")
        if is_ai_task:
            payload = {
                "task_name": "Announcement Hub announcement",
                "instructions": prompt,
                "entity_id": candidate,
            }
        else:
            payload = {"text": prompt}
            if candidate:
                payload["agent_id"] = candidate
            if preferred_language:
                payload["language"] = preferred_language
        # Await the *same* in-flight request for as long as the agent needs.
        # Do not cancel generation just because a local model is loading.
        loop = asyncio.get_running_loop()
        attempt_started = loop.time()
        pending_notice = loop.call_later(
            AI_FILTER_SLOW_REQUEST_SECONDS,
            _LOGGER.warning,
            "Announcement AI agent %s has not responded after %.0f seconds; "
            "continuing to await AI provider (no Hub timeout)",
            agent_label,
            AI_FILTER_SLOW_REQUEST_SECONDS,
        )
        try:
            response = await hass.services.async_call(
                "ai_task" if is_ai_task else "conversation",
                "generate_data" if is_ai_task else "process",
                payload,
                blocking=True,
                return_response=True,
            )
        except Exception as error:
            # Error class only: never return provider secrets or original text.
            # A TimeoutError raised by the provider itself is different from
            # Hub cancelling an otherwise active request (which we never do).
            reason = (
                "provider_timeout"
                if isinstance(error, TimeoutError) else "agent_error"
            )
            if diagnostics is not None:
                diagnostics["attempts"].append(
                    {"agent": agent_label, "outcome": reason}
                )
                diagnostics["failure_reason"] = reason
            _LOGGER.warning(
                "Announcement %s AI agent %s failed (%s); falling back",
                "backup" if index else "primary",
                agent_label,
                type(error).__name__,
            )
            continue
        finally:
            pending_notice.cancel()
            if diagnostics is not None:
                diagnostics.setdefault("attempt_duration_seconds", {})[
                    agent_label
                ] = round(loop.time() - attempt_started, 3)

        # AI Task returns {"data": generated_text}; normalize only this
        # provider's response and retain all existing safety checks.
        if is_ai_task and isinstance(response, dict):
            data = response.get("data")
            if isinstance(data, dict):
                data = json.dumps(data, ensure_ascii=False)
            if isinstance(data, str):
                response = {"response": {"speech": {"plain": {"speech": data}}}}
        try:
            edited = _parse_reply(
                response, originals, generate=(mode == "generate"),
                title_result=title_result if mode == "generate" else None,
            )
        except Exception:  # noqa: BLE001
            # A surprising provider response must not block delivery.
            _LOGGER.exception(
                "Announcement AI result validation failed; using fallback"
            )
            edited = None
        if edited is not None:
            if diagnostics is not None:
                status = (
                    "rewritten"
                    if (
                        edited != (text_tts, text_notify)
                        or (mode == "generate" and bool(title_result))
                    )
                    else "accepted_unchanged"
                )
                diagnostics["status"] = status
                diagnostics["agent_used"] = agent_label
                diagnostics["failure_reason"] = None
                diagnostics["attempts"].append(
                    {"agent": agent_label, "outcome": status}
                )
            if index:
                _LOGGER.info(
                    "Announcement AI backup %s succeeded after primary failed",
                    agent_label,
                )
            return edited
        if diagnostics is not None:
            reason = _failure_reason(response)
            diagnostics["attempts"].append(
                {"agent": agent_label, "outcome": reason}
            )
            diagnostics["failure_reason"] = reason
        _LOGGER.warning(
            "Announcement %s AI agent %s returned invalid or unsafe text; falling back",
            "backup" if index else "primary",
            agent_label,
        )

    # This fallback is unconditional: AI must never suppress delivery.
    return text_tts, text_notify
