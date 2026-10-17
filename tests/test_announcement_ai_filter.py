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
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def async_call(self, domain, service, payload, **kwargs):
        self.calls.append((domain, service, payload, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


class Hass:
    def __init__(self, response=None, error=None):
        self.services = Services(response, error)


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


def test_config_and_actions_support_optional_ai_overrides() -> None:
    flow = (COMPONENT / "config_flow.py").read_text()
    init = (COMPONENT / "__init__.py").read_text()
    manager = (COMPONENT / "manager.py").read_text()
    const = (COMPONENT / "const.py").read_text()
    service = yaml.safe_load((COMPONENT / "services.yaml").read_text())
    assert 'DEFAULT_USE_AI: Final = False' in const
    assert 'DEFAULT_AI_AGENT: Final = "default"' in const
    assert 'self.hass.states.async_all("conversation")' in flow
    assert "CONF_DEFAULT_USE_AI" in flow and "CONF_DEFAULT_AI_AGENT" in flow
    assert "probatio.Optional(ATTR_USE_AI): bool" in init
    assert "probatio.Optional(ATTR_AI_AGENT): cv.string" in init
    assert "probatio.Optional(ATTR_USE_AI, default=False)" not in init
    assert "use_ai=call.data.get(ATTR_USE_AI)" in init
    assert "ai_agent=call.data.get(ATTR_AI_AGENT)" in init
    assert "if use_ai is None" in manager
    assert "if ai_enabled:" in manager
    assert "plan.tts_text = text_tts or text_notify" in manager
    assert "plan.notify_text = text_notify or text_tts" in manager
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
            for key in ("default_use_ai", "default_ai_agent"):
                assert queue["data"][key]
                assert queue["data_description"][key]
        send = data["services"]["send"]
        assert send["sections"]["ai"]["name"]
        for key in ("use_ai", "ai_agent"):
            assert send["fields"][key]["name"]
            assert send["fields"][key]["description"]
