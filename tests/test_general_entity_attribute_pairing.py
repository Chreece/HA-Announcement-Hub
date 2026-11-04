"""General settings entity/attribute layout and numbered reconfigure menus.

Execute the real config-flow methods with small selector stubs, without
requiring Home Assistant to be installed on the CI runner.
"""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
SOURCE = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
MIXIN = next(node for node in TREE.body if isinstance(node, ast.ClassDef)
             and node.name == "_AnnouncementFlowMixin")
GENERAL = next(node for node in MIXIN.body if isinstance(node, ast.AsyncFunctionDef)
               and node.name == "async_step_queue")

MENU_ORDER = (
    "edit_outputs", "edit_tts", "edit_profiles", "edit_general",
    "edit_people", "edit_advanced_ai", "edit_audio",
    "edit_room_safety", "edit_all",
)


def test_every_reconfigure_menu_numbers_all_nine_sections():
    files = [COMPONENT / "strings.json", *sorted(
        (COMPONENT / "translations").glob("*.json")
    )]
    assert len(files) == 21
    menu = next(node for node in TREE.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and
                        target.id == "EDIT_MENU_OPTIONS" for target in node.targets))
    assert tuple(ast.literal_eval(menu.value)) == MENU_ORDER
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for scope, step in (("config", "reconfigure"), ("options", "init")):
            choices = data[scope]["step"][step]["menu_options"]
            assert set(choices) == set(MENU_ORDER), (path, scope)
            for n, key in enumerate(MENU_ORDER, start=1):
                digit = "١٢٣٤٥٦٧٨٩"[n - 1] if path.name == "ar.json" else str(n)
                label = choices[key]
                assert label.startswith(f"{digit}. ") and label[len(digit)+2:].strip(), (
                    path, scope, key, label,
                )
        assert (
            data["config"]["step"]["reconfigure"]["menu_options"]
            == data["options"]["step"]["init"]["menu_options"]
        ), path


class Marker:
    def __init__(self, name, default=None):
        self.schema = name
        self.default = default

    def __hash__(self):
        return hash(self.schema)

    def __eq__(self, other):
        return isinstance(other, Marker) and self.schema == other.schema


def _flow():
    methods = [
        node for node in MIXIN.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and node.name in {
            "async_step_queue", "_sleep_rooms_attribute_options",
            "_occupancy_attribute_options",
        }
    ]
    names = {
        node.id for method in methods for node in ast.walk(method)
        if isinstance(node, ast.Name)
    }
    env = {
        name: name.removeprefix("CONF_").lower()
        for name in names if name.startswith("CONF_")
    }
    env.update({
        name: name.removeprefix("DEFAULT_").lower()
        for name in names if name.startswith("DEFAULT_")
    })
    env.update(
        probatio=SimpleNamespace(
            Marker=Marker,
            Required=lambda key, default=None: Marker(key, default),
            Optional=lambda key, default=None: Marker(key, default),
            Schema=lambda fields: fields,
        ),
        selector=SimpleNamespace(
            SelectOptionDict=lambda **fields: fields,
            SelectSelectorConfig=lambda **fields: fields,
            SelectSelector=lambda cfg: cfg,
            EntitySelector=lambda *args, **kwargs: "entity",
            TextSelector=lambda *args, **kwargs: "text",
            BooleanSelector=lambda *args, **kwargs: "boolean",
            AreaSelector=lambda *args, **kwargs: "area",
            ObjectSelector=lambda *args, **kwargs: "object",
            LabelSelector=lambda *args, **kwargs: "label",
            NumberSelector=lambda cfg: cfg,
            NumberSelectorConfig=lambda **fields: fields,
            SelectSelectorMode=SimpleNamespace(DROPDOWN="dropdown"),
            NumberSelectorMode=SimpleNamespace(BOX="box"),
        ),
        _optional_marker=lambda key, value: Marker(key, value),
        _known_multi_select=lambda options: options,
        provider_label=lambda hass, key: key,
        CHANNEL_FALLBACK_MODES=("both",),
    )
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=methods, type_ignores=[],
    )), "live Announcement Hub General settings", "exec"), env)

    class FakeFlow:
        def __init__(self):
            self._working = {
                "notify_outputs": ["entity:notify.phone"],
                "occupancy_sensor": "sensor.presence_old",
                "occupancy_attribute": "occupied_rooms",
                "sleep_rooms_entity": "sensor.sleep_old",
                "sleep_rooms_attribute": "sleeping_rooms",
            }
            states = {
                "sensor.presence_old": SimpleNamespace(
                    attributes={"occupied_rooms": ["kitchen"]},
                ),
                "sensor.sleep_old": SimpleNamespace(
                    attributes={"sleeping_rooms": ["bedroom"]},
                ),
                "sensor.presence_new": SimpleNamespace(
                    attributes={"current_areas": ["living"]},
                ),
                "sensor.sleep_new": SimpleNamespace(
                    attributes={"new_sleeping_areas": ["bedroom"]},
                ),
            }
            self.hass = SimpleNamespace(states=SimpleNamespace(get=states.get))

        def _value(self, name, default):
            return self._working.get(name, default)

        def _ai_agent_options(self):
            return []

        def _ai_fallback_agent_options(self):
            return []

        def _sleep_written_recipient_options(self):
            return [], []

        async def _async_finish(self):
            return {"step_id": "finished", "data": dict(self._working)}

        def async_show_form(self, **kwargs):
            return kwargs

    for method in methods:
        setattr(FakeFlow, method.name, env[method.name])
    return FakeFlow()


def _fields(form):
    return [(marker.schema, marker.default, selector_value)
            for marker, selector_value in form["data_schema"].items()]


def test_occupancy_and_sleep_attribute_selectors_are_directly_below_their_entity():
    flow = _flow()
    form = asyncio.run(flow.async_step_queue())
    fields = _fields(form)
    names = [name for name, _, _ in fields]
    assert names[names.index("occupancy_sensor"):names.index("sleep_rooms_attribute") + 1] == [
        "occupancy_sensor", "occupancy_attribute",
        "sleep_rooms_entity", "sleep_rooms_attribute",
    ]
    by_key = {name: (default, component) for name, default, component in fields}
    assert by_key["occupancy_attribute"][0] == "occupied_rooms"
    assert by_key["sleep_rooms_attribute"][0] == "sleeping_rooms"
    assert {item["value"] for item in by_key["occupancy_attribute"][1]["options"]} == {
        "state", "occupied_rooms",
    }
    assert {item["value"] for item in by_key["sleep_rooms_attribute"][1]["options"]} == {
        "state", "sleeping_rooms",
    }


def test_new_entities_reload_their_own_attribute_dropdowns_without_stale_selections():
    flow = _flow()
    first = asyncio.run(flow.async_step_queue({
        "occupancy_sensor": "sensor.presence_new",
        "occupancy_attribute": "occupied_rooms",
        "sleep_rooms_entity": "sensor.sleep_new",
        "sleep_rooms_attribute": "sleeping_rooms",
        "default_title": "Keep my title",
        "sleep_fallback_outputs": [],
    }))
    assert first["step_id"] == "queue"
    assert flow._working["occupancy_attribute"] == ""
    assert flow._working["sleep_rooms_attribute"] == ""
    assert flow._working["default_title"] == "Keep my title"
    fields = {name: (default, widget) for name, default, widget in _fields(first)}
    assert {entry["value"] for entry in fields["occupancy_attribute"][1]["options"]} == {
        "state", "current_areas",
    }
    assert {entry["value"] for entry in fields["sleep_rooms_attribute"][1]["options"]} == {
        "state", "new_sleeping_areas",
    }
    second = asyncio.run(flow.async_step_queue({
        "occupancy_sensor": "sensor.presence_new",
        "occupancy_attribute": "current_areas",
        "sleep_rooms_entity": "sensor.sleep_new",
        "sleep_rooms_attribute": "new_sleeping_areas",
        "default_title": "Keep my title",
        "sleep_fallback_outputs": [],
    }))
    assert second["step_id"] == "finished"
    assert second["data"]["occupancy_attribute"] == "current_areas"
    assert second["data"]["sleep_rooms_attribute"] == "new_sleeping_areas"
    assert second["data"]["default_title"] == "Keep my title"


def test_offline_sources_do_not_forget_saved_attributes():
    flow = _flow()
    flow.hass.states.get = lambda entity: None
    form = asyncio.run(flow.async_step_queue())
    fields = {name: (default, widget) for name, default, widget in _fields(form)}
    assert "occupied_rooms" in {
        option["value"] for option in fields["occupancy_attribute"][1]["options"]
    }
    assert "sleeping_rooms" in {
        option["value"] for option in fields["sleep_rooms_attribute"][1]["options"]
    }
