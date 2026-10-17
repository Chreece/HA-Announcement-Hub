"""Optional AI rewriting behavior and configuration/action contracts."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"

spec = importlib.util.spec_from_file_location(
    "announcement_hub_ai_filter_test",
    COMPONENT / "ai_filter.py",
)
assert spec is not None and spec.loader is not None
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)


class Services:
    def __init__(self, response=None, error=None, responses=None):
        self.response = response
        self.error = error
        self.responses = None if responses is None else list(responses)
        self.calls = []

    async def async_call(self, domain, service, payload, **kwargs):
        self.calls.append((domain, service, payload, kwargs))
        if self.error is not None:
            raise self.error
        if self.responses is not None:
            result = self.responses.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        return self.response


class Hass:
    def __init__(self, response=None, error=None, responses=None):
        self.services = Services(response, error, responses)


def ha_reply(tts, notify):
    return {
        "response": {
            "speech": {
                "plain": {
                    "speech": json.dumps(
                        {"text_tts": tts, "text_notify": notify},
                        ensure_ascii=False,
                    ),
                },
            },
        },
    }


def test_rewrites_both_channels_using_ha_default() -> None:
    hass = Hass(ha_reply("Die Wäsche ist fertig.", "Waschgang beendet"))
    result = asyncio.run(
        ai.async_filter_announcement(
            hass,
            text_tts="Die Wäsche ist fertig",
            text_notify="Waschgang beendet",
            agent_id=None,
        )
    )
    assert result == ("Die Wäsche ist fertig.", "Waschgang beendet")
    assert len(hass.services.calls) == 1
    domain, service, payload, kwargs = hass.services.calls[0]
    assert (domain, service) == ("conversation", "process")
    assert "agent_id" not in payload
    assert kwargs == {"blocking": True, "return_response": True}
    assert "Do not call tools" in payload["text"]


def test_prompt_specifies_independent_speech_and_visual_styles() -> None:
    hass = Hass(ha_reply("Room is ready.", "✅ **Room is ready**"))
    got = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="Room is ready",
        text_notify="Room is ready",
        agent_id=None,
    ))
    assert got == ("Room is ready.", "✅ **Room is ready**")
    prompt = hass.services.calls[0][2]["text"]
    assert "text_tts (SPOKEN VERSION)" in prompt
    assert "text_notify (VISUAL VERSION)" in prompt
    assert "NO emoji, emoticons" in prompt
    assert "simple text styling" in prompt
    assert "NEVER enable a new delivery channel" in prompt


def test_ai_tts_cleaning_keeps_facts_and_separate_visual_styling() -> None:
    hass = Hass(ha_reply(
        "🚨 **The kitchen is at 23°C!**\nStay alert. :)",
        "🌡️ **Kitchen: 23°C**\n⚠️ Stay alert.",
    ))
    got = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="The kitchen is at 23°C. Stay alert.",
        text_notify="Kitchen 23°C. Stay alert.",
        agent_id=None,
    ))
    assert got == (
        "The kitchen is at 23°C! Stay alert.",
        "🌡️ **Kitchen: 23°C**\n⚠️ Stay alert.",
    )


@pytest.mark.parametrize(
    "generated",
    [
        "✅ Garage closed.",
        "**Garage closed.**",
        "# Garage closed.",
        "Garage closed. :-)",
        "TTS: Garage closed.",
    ],
)
def test_ai_generated_speech_never_contains_simple_decoration(generated) -> None:
    hass = Hass(ha_reply(generated, None))
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Garage closed.", text_notify=None, agent_id=None,
    ))
    assert got == ("Garage closed.", None)


@pytest.mark.parametrize(
    "unsafe",
    [
        "<speak>Garage closed.</speak>",
        "<b>Garage closed.</b>",
        "[Garage](https://example.com) closed.",
        chr(96) * 3 + "Garage closed." + chr(96) * 3,
    ],
)
def test_unsafe_generated_tts_markup_triggers_backup(unsafe) -> None:
    hass = Hass(responses=[
        ha_reply(unsafe, None),
        ha_reply("Garage is closed.", None),
    ])
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Garage closed.", text_notify=None,
        agent_id="conversation.primary",
        fallback_agent_id="conversation.backup",
    ))
    assert got == ("Garage is closed.", None)
    assert len(hass.services.calls) == 2


def test_original_text_is_preserved_when_both_agents_fail_even_with_decoration() -> None:
    original = ("**Garage** is closed 🚗", "🚗 **Garage is closed**")
    hass = Hass(responses=[RuntimeError("offline"), RuntimeError("offline")])
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts=original[0], text_notify=original[1],
        agent_id="conversation.primary", fallback_agent_id="conversation.backup",
    ))
    assert got == original
    assert len(hass.services.calls) == 2


def test_greek_speech_keeps_accents_but_not_emoji_or_emphasis() -> None:
    hass = Hass(ha_reply(
        "🚪 **Η πόρτα είναι ανοιχτή.**",
        "🚪 **Η πόρτα είναι ανοιχτή!**",
    ))
    got = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="Η πόρτα είναι ανοιχτή.",
        text_notify="Η πόρτα είναι ανοιχτή.",
        agent_id="conversation.greek",
    ))
    assert got == ("Η πόρτα είναι ανοιχτή.", "🚪 **Η πόρτα είναι ανοιχτή!**")


def test_explicit_agent_passed_and_null_channel_preserved() -> None:
    hass = Hass(ha_reply(None, "The window is open."))
    result = asyncio.run(
        ai.async_filter_announcement(
            hass,
            text_tts=None,
            text_notify="Window open",
            agent_id="conversation.ollama",
        )
    )
    assert result == (None, "The window is open.")
    assert hass.services.calls[0][2]["agent_id"] == "conversation.ollama"


@pytest.mark.parametrize(
    "bad",
    [
        {"response": {"speech": {"plain": {"speech": "not JSON"}}}},
        ha_reply("", "Updated visual text"),
        ha_reply(None, "Updated visual text"),
        ha_reply("New spoken text", None),
        ha_reply("Very long text " * 100, "Updated visual text"),
    ],
)
def test_bad_ai_reply_does_not_replace_original(bad) -> None:
    hass = Hass(bad)
    result = asyncio.run(
        ai.async_filter_announcement(
            hass,
            text_tts="original TTS",
            text_notify="original display",
            agent_id=None,
        )
    )
    assert result == ("original TTS", "original display")


def test_agent_failure_falls_back_to_original() -> None:
    hass = Hass(error=RuntimeError("offline"))
    result = asyncio.run(
        ai.async_filter_announcement(
            hass,
            text_tts="spoken",
            text_notify=None,
            agent_id="conversation.offline",
        )
    )
    assert result == ("spoken", None)


def test_successful_primary_does_not_call_backup() -> None:
    hass = Hass(responses=[ha_reply("Door open.", None)])
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Door open", text_notify=None,
        agent_id="conversation.local",
        fallback_agent_id="conversation.backup",
    ))
    assert got == ("Door open.", None)
    assert len(hass.services.calls) == 1


def test_failing_primary_retries_backup_and_preserves_channel_shape() -> None:
    hass = Hass(responses=[
        RuntimeError("primary offline"),
        ha_reply(None, "Fenster ist offen."),
    ])
    got = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts=None,
        text_notify="Fenster offen",
        agent_id="conversation.local",
        fallback_agent_id="conversation.backup",
    ))
    assert got == (None, "Fenster ist offen.")
    calls = hass.services.calls
    assert len(calls) == 2
    assert calls[0][2]["agent_id"] == "conversation.local"
    assert calls[1][2]["agent_id"] == "conversation.backup"


def test_unusable_primary_tries_home_assistant_default_as_backup() -> None:
    hass = Hass(responses=[
        ha_reply("Wrong 24°C", None),
        ha_reply("Still 23°C", None),
    ])
    got = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="Room temperature 23°C",
        text_notify=None,
        agent_id="conversation.local",
        fallback_agent_id="",
    ))
    assert got == ("Still 23°C", None)
    assert len(hass.services.calls) == 2
    assert "agent_id" not in hass.services.calls[1][2]


def test_both_agents_failing_delivers_original_message() -> None:
    hass = Hass(responses=[
        RuntimeError("offline"),
        ha_reply("I cannot do that", "I cannot do that"),
    ])
    original = ("The door is open", "Door open")
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts=original[0], text_notify=original[1],
        agent_id="conversation.primary",
        fallback_agent_id="conversation.secondary",
    ))
    assert got == original
    assert len(hass.services.calls) == 2


def test_no_duplicate_attempt_for_identical_primary_backup() -> None:
    hass = Hass(error=RuntimeError("offline"))
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Original", text_notify=None,
        agent_id="conversation.same", fallback_agent_id="conversation.same",
    ))
    assert got == ("Original", None)
    assert len(hass.services.calls) == 1


@pytest.mark.parametrize("kind", ["error", "action_done"])
def test_error_and_action_done_responses_are_unusable(kind) -> None:
    response = ha_reply("Changed", None)
    response["response"]["response_type"] = kind
    hass = Hass(response)
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Original", text_notify=None, agent_id=None
    ))
    assert got == ("Original", None)


def test_rewrite_must_preserve_numeric_signs_in_both_channels() -> None:
    source = ("Temperature is -5°C.", "Temperature: -5°C.")
    for changed in (
        ha_reply("Temperature is 5°C.", source[1]),
        ha_reply(source[0], "🌡️ Temperature: +5°C."),
    ):
        hass = Hass(changed)
        got = asyncio.run(ai.async_filter_announcement(
            hass, text_tts=source[0], text_notify=source[1],
            agent_id=None,
        ))
        assert got == source


def test_faulty_numeric_or_refusal_without_backup_uses_original() -> None:
    for edited in ("The temperature is 30°C", "I am sorry, I cannot help"):
        hass = Hass(ha_reply(edited, None))
        got = asyncio.run(ai.async_filter_announcement(
            hass, text_tts="The temperature is 23°C",
            text_notify=None, agent_id=None
        ))
        assert got == ("The temperature is 23°C", None)


def test_timeout_uses_backup_then_original(monkeypatch) -> None:
    monkeypatch.setattr(ai, "AI_FILTER_TIMEOUT_SECONDS", 0.005)
    class SlowServices:
        def __init__(self):
            self.calls = 0
        async def async_call(self, *args, **kwargs):
            self.calls += 1
            await asyncio.sleep(1)
    hass = Hass()
    hass.services = SlowServices()
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Original", text_notify=None,
        agent_id="conversation.primary", fallback_agent_id="conversation.backup",
    ))
    assert got == ("Original", None)
    assert hass.services.calls == 2


def test_cancelled_request_is_not_swallowed() -> None:
    hass = Hass(error=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(ai.async_filter_announcement(
            hass, text_tts="Original", text_notify=None, agent_id=None
        ))


def test_action_diagnostics_identify_success_and_integrity() -> None:
    diag = {}
    hass = Hass(ha_reply("Door is open.", "🚪 **Door open**"))
    rewritten = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Door open", text_notify="Door open",
        agent_id="conversation.gpt", diagnostics=diag,
    ))
    assert rewritten == ("Door is open.", "🚪 **Door open**")
    assert diag["attempted"] is True
    assert diag["status"] == "rewritten"
    assert diag["agent_used"] == "conversation.gpt"
    assert diag["attempts"] == [{"agent": "conversation.gpt", "outcome": "rewritten"}]
    assert diag["failure_reason"] is None
    assert "Door open" not in str(diag)


def test_agent_successful_but_unchanged_is_reported_separately() -> None:
    diag = {}
    hass = Hass(ha_reply(None, "Already clear"))
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts=None, text_notify="Already clear",
        agent_id=None, diagnostics=diag,
    ))
    assert got == (None, "Already clear")
    assert diag["status"] == "accepted_unchanged"
    assert diag["attempted"] is True
    assert diag["agent_used"] == "Home Assistant default"


def test_intent_only_default_agent_error_is_visible_without_text() -> None:
    diag = {}
    response = {"response": {
        "response_type": "error",
        "data": {"code": "no_intent_match"},
        "speech": {"plain": {"speech": "Sorry I cannot do that."}},
    }}
    hass = Hass(response)
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts=None, text_notify="Door open",
        agent_id=None, diagnostics=diag,
    ))
    assert got == (None, "Door open")
    assert diag["attempted"] is True
    assert diag["status"] == "fallback_original"
    assert diag["failure_reason"] == "no_intent_match"
    assert diag["attempts"] == [
        {"agent": "Home Assistant default", "outcome": "no_intent_match"}
    ]
    assert "Sorry" not in str(diag)


def test_primary_exception_and_backup_success_are_reported() -> None:
    diag = {}
    hass = Hass(responses=[
        RuntimeError("secret token in exception"),
        ha_reply(None, "🚪 Door is open."),
    ])
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts=None, text_notify="Door open",
        agent_id="conversation.primary",
        fallback_agent_id="conversation.backup",
        diagnostics=diag,
    ))
    assert got == (None, "🚪 Door is open.")
    assert diag["attempted"] is True
    assert diag["status"] == "rewritten"
    assert diag["agent_used"] == "conversation.backup"
    assert len(diag["attempts"]) == 2
    assert diag["attempts"][0]["outcome"] == "agent_error"
    assert diag["attempts"][1]["outcome"] == "rewritten"
    assert "secret token" not in str(diag)


def test_parse_exception_does_not_block_original_announcement(monkeypatch) -> None:
    diag = {}
    def fail(*_args):
        raise RuntimeError("parser failure")
    monkeypatch.setattr(ai, "_parse_reply", fail)
    got = asyncio.run(ai.async_filter_announcement(
        Hass(ha_reply("Door open", None)),
        text_tts="Door open", text_notify=None,
        agent_id=None, diagnostics=diag,
    ))
    assert got == ("Door open", None)
    assert diag["status"] == "fallback_original"
    assert diag["attempts"][0]["outcome"] == "invalid_response"

def test_config_and_actions_support_optional_ai_overrides() -> None:
    flow = (COMPONENT / "config_flow.py").read_text()
    init = (COMPONENT / "__init__.py").read_text()
    manager = (COMPONENT / "manager.py").read_text()
    const = (COMPONENT / "const.py").read_text()
    service = yaml.safe_load((COMPONENT / "services.yaml").read_text())
    assert 'DEFAULT_USE_AI: Final = False' in const
    assert 'DEFAULT_AI_AGENT: Final = "default"' in const
    assert 'DEFAULT_FALLBACK_AI_AGENT: Final = "original"' in const
    assert "CONF_FALLBACK_AI_AGENT" in flow
    assert "options=self._ai_fallback_agent_options()" in flow
    assert "fallback_agent_id=fallback_agent_id" in manager
    assert 'self.hass.states.async_all("conversation")' in flow
    assert "get_agent_manager(self.hass).async_get_agent_info()" in flow
    assert "CONF_DEFAULT_USE_AI" in flow and "CONF_DEFAULT_AI_AGENT" in flow
    assert "probatio.Optional(ATTR_USE_AI): bool" in init
    assert "probatio.Optional(ATTR_AI_AGENT): cv.string" in init
    assert "probatio.Optional(ATTR_USE_AI, default=False)" not in init
    assert "use_ai=call.data.get(ATTR_USE_AI)" in init
    assert "ai_agent=call.data.get(ATTR_AI_AGENT)" in init
    assert "if use_ai is None" in manager
    assert "if ai_enabled:" in manager
    assert manager.count("Announcement queue is full") == 2
    assert "plan.tts_text, plan.notify_text = await async_filter_announcement(" in manager
    assert "text_tts=plan.tts_text," in manager
    assert "text_notify=plan.notify_text," in manager
    assert "text_tts, text_notify = plan.tts_text, plan.notify_text" in manager
    fields = service["send"]["fields"]["ai"]["fields"]
    assert "boolean" in fields["use_ai"]["selector"]
    assert "conversation_agent" in fields["ai_agent"]["selector"]


def test_ai_fields_localized_in_config_options_and_action() -> None:
    for filename in (
        "strings.json",
        "translations/en.json",
        "translations/de.json",
        "translations/el.json",
    ):
        data = json.loads((COMPONENT / filename).read_text(encoding="utf-8"))
        for section in ("config", "options"):
            queue = data[section]["step"]["queue"]
            for key in ("default_use_ai", "default_ai_agent", "fallback_ai_agent"):
                assert queue["data"][key]
                assert queue["data_description"][key]
        send = data["services"]["send"]
        assert send["sections"]["ai"]["name"]
        for key in ("use_ai", "ai_agent"):
            assert send["fields"][key]["name"]
            assert send["fields"][key]["description"]
