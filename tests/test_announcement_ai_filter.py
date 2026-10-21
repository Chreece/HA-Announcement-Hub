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


def test_ha_default_action_done_without_actions_is_valid_ai_text() -> None:
    """HA IntentResponse defaults to action_done even for text-only agents."""
    reply = ha_reply("The kitchen light is on.", "💡 **Kitchen light on**")
    reply["response"]["response_type"] = "action_done"
    reply["response"]["data"] = {"success": [], "failed": []}
    diag = {}
    got = asyncio.run(ai.async_filter_announcement(
        Hass(reply),
        text_tts="Kitchen light on", text_notify="Kitchen light on",
        agent_id="conversation.llm", diagnostics=diag,
    ))
    assert got == ("The kitchen light is on.", "💡 **Kitchen light on**")
    assert diag["status"] == "rewritten"
    assert diag["agent_used"] == "conversation.llm"


@pytest.mark.parametrize("action_data", [
    {"success": [{"name": "Kitchen", "type": "area"}], "failed": []},
    {"success": [], "failed": [{"name": "Light", "type": "entity"}]},
    {"success": [], "failed": [], "other_actions": ["turn on"]},
])
def test_ai_cannot_accept_reply_reporting_actions(action_data) -> None:
    reply = ha_reply("The kitchen light is on.", None)
    reply["response"]["response_type"] = "action_done"
    reply["response"]["data"] = action_data
    diag = {}
    got = asyncio.run(ai.async_filter_announcement(
        Hass(reply), text_tts="Kitchen light on",
        text_notify=None, agent_id=None, diagnostics=diag,
    ))
    assert got == ("Kitchen light on", None)
    assert diag["status"] == "fallback_original"
    assert diag["failure_reason"] == "action_response_not_allowed"

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


def test_slow_primary_finishes_without_hub_timeout_or_backup(monkeypatch, caplog) -> None:
    """A cold-started model must get its response even after the advisory minute."""
    monkeypatch.setattr(ai, "AI_FILTER_SLOW_REQUEST_SECONDS", 0.01)

    class ColdStartServices:
        def __init__(self):
            self.calls = []

        async def async_call(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            await asyncio.sleep(0.06)
            return ha_reply("Door is open.", None)

    hass = Hass()
    hass.services = ColdStartServices()
    diag = {}
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Door open", text_notify=None,
        agent_id="conversation.primary", fallback_agent_id="conversation.backup",
        diagnostics=diag,
    ))
    assert got == ("Door is open.", None)
    assert len(hass.services.calls) == 1
    assert diag["status"] == "rewritten"
    assert diag["attempt_duration_seconds"]["conversation.primary"] >= 0.05
    assert "continuing to await AI provider" in caplog.text


def test_backend_timeout_is_reported_as_provider_failure_not_local_cutoff() -> None:
    """If a provider itself aborts the request, its error may trigger backup."""
    hass = Hass(responses=[
        TimeoutError("backend disconnected"),
        ha_reply("Door is open.", None),
    ])
    diag = {}
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Door open", text_notify=None,
        agent_id="conversation.primary", fallback_agent_id="conversation.backup",
        diagnostics=diag,
    ))
    assert got == ("Door is open.", None)
    assert len(hass.services.calls) == 2
    assert diag["attempts"][0]["outcome"] == "provider_timeout"
    assert diag["attempts"][1]["outcome"] == "rewritten"


def test_no_hub_timeout_even_without_backup(monkeypatch) -> None:
    monkeypatch.setattr(ai, "AI_FILTER_SLOW_REQUEST_SECONDS", 0.001)

    class SlowServices:
        async def async_call(self, *_args, **_kwargs):
            await asyncio.sleep(0.02)
            return ha_reply(None, "✅ Window is open.")

    hass = Hass()
    hass.services = SlowServices()
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts=None, text_notify="Window open",
        agent_id="conversation.ollama",
    ))
    assert got == (None, "✅ Window is open.")


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
    assert diag["agent_used"] == "Home Assistant built-in"


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
        {"agent": "Home Assistant built-in", "outcome": "no_intent_match"}
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


def test_default_agent_is_preferred_assist_pipeline_not_builtin(monkeypatch) -> None:
    monkeypatch.setattr(
        ai, "resolve_preferred_assist_agent",
        lambda _hass: ("conversation.ollama", "el", None),
    )
    hass = Hass(ha_reply("Η πόρτα είναι ανοιχτή.", "🚪 Η πόρτα είναι ανοιχτή."))
    diagnostics = {"agent": "Preferred Assist pipeline"}
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Η πόρτα είναι ανοιχτή",
        text_notify="Η πόρτα είναι ανοιχτή", agent_id="default",
        diagnostics=diagnostics,
    ))
    assert got == ("Η πόρτα είναι ανοιχτή.", "🚪 Η πόρτα είναι ανοιχτή.")
    assert len(hass.services.calls) == 1
    _, _, payload, kwargs = hass.services.calls[0]
    assert payload["agent_id"] == "conversation.ollama"
    assert payload["language"] == "el"
    assert kwargs == {"blocking": True, "return_response": True}
    assert diagnostics["agent"] == "conversation.ollama"
    assert diagnostics["agent_used"] == "conversation.ollama"
    assert diagnostics["status"] == "rewritten"


def test_explicit_selected_agent_does_not_resolve_preferred(monkeypatch) -> None:
    def fail(_hass):
        raise AssertionError("Explicit agent must not query preferred pipeline")
    monkeypatch.setattr(ai, "resolve_preferred_assist_agent", fail)
    hass = Hass(ha_reply(None, "The door is open."))
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts=None, text_notify="Door open",
        agent_id="conversation.explicit",
    ))
    assert got == (None, "The door is open.")
    assert hass.services.calls[0][2]["agent_id"] == "conversation.explicit"
    assert "language" not in hass.services.calls[0][2]


@pytest.mark.parametrize("failure_reason", [
    "preferred_assist_pipeline_unavailable",
    "preferred_assist_agent_not_generative",
    "preferred_assist_agent_unavailable",
])
def test_preferred_agent_unavailable_never_calls_builtin(
    monkeypatch, failure_reason
) -> None:
    monkeypatch.setattr(
        ai, "resolve_preferred_assist_agent",
        lambda _hass: (None, None, failure_reason),
    )
    hass = Hass(error=AssertionError("Must not call the built-in agent"))
    diagnostics = {}
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Original speech", text_notify="Original text",
        agent_id="default", diagnostics=diagnostics,
    ))
    assert got == ("Original speech", "Original text")
    assert not hass.services.calls
    assert diagnostics["status"] == "fallback_original"
    assert diagnostics["attempted"] is False
    assert diagnostics["agent_used"] is None
    assert diagnostics["failure_reason"] == failure_reason
    assert diagnostics["attempts"] == [
        {"agent": "Preferred Assist pipeline", "outcome": failure_reason}
    ]


def test_missing_preferred_agent_tries_configured_backup(monkeypatch) -> None:
    monkeypatch.setattr(
        ai, "resolve_preferred_assist_agent",
        lambda _hass: (None, None, "preferred_assist_agent_not_generative"),
    )
    hass = Hass(ha_reply("The door is open.", None))
    diagnostics = {}
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Door open", text_notify=None,
        agent_id="default", fallback_agent_id="conversation.backup",
        diagnostics=diagnostics,
    ))
    assert got == ("The door is open.", None)
    assert len(hass.services.calls) == 1
    assert hass.services.calls[0][2]["agent_id"] == "conversation.backup"
    assert diagnostics["attempts"] == [
        {
            "agent": "Preferred Assist pipeline",
            "outcome": "preferred_assist_agent_not_generative",
        },
        {"agent": "conversation.backup", "outcome": "rewritten"},
    ]
    assert diagnostics["agent_used"] == "conversation.backup"
    assert diagnostics["failure_reason"] is None


def test_fallback_default_uses_preferred_assist_agent(monkeypatch) -> None:
    monkeypatch.setattr(
        ai, "resolve_preferred_assist_agent",
        lambda _hass: ("conversation.qwen", "el", None),
    )
    hass = Hass(responses=[
        RuntimeError("primary offline"),
        ha_reply(None, "🚪 Η πόρτα είναι ανοιχτή."),
    ])
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts=None, text_notify="Η πόρτα είναι ανοιχτή",
        agent_id="conversation.broken", fallback_agent_id="default",
    ))
    assert got == (None, "🚪 Η πόρτα είναι ανοιχτή.")
    assert len(hass.services.calls) == 2
    assert hass.services.calls[0][2]["agent_id"] == "conversation.broken"
    assert hass.services.calls[1][2]["agent_id"] == "conversation.qwen"
    assert hass.services.calls[1][2]["language"] == "el"


def test_fallback_default_deduplicates_preferred_primary(monkeypatch) -> None:
    monkeypatch.setattr(
        ai, "resolve_preferred_assist_agent",
        lambda _hass: ("conversation.qwen", "el", None),
    )
    hass = Hass(error=RuntimeError("agent offline"))
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Door open", text_notify=None,
        agent_id="conversation.qwen", fallback_agent_id="default",
    ))
    assert got == ("Door open", None)
    assert len(hass.services.calls) == 1


def test_preferred_pipeline_is_resolved_fresh_per_announcement(monkeypatch) -> None:
    agent_ids = iter(["conversation.ollama", "conversation.openai"])
    monkeypatch.setattr(
        ai, "resolve_preferred_assist_agent",
        lambda _hass: (next(agent_ids), "el", None),
    )
    hass = Hass(ha_reply(None, "Ready."))
    for expected in ("conversation.ollama", "conversation.openai"):
        got = asyncio.run(ai.async_filter_announcement(
            hass, text_tts=None, text_notify="Ready",
            agent_id="default",
        ))
        assert got == (None, "Ready.")
        assert hass.services.calls[-1][2]["agent_id"] == expected


def test_preferred_pipeline_resolver_uses_home_assistant_public_api(
    monkeypatch,
) -> None:
    import sys
    from types import ModuleType, SimpleNamespace

    fake_homeassistant = ModuleType("homeassistant")
    fake_homeassistant.__path__ = []
    fake_components = ModuleType("homeassistant.components")
    fake_components.__path__ = []
    fake_pipeline = ModuleType("homeassistant.components.assist_pipeline")
    calls = []
    def get_pipeline(hass):
        calls.append(hass)
        return SimpleNamespace(
            conversation_engine="conversation.ollama",
            conversation_language="el",
        )
    fake_pipeline.async_get_pipeline = get_pipeline
    monkeypatch.setitem(sys.modules, "homeassistant", fake_homeassistant)
    monkeypatch.setitem(sys.modules, "homeassistant.components", fake_components)
    monkeypatch.setitem(
        sys.modules, "homeassistant.components.assist_pipeline", fake_pipeline
    )
    hass = Hass()
    assert ai.resolve_preferred_assist_agent(hass) == (
        "conversation.ollama", "el", None
    )
    assert calls == [hass]

    fake_pipeline.async_get_pipeline = lambda _hass: SimpleNamespace(
        conversation_engine="conversation.home_assistant",
        conversation_language="el",
    )
    assert ai.resolve_preferred_assist_agent(hass) == (
        None, None, "preferred_assist_agent_not_generative"
    )

    def no_pipeline(_hass):
        raise KeyError("No preferred pipeline")
    fake_pipeline.async_get_pipeline = no_pipeline
    assert ai.resolve_preferred_assist_agent(hass) == (
        None, None, "preferred_assist_pipeline_unavailable"
    )


def test_manager_passes_default_marker_instead_of_none() -> None:
    source = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "if not selected_agent or selected_agent == DEFAULT_AI_AGENT" in source
    assert "agent_id = (" in source
    assert '"preferred_assist" if agent_id == DEFAULT_AI_AGENT else "explicit"' in source
    assert "else fallback_setting" in source
    assert "diagnostics=ai" in source
    flow = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    assert "resolve_preferred_assist_agent(" in flow
    assert 'provider_label(self.hass, "preferred", name=preferred_name)' in flow
    assert 'provider_label(self.hass, "original")' in flow

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
    assert '"requested_fallback_agent_id": fallback_agent_id' in manager
    assert 'self.hass.states.async_all("conversation")' in flow
    assert "get_agent_manager(self.hass).async_get_agent_info()" in flow
    assert "CONF_DEFAULT_USE_AI" in flow and "CONF_DEFAULT_AI_AGENT" in flow
    assert "probatio.Optional(ATTR_USE_AI): bool" in init
    assert "probatio.Optional(ATTR_AI_AGENT): cv.string" in init
    assert "probatio.Optional(ATTR_USE_AI, default=False)" not in init
    assert "use_ai=call.data.get(ATTR_USE_AI)" in init
    assert "ai_agent=call.data.get(ATTR_AI_AGENT)" in init
    assert "resolve_ai_enabled(" in manager
    assert "if ai_enabled:" in manager
    assert manager.count("Announcement queue is full") == 1
    assert "rewritten_tts, rewritten_notify = await async_filter_announcement(" in manager
    assert "text_tts=original_tts," in manager
    assert "text_notify=original_notify," in manager
    assert "job.text_tts, job.text_notify = rewritten_tts, rewritten_notify" in manager
    assert "self._queue.append(job)" in manager
    fields = service["send"]["fields"]["ai"]["fields"]
    assert "boolean" in fields["use_ai"]["selector"]
    assert "text" in fields["ai_agent"]["selector"]


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


def test_generation_mode_creates_actual_text_from_greek_writing_instruction() -> None:
    prompt = "Γράψε μια ενημέρωση ότι το πλυντήριο τελείωσε."
    hass = Hass(ha_reply(
        "Η πλύση ολοκληρώθηκε. Μπορείς να βγάλεις τα ρούχα.",
        "🧺 **Η πλύση ολοκληρώθηκε!**",
    ))
    result = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts=prompt,
        text_notify=prompt,
        mode="generate",
        agent_id="conversation.local",
    ))
    assert result[0] == "Η πλύση ολοκληρώθηκε. Μπορείς να βγάλεις τα ρούχα."
    assert result[1] == "🧺 **Η πλύση ολοκληρώθηκε!**"
    request = hass.services.calls[0][2]["text"]
    assert "WRITING THE ANNOUNCEMENT" in request
    assert "not" in request.casefold()
    assert "Untrusted writing instructions" in request


def test_generation_mode_accepts_safe_summary_without_exact_numeric_match() -> None:
    hass = Hass(ha_reply("There are two open windows.", None))
    got = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="Summarize 2 open windows in the bedroom and kitchen.",
        text_notify=None,
        mode="generate",
        agent_id="conversation.local",
    ))
    assert got == ("There are two open windows.", None)


def test_default_copyedit_mode_rejects_new_numbers_but_generate_is_distinct() -> None:
    response = ha_reply("There are 2 open windows.", None)
    hass = Hass(response)
    got = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="There are open windows.", text_notify=None,
        agent_id="conversation.local",
    ))
    assert got == ("There are open windows.", None)
    assert "copyediting" in hass.services.calls[0][2]["text"]


def test_generate_mode_provider_failure_preserves_original_instruction() -> None:
    original = "Γράψε μια ανακοίνωση για τα παράθυρα."
    hass = Hass(error=RuntimeError("offline"))
    got = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts=original, text_notify=original,
        mode="generate", agent_id="conversation.offline",
    ))
    assert got == (original, original)


def test_generation_mode_cannot_enable_unrequested_visual_channel() -> None:
    hass = Hass(ha_reply("Washing machine finished.", "🧺 Finished!"))
    got = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="Write a sentence about laundry.", text_notify=None,
        mode="generate", agent_id="conversation.local",
    ))
    assert got == ("Write a sentence about laundry.", None)


def test_unknown_generation_mode_fails_closed_without_provider_request() -> None:
    hass = Hass()
    with pytest.raises(ValueError):
        asyncio.run(ai.async_filter_announcement(
            hass, text_tts="Text", text_notify=None,
            mode="unsupported", agent_id="conversation.local",
        ))
    assert not hass.services.calls


def test_action_accepts_generation_mode_and_persists_it_with_original_job():
    init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    services = yaml.safe_load((COMPONENT / "services.yaml").read_text())
    assert 'probatio.Optional(ATTR_AI_MODE, default="rewrite")' in init
    assert 'ai_mode=call.data[ATTR_AI_MODE]' in init
    assert 'ai_mode=ai_mode, channels=channel_tokens' in manager
    assert '"requested_mode": ai_mode' in manager
    assert 'mode=ai.get("requested_mode", "rewrite")' in manager
    assert "generate" in services["send"]["fields"]["ai"]["fields"]["ai_mode"]["selector"]["select"]["options"]


def _ha_reply_with_generated_title(tts, notify, title):
    response = ha_reply(tts, notify)
    payload = json.loads(response["response"]["speech"]["plain"]["speech"])
    payload["title"] = title
    response["response"]["speech"]["plain"]["speech"] = json.dumps(
        payload, ensure_ascii=False
    )
    return response


def test_generation_without_explicit_title_requests_three_words_in_one_call():
    prompt = "Γράψε μία σύντομη ενημέρωση ότι η πόρτα είναι ανοιχτή."
    hass = Hass(_ha_reply_with_generated_title(
        "Η πόρτα είναι ανοιχτή.", "🚪 Η πόρτα είναι ανοιχτή.",
        "🚪 **Ανοιχτή Πόρτα Σπιτιού Σήμερα**",
    ))
    title = {"title": "stale"}
    result = asyncio.run(ai.async_filter_announcement(
        hass, text_tts=prompt, text_notify=prompt,
        agent_id="conversation.local", mode="generate", title_result=title,
    ))
    assert result == (
        "Η πόρτα είναι ανοιχτή.", "🚪 Η πόρτα είναι ανοιχτή."
    )
    assert title == {"title": "Ανοιχτή Πόρτα Σπιτιού"}
    assert len(title["title"].split()) == 3
    assert len(hass.services.calls) == 1
    message = hass.services.calls[0][2]["text"]
    assert "ONE TO THREE WORDS maximum" in message
    assert "text_tts, text_notify and title" in message


def test_generation_with_explicit_title_does_not_ask_model_for_a_new_title():
    hass = Hass(ha_reply("The door is open.", "Door open."))
    result = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Write a door alert.", text_notify="Write a door alert.",
        agent_id="conversation.local", mode="generate",
    ))
    assert result == ("The door is open.", "Door open.")
    message = hass.services.calls[0][2]["text"]
    assert "ONE TO THREE WORDS maximum" not in message
    assert "exactly these keys: text_tts and text_notify" in message


def test_missing_optional_ai_title_preserves_generated_message():
    hass = Hass(ha_reply("The oven is ready.", "Oven ready."))
    title = {}
    result = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Announce oven ready",
        text_notify="Announce oven ready",
        agent_id="conversation.local", mode="generate", title_result=title,
    ))
    assert result == ("The oven is ready.", "Oven ready.")
    assert title == {}  # Caller retains configured Default notification title.


@pytest.mark.parametrize("bad_title", [
    None,
    "",
    "🚪",
    "<script>alert('x')</script>",
    "https://example.invalid/alert",
    "www.example.invalid",
])
def test_unusable_ai_title_never_discards_valid_body(bad_title):
    hass = Hass(_ha_reply_with_generated_title(
        "The window is open.", "Window open.", bad_title
    ))
    title = {}
    result = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Write window warning",
        text_notify="Write window warning",
        agent_id="conversation.local", mode="generate", title_result=title,
    ))
    assert result == ("The window is open.", "Window open.")
    assert title == {}


def test_provider_failure_clears_title_and_preserves_original_message():
    hass = Hass(error=RuntimeError("provider offline"))
    title = {"title": "Old title"}
    original = "Γράψε μήνυμα για την πόρτα."
    result = asyncio.run(ai.async_filter_announcement(
        hass, text_tts=original, text_notify=original,
        agent_id="conversation.local", mode="generate", title_result=title,
    ))
    assert result == (original, original)
    assert title == {}


def test_backup_agent_may_generate_short_title_when_primary_fails():
    hass = Hass(responses=[
        RuntimeError("primary offline"),
        _ha_reply_with_generated_title(
            "Waschmaschine fertig.", "Wäsche ist fertig.",
            "**Wäsche jetzt fertig**",
        ),
    ])
    title = {}
    result = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="Formuliere eine Waschmaschinenmeldung.",
        text_notify="Formuliere eine Waschmaschinenmeldung.",
        mode="generate", agent_id="conversation.primary",
        fallback_agent_id="conversation.backup", title_result=title,
    ))
    assert result == ("Waschmaschine fertig.", "Wäsche ist fertig.")
    assert title == {"title": "Wäsche jetzt fertig"}
    assert len(hass.services.calls) == 2


def test_rewrite_mode_does_not_generate_a_title_even_when_destination_provided():
    hass = Hass(ha_reply("Kitchen open.", "Kitchen open."))
    title = {"title": "must clear"}
    result = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Kitchen open", text_notify="Kitchen open",
        agent_id="conversation.local", mode="rewrite", title_result=title,
    ))
    assert result == ("Kitchen open.", "Kitchen open.")
    assert title == {}
    assert "ONE TO THREE WORDS" not in hass.services.calls[0][2]["text"]


def test_generated_title_remains_private_in_durable_queue_diagnostics():
    source = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    models = (COMPONENT / "models.py").read_text(encoding="utf-8")
    assert 'ai_mode == "generate" and title is None' in source
    assert '"requested_generate_title": generate_title' in source
    assert 'title_result if ai.get("requested_generate_title") else None' in source
    assert 'job.title = title_result["title"]' in source
    assert '"requested_generate_title"' in models
    assert 'result["title"] = self.title' in models


def test_ai_task_generates_using_selected_entity() -> None:
    response = {"data": json.dumps({
        "text_tts": "Die Wäsche ist fertig.",
        "text_notify": "✅ Wäsche fertig",
    })}
    hass = Hass(response)
    result = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="Die Wäsche ist fertig",
        text_notify="Wäsche fertig",
        agent_id="ai_task.local_model",
    ))
    assert result == ("Die Wäsche ist fertig.", "✅ Wäsche fertig")
    domain, service, payload, kwargs = hass.services.calls[0]
    assert (domain, service) == ("ai_task", "generate_data")
    assert payload["entity_id"] == "ai_task.local_model"
    assert payload["task_name"] == "Announcement Hub announcement"
    assert "Announcement source JSON" in payload["instructions"]
    assert kwargs == {"blocking": True, "return_response": True}


def test_ai_task_structured_data_and_short_title() -> None:
    hass = Hass({"data": {
        "text_tts": "Room ready.",
        "text_notify": "✅ Room ready",
        "title": "Room is ready now",
    }})
    title = {}
    result = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="Room ready",
        text_notify="Room ready",
        agent_id="ai_task.local",
        mode="generate",
        title_result=title,
    ))
    assert result == ("Room ready.", "✅ Room ready")
    assert title["title"] == "Room is ready"


def test_ai_task_failure_uses_conversation_backup() -> None:
    hass = Hass(responses=[
        RuntimeError("AI Task unavailable"),
        ha_reply("Ready.", "✅ Ready"),
    ])
    result = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="Ready",
        text_notify="Ready",
        agent_id="ai_task.offline",
        fallback_agent_id="conversation.backup",
    ))
    assert result == ("Ready.", "✅ Ready")
    assert [(d, s) for d, s, _, _ in hass.services.calls] == [
        ("ai_task", "generate_data"), ("conversation", "process")
    ]


def test_ai_task_invalid_response_falls_back_to_original() -> None:
    hass = Hass({"data": "not json"})
    result = asyncio.run(ai.async_filter_announcement(
        hass,
        text_tts="Temperature 23°C",
        text_notify="Temperature 23°C",
        agent_id="ai_task.bad",
    ))
    assert result == ("Temperature 23°C", "Temperature 23°C")


def test_action_done_with_empty_targets_is_not_real_device_action():
    """Modern HA LLMs include an empty targets field in action_done."""
    response = ha_reply("Das Fenster ist offen.", "🪟 Fenster offen.")
    response["response"]["response_type"] = "action_done"
    response["response"]["data"] = {
        "targets": [], "success": [], "failed": [],
    }
    diag = {}
    result = asyncio.run(ai.async_filter_announcement(
        Hass(response), text_tts="Fenster offen",
        text_notify="Fenster offen", agent_id="conversation.local",
        diagnostics=diag,
    ))
    assert result == ("Das Fenster ist offen.", "🪟 Fenster offen.")
    assert diag["status"] == "rewritten"
    assert diag["failure_reason"] is None


def test_ai_task_native_schema_requests_only_selected_channels():
    hass = Hass({"data": {"text_notify": "🚪 Door open!"}})
    result = asyncio.run(ai.async_filter_announcement(
        hass, text_tts=None, text_notify="Door open",
        agent_id="ai_task.local", mode="rewrite",
    ))
    assert result == (None, "🚪 Door open!")
    domain, action, payload, _ = hass.services.calls[0]
    assert (domain, action) == ("ai_task", "generate_data")
    assert set(payload["structure"]) == {"text_notify"}
    assert payload["structure"]["text_notify"]["required"] is True
    assert payload["structure"]["text_notify"]["selector"] == {"text": {}}


def test_ai_task_native_schema_includes_short_title_for_generation():
    hass = Hass({"data": {
        "text_tts": "Door is open.",
        "text_notify": "🚪 Door open",
        "title": "Front door open",
    }})
    title = {}
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Door open", text_notify="Door open",
        agent_id="ai_task.local", mode="generate", title_result=title,
    ))
    assert got == ("Door is open.", "🚪 Door open")
    assert title["title"] == "Front door open"
    assert set(hass.services.calls[0][2]["structure"]) == {
        "text_tts", "text_notify", "title"
    }


def test_ai_task_cannot_create_missing_channel_even_with_structured_response():
    hass = Hass({"data": {
        "text_tts": "Hello.",
        "text_notify": "Unrequested",
    }})
    got = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Hello", text_notify=None,
        agent_id="ai_task.local",
    ))
    assert got == ("Hello.", None)


def test_safe_diagnostics_separate_online_invalid_json_from_timeout():
    diag = {}
    got = asyncio.run(ai.async_filter_announcement(
        Hass(ha_reply("not JSON", None)),
        text_tts="Door open", text_notify=None,
        agent_id="conversation.local", diagnostics=diag,
    ))
    assert got == ("Door open", None)
    assert diag["failure_reason"] == "invalid_json"
    assert diag["attempts"][0]["outcome"] == "invalid_json"
    assert "not JSON" not in str(diag)


def test_safe_diagnostics_identify_factual_numeric_change():
    diag = {}
    got = asyncio.run(ai.async_filter_announcement(
        Hass(ha_reply("Temperature 25°C", None)),
        text_tts="Temperature 23°C", text_notify=None,
        agent_id="conversation.local", diagnostics=diag,
    ))
    assert got == ("Temperature 23°C", None)
    assert diag["failure_reason"] == "number_mismatch"
