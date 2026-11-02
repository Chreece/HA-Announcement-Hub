"""Provider dropdown discovery preserves the configured provider identities."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
SOURCE = COMPONENT / "provider_catalog.py"
spec = importlib.util.spec_from_file_location("ah_provider_catalog_test", SOURCE)
assert spec and spec.loader
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


def state(entity_id, name):
    return SimpleNamespace(entity_id=entity_id, name=name, attributes={"friendly_name": name})


def test_available_provider_catalog_includes_entity_and_nonentity_conversation_agents():
    result = catalog.build_provider_catalog(
        [state("conversation.assist", "Assist")],
        [state("ai_task.qwen", "Qwen 3"), state("ai_task.gemini", "Gemini")],
        [SimpleNamespace(id="conversation.assist", name="Duplicate"),
         SimpleNamespace(id="other_agent", name="Legacy agent")],
        [{"value": "tts.piper", "label": "Piper · Greek"},
         {"value": "tts.cloud", "label": "Cloud TTS"},
         {"value": "media_player.speaker", "label": "Not a TTS provider"},
         {"value": "tts.piper", "label": "Duplicate"}],
    )
    agents = result["ai_agents"]
    assert agents[0] == {"value": "default", "label": "Home Assistant preferred agent"}
    assert [option["value"] for option in agents].count("conversation.assist") == 1
    assert "ai_task.qwen" in [option["value"] for option in agents]
    assert "ai_task.gemini" in [option["value"] for option in agents]
    assert {"value": "other_agent", "label": "Legacy agent · Conversation"} in agents
    assert {item["value"] for item in result["tts_engines"]} == {"tts.piper", "tts.cloud"}
    assert len(result["tts_engines"]) == 2


def test_no_provider_catalog_is_still_a_valid_dropdown_response():
    result = catalog.build_provider_catalog([], [], [], [])
    assert result["ai_agents"] == [{"value": "default", "label": "Home Assistant preferred agent"}]
    assert result["tts_engines"] == []


def test_catalog_does_not_serialize_credentials_or_message_bodies():
    agent = SimpleNamespace(id="external_agent", name="Voice provider", token="PRIVATE_TOKEN")
    entity = SimpleNamespace(entity_id="ai_task.test", name="Provider",
                             attributes={"friendly_name": "Provider", "api_key": "PRIVATE_TOKEN"})
    result = catalog.build_provider_catalog([], [entity], [agent], [])
    assert "PRIVATE_TOKEN" not in str(result)
    assert set(result) == {"ai_agents", "tts_engines"}
    assert all(set(item) == {"value", "label"} for items in result.values() for item in items)


def test_registered_agents_may_be_mappings_or_objects():
    result = catalog.build_provider_catalog(
        [], [], [{"id": "legacy_agent", "name": "Legacy"}, SimpleNamespace(id="legacy2", name="Legacy 2")], []
    )
    assert {"value": "legacy_agent", "label": "Legacy · Conversation"} in result["ai_agents"]
    assert {"value": "legacy2", "label": "Legacy 2 · Conversation"} in result["ai_agents"]


def test_action_registration_provides_authenticated_readonly_response():
    init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    services = (COMPONENT / "services.yaml").read_text(encoding="utf-8")
    assert "async def async_list_providers(call: ServiceCall)" in init
    assert "build_provider_catalog(" in init
    assert "SERVICE_LIST_PROVIDERS" in init
    assert "supports_response=SupportsResponse.OPTIONAL" in init
    assert "list_providers:" in services
    assert "No credentials or message contents are returned." in services
