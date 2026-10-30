"""Live sleep-room source: entity/attribute selection and tolerant HA areas."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
MANAGER = (COMPONENT / "manager.py").read_text(encoding="utf-8")
FLOW = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")


class FakeRegistry:
    def __init__(self):
        self.areas = [
            SimpleNamespace(
                id="schlafzimmer", name="Schlafzimmer",
                aliases={"Bedroom", "Sleeping Room"},
            ),
            SimpleNamespace(
                id="kueche", name="Küche", aliases={"Kitchen"},
            ),
        ]

    def async_list_areas(self):
        return self.areas

    def async_get_area(self, value):
        return next((area for area in self.areas if area.id == value), None)


def _resolve_live_values(values):
    """Execute the real production area resolver without Home Assistant."""
    manager_tree = ast.parse(MANAGER)
    klass = next(node for node in manager_tree.body
                 if isinstance(node, ast.ClassDef)
                 and node.name == "AnnouncementManager")
    method = next(node for node in klass.body
                  if isinstance(node, ast.FunctionDef)
                  and node.name == "_observed_area_ids")
    registry = FakeRegistry()
    namespace = {
        "Sequence": Sequence,
        "ar": SimpleNamespace(async_get=lambda hass: registry),
        "_LOGGER": SimpleNamespace(debug=lambda *args: None),
    }
    code = compile(ast.fix_missing_locations(
        ast.Module(body=[method], type_ignores=[])), "live area resolver", "exec"
    )
    exec(code, namespace)
    instance = SimpleNamespace(hass=SimpleNamespace())
    return namespace["_observed_area_ids"](instance, values, "sensor.sleeping_rooms")


def test_sleep_entity_selection_is_two_drop_down_menus_not_fixed_areas():
    assert "async def async_step_sleep_rooms(" in FLOW
    assert "async def async_step_sleep_rooms_source(" in FLOW
    assert "CONF_SLEEP_ROOMS_ENTITY" in FLOW
    assert "CONF_SLEEP_ROOMS_ATTRIBUTE" in FLOW
    assert "self._sleep_rooms_attribute_options()" in FLOW
    assert "state.attributes if state else {}" in FLOW
    assert "return await self.async_step_sleep_rooms_source()" in FLOW
    assert 'step_id="sleep_rooms"' in FLOW
    assert 'step_id="sleep_rooms_source"' in FLOW
    wizard = FLOW[FLOW.index("async def async_step_sleep_rooms("):
                  FLOW.index("def _ai_agent_options(")]
    assert "selector.EntitySelector()" in wizard
    assert "selector.SelectSelector(" in wizard
    assert "selector.AreaSelector(" not in wizard


def test_configured_source_is_rechecked_and_legacy_is_only_a_fallback():
    sleep = MANAGER[MANAGER.index("    def _sleep_rooms_source_unavailable("):
                    MANAGER.index("    def _staged_areas(")]
    assert "self.hass.states.get(entity)" in sleep
    assert "CONF_SLEEP_ROOMS_ATTRIBUTE" in sleep
    assert "if entity:" in sleep
    assert "self._occupancy_values(raw)" in sleep
    assert "self._observed_area_ids(" in sleep
    assert "self.settings.get(CONF_SLEEP_ROOMS," in sleep
    assert "if self._sleep_rooms_source_unavailable():" in sleep


def test_live_area_list_accepts_ids_names_aliases_and_ignores_unknown():
    actual = _resolve_live_values([
        "Bedroom", "Küche", "unknown-room", "schlafzimmer",
        "Sleeping Room", "Kitchen",
    ])
    assert actual == ("schlafzimmer", "kueche")
    assert _resolve_live_values([]) == ()


def test_all_locales_offer_help_in_both_new_steps_and_general_settings():
    for relative in ["strings.json", *[
        "translations/" + lang + ".json"
        for lang in [
            "en", "el", "de", "fr", "es", "it", "pt", "pt-BR",
            "nl", "pl", "ru", "tr", "uk", "ar", "zh-Hans",
            "zh-Hant", "ja", "ko", "sv", "cs",
        ]
    ]]:
        doc = json.loads((COMPONENT / relative).read_text(encoding="utf-8"))
        for scope in ("config", "options"):
            queue = doc[scope]["step"]["queue"]
            assert "sleep_rooms" not in queue["data"], relative
            for key in ("sleep_rooms_entity", "sleep_rooms_attribute"):
                assert len(queue["data"][key]) >= 3
                assert len(queue["data_description"][key]) >= 30
            for step, field in (
                ("sleep_rooms", "sleep_rooms_entity"),
                ("sleep_rooms_source", "sleep_rooms_attribute"),
            ):
                item = doc[scope]["step"][step]
                assert len(item["description"]) >= 30
                assert item["data"][field] == queue["data"][field]
                assert item["data_description"][field] == queue["data_description"][field]
            assert doc[scope]["error"]["invalid_sleep_source"]


def test_sleep_source_values_are_not_fixed_permanent_rooms():
    assert "CONF_SLEEP_ROOMS, [])" not in FLOW
    assert "CONF_SLEEP_ROOMS, []" not in FLOW
    assert "multiple=True" in FLOW  # Other unrelated multi-select options remain.
