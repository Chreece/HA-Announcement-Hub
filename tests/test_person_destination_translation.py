"""Person delivery destination aliases and translation safety regressions."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def import_module(name):
    spec = importlib.util.spec_from_file_location(name, COMPONENT / (name + ".py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


person = import_module("person_targeting")
ai = import_module("ai_filter")


def test_destinations_are_exact_named_assignments_without_entity_guessing():
    profile = {"destinations": {
        "mobile": ["notify.pixel", "notify.pixel"],
        "watch": ["notify.pixel_watch_3"],
        "tablet": ["media_player.hall_display"],
    }}
    assert person.selected_person_destinations(
        profile, ["mobile", "watch"]
    ) == {
        "mobile": ("notify.pixel",),
        "watch": ("notify.pixel_watch_3",),
    }
    with pytest.raises(person.PersonTargetError, match="not configured"):
        person.selected_person_destinations(profile, ["other"])
    with pytest.raises(person.PersonTargetError, match="Invalid"):
        person.selected_person_destinations(profile, ["mobile", "all"])
    assert person.selected_person_destinations(profile, ["room"]) == {"room": ()}


def test_person_ids_work_away_from_home_without_room_lookup():
    people = [
        SimpleNamespace(entity_id="person.alex", state="not_home",
                        attributes={"friendly_name": "Alex"})
    ]
    hass = SimpleNamespace(states=SimpleNamespace(async_all=lambda domain: people))
    assert person.resolve_person_ids(hass, ["Alex,person.alex"]) == ["person.alex"]


class FakeServices:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def async_call(self, domain, service, payload, **kwargs):
        self.calls.append((domain, service, payload))
        if self.error:
            raise self.error
        return self.response


def test_ai_translation_respects_tts_voice_language_and_channel_shape():
    response = {
        "response": {
            "speech": {"plain": {"speech": json.dumps({
                "text_tts": "Το πλυντήριο τελείωσε στις 18:00.",
                "text_notify": "✅ Το πλυντήριο τελείωσε στις 18:00.",
            }, ensure_ascii=False)}}
        }
    }
    services = FakeServices(response)
    hass = SimpleNamespace(services=services)
    result = asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Washing finished at 18:00.",
        text_notify="Washing finished at 18:00.",
        agent_id="conversation.person", mode="translate",
        target_language="el",
    ))
    assert result == (
        "Το πλυντήριο τελείωσε στις 18:00.",
        "✅ Το πλυντήριο τελείωσε στις 18:00.",
    )
    prompt = services.calls[0][2]["text"]
    assert "Translate each non-null announcement channel into el" in prompt
    assert "Do not invent details" in prompt
    assert services.calls[0][2].get("language") is None  # explicit agent


def test_translation_preserves_original_if_ai_unavailable():
    services = FakeServices(error=RuntimeError("offline"))
    hass = SimpleNamespace(services=services)
    assert asyncio.run(ai.async_filter_announcement(
        hass, text_tts="Waschmaschine fertig", text_notify=None,
        agent_id="conversation.offline", target_language="el",
        mode="translate",
    )) == ("Waschmaschine fertig", None)


def test_person_send_uses_named_destinations_and_language_not_client_entity_names():
    service = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    setup = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "selected_person_destinations(profile, destinations)" in service
    assert "refs = tuple(dict.fromkeys(" in service
    assert 'local["entities"] = refs' in service
    assert 'local["manual_targets"] = True' in service
    assert 'local["translate_to"]' in service
    assert '"destination_watch"' in setup
    assert '"translate"' in setup
    assert '"requested_target_language"' in manager


def test_card_shows_named_person_destinations_without_exposing_entity_ids():
    js = (COMPONENT / "frontend" / "announcement-hub-card.js").read_text()
    html = (COMPONENT / "frontend" / "announcement-hub-card.html").read_text()
    assert 'payload.person_destination = [...this._personDestinations]' in js
    assert 'payload.target_person = [...this._selected.person]' in js
    assert 'state.attributes?.person_destinations' in js
    assert 'id="person-destinations"' in html
