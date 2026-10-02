from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(".")
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# config_flow.py
path = COMPONENT / "config_flow.py"

# Occupancy/fallback no longer belong to the generic Outputs page.
replace_once(
    path,
    '''                    CONF_CRITICAL_NOTIFY_DATA: {},
                    CONF_OCCUPANCY_SENSOR: None,
                    CONF_OCCUPANCY_ATTRIBUTE: "",
                    CONF_FALLBACK_ROOM: None,
                    CONF_FALLBACK_CHECK_DOOR: DEFAULT_FALLBACK_CHECK_DOOR,
''',
    '''                    CONF_CRITICAL_NOTIFY_DATA: {},
''',
)

replace_once(
    path,
    '''                _optional_marker(
                    CONF_OCCUPANCY_SENSOR,
                    self._value(CONF_OCCUPANCY_SENSOR, None),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                _optional_marker(
                    CONF_OCCUPANCY_ATTRIBUTE,
                    self._value(CONF_OCCUPANCY_ATTRIBUTE, ""),
                ): selector.TextSelector(),
                _optional_marker(
                    CONF_FALLBACK_ROOM,
                    self._value(CONF_FALLBACK_ROOM, None),
                ): selector.AreaSelector(),
                probatio.Required(
                    CONF_FALLBACK_CHECK_DOOR,
                    default=self._value(
                        CONF_FALLBACK_CHECK_DOOR,
                        DEFAULT_FALLBACK_CHECK_DOOR,
                    ),
                ): selector.BooleanSelector(),
''',
    "",
)

# Snapcast now proceeds to the dedicated occupancy UI.
replace_once(
    path,
    "            return await self.async_step_queue()\n\n        schema = probatio.Schema(\n",
    "            return await self.async_step_occupancy()\n\n        schema = probatio.Schema(\n",
)

queue_anchor = '''    async def async_step_queue(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
'''
if queue_anchor not in path.read_text(encoding="utf-8"):
    raise SystemExit("config_flow.py: queue anchor missing")

occupancy_methods = '''    def _occupancy_attribute_options(self) -> list[str]:
        """Return State plus live attributes for the selected occupancy entity."""
        sensor = str(self._working.get(CONF_OCCUPANCY_SENSOR, "") or "").strip()
        state = self.hass.states.get(sensor) if sensor else None
        attributes = sorted(str(key) for key in (state.attributes if state else {}))
        return ["__state__", *attributes]

    async def async_step_occupancy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure occupancy-aware routing and optional fallback."""
        if user_input is not None:
            self._store_step(
                user_input,
                {
                    CONF_OCCUPANCY_SENSOR: None,
                    CONF_FALLBACK_ROOM: None,
                    CONF_FALLBACK_CHECK_DOOR: DEFAULT_FALLBACK_CHECK_DOOR,
                },
            )
            if self._working.get(CONF_OCCUPANCY_SENSOR):
                return await self.async_step_occupancy_source()
            self._working[CONF_OCCUPANCY_ATTRIBUTE] = ""
            return await self.async_step_queue()

        schema = probatio.Schema(
            {
                _optional_marker(
                    CONF_OCCUPANCY_SENSOR,
                    self._value(CONF_OCCUPANCY_SENSOR, None),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                _optional_marker(
                    CONF_FALLBACK_ROOM,
                    self._value(CONF_FALLBACK_ROOM, None),
                ): selector.AreaSelector(),
                probatio.Required(
                    CONF_FALLBACK_CHECK_DOOR,
                    default=self._value(
                        CONF_FALLBACK_CHECK_DOOR,
                        DEFAULT_FALLBACK_CHECK_DOOR,
                    ),
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="occupancy", data_schema=schema)

    async def async_step_occupancy_source(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose whether occupied areas come from state or one live attribute."""
        sensor = str(self._working.get(CONF_OCCUPANCY_SENSOR, "") or "").strip()
        if not sensor:
            self._working[CONF_OCCUPANCY_ATTRIBUTE] = ""
            return await self.async_step_queue()

        options = self._occupancy_attribute_options()
        if user_input is not None:
            source = str(user_input.get(CONF_OCCUPANCY_ATTRIBUTE, "__state__"))
            self._working[CONF_OCCUPANCY_ATTRIBUTE] = (
                "" if source == "__state__" else source
            )
            return await self.async_step_queue()

        current = str(self._working.get(CONF_OCCUPANCY_ATTRIBUTE, "") or "")
        default = current if current in options else "__state__"
        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_OCCUPANCY_ATTRIBUTE,
                    default=default,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="occupancy_source",
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="occupancy_source",
            data_schema=schema,
            description_placeholders={"entity": sensor},
        )

'''
text = path.read_text(encoding="utf-8")
path.write_text(
    text.replace(queue_anchor, occupancy_methods + queue_anchor, 1),
    encoding="utf-8",
)

# manifest + const version
replace_once(COMPONENT / "const.py", 'VERSION: Final = "0.5.0"', 'VERSION: Final = "0.5.1"')
manifest_path = COMPONENT / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("version") != "0.5.0":
    raise SystemExit(f"Unexpected manifest version: {manifest.get('version')}")
manifest["version"] = "0.5.1"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

# Translation resources: move occupancy/fallback fields out of Outputs and give
# them their own translated steps. The source field is a dropdown, never text.
locales = {
    "strings.json": {
        "occ_title": "Occupancy routing",
        "occ_desc": "Optionally restrict announcements to occupied Home Assistant areas and configure the zero-candidate fallback.",
        "sensor": "Occupied-areas entity",
        "sensor_desc": "Select the sensor/entity that reports occupied areas. After this step you can choose its state or one of its current attributes.",
        "fallback": "Fallback room",
        "fallback_desc": "Optional area used only when occupancy routing has zero configured candidates.",
        "door": "Check occupied-room door before fallback",
        "door_desc": "When enabled, fallback is allowed only when an occupied target room has an open binary door sensor.",
        "source_title": "Occupied-areas value",
        "source_desc": "Choose the state or one current attribute of {entity} that contains the occupied area names/IDs.",
        "source": "Read occupied areas from",
        "source_field_desc": "State uses the entity state itself. Attribute choices are read live from the selected entity.",
        "state": "State",
    },
    "translations/en.json": {
        "occ_title": "Occupancy routing",
        "occ_desc": "Optionally restrict announcements to occupied Home Assistant areas and configure the zero-candidate fallback.",
        "sensor": "Occupied-areas entity",
        "sensor_desc": "Select the sensor/entity that reports occupied areas. After this step you can choose its state or one of its current attributes.",
        "fallback": "Fallback room",
        "fallback_desc": "Optional area used only when occupancy routing has zero configured candidates.",
        "door": "Check occupied-room door before fallback",
        "door_desc": "When enabled, fallback is allowed only when an occupied target room has an open binary door sensor.",
        "source_title": "Occupied-areas value",
        "source_desc": "Choose the state or one current attribute of {entity} that contains the occupied area names/IDs.",
        "source": "Read occupied areas from",
        "source_field_desc": "State uses the entity state itself. Attribute choices are read live from the selected entity.",
        "state": "State",
    },
    "translations/de.json": {
        "occ_title": "Belegungsabhängige Ausgabe",
        "occ_desc": "Beschränke Ankündigungen optional auf belegte Home-Assistant-Bereiche und konfiguriere den Fallback ohne Kandidaten.",
        "sensor": "Entität für belegte Bereiche",
        "sensor_desc": "Wähle den Sensor/die Entität, die belegte Bereiche meldet. Im nächsten Schritt kannst du den Zustand oder eines der aktuellen Attribute auswählen.",
        "fallback": "Fallback-Bereich",
        "fallback_desc": "Optionaler Bereich, der nur verwendet wird, wenn die Belegungsfilterung keine konfigurierten Kandidaten ergibt.",
        "door": "Tür des belegten Bereichs vor Fallback prüfen",
        "door_desc": "Wenn aktiviert, ist der Fallback nur erlaubt, wenn in einem belegten Zielbereich ein offener binärer Türsensor vorhanden ist.",
        "source_title": "Wert für belegte Bereiche",
        "source_desc": "Wähle den Zustand oder ein aktuelles Attribut von {entity}, das die Namen/IDs der belegten Bereiche enthält.",
        "source": "Belegte Bereiche lesen aus",
        "source_field_desc": "Zustand verwendet den Entitätszustand selbst. Die Attribute werden live aus der ausgewählten Entität gelesen.",
        "state": "Zustand",
    },
    "translations/el.json": {
        "occ_title": "Δρομολόγηση βάσει παρουσίας",
        "occ_desc": "Προαιρετικά περιόρισε τις ανακοινώσεις στις κατειλημμένες περιοχές του Home Assistant και ρύθμισε την εφεδρική περιοχή όταν δεν υπάρχουν candidates.",
        "sensor": "Οντότητα κατειλημμένων περιοχών",
        "sensor_desc": "Επίλεξε τον αισθητήρα/οντότητα που αναφέρει τις κατειλημμένες περιοχές. Στο επόμενο βήμα επιλέγεις την κατάσταση ή ένα από τα τρέχοντα attributes του.",
        "fallback": "Εφεδρική περιοχή",
        "fallback_desc": "Προαιρετική περιοχή που χρησιμοποιείται μόνο όταν η δρομολόγηση βάσει παρουσίας δεν αφήνει κανένα ρυθμισμένο candidate.",
        "door": "Έλεγχος πόρτας πριν την εφεδρική δρομολόγηση",
        "door_desc": "Όταν είναι ενεργό, το fallback επιτρέπεται μόνο αν μία κατειλημμένη περιοχή-στόχος έχει ανοιχτό binary sensor πόρτας.",
        "source_title": "Τιμή κατειλημμένων περιοχών",
        "source_desc": "Επίλεξε την κατάσταση ή ένα τρέχον attribute του {entity} που περιέχει τα ονόματα/ID των κατειλημμένων περιοχών.",
        "source": "Ανάγνωση κατειλημμένων περιοχών από",
        "source_field_desc": "Η Κατάσταση χρησιμοποιεί την ίδια την κατάσταση της οντότητας. Τα attributes διαβάζονται ζωντανά από την επιλεγμένη οντότητα.",
        "state": "Κατάσταση",
    },
}

for relative, labels in locales.items():
    resource_path = COMPONENT / relative
    data = json.loads(resource_path.read_text(encoding="utf-8"))
    for section_name in ("config", "options"):
        steps = data[section_name]["step"]
        outputs = steps["outputs"]
        for key in (
            "occupancy_sensor",
            "occupancy_attribute",
            "fallback_room",
            "fallback_check_door",
        ):
            outputs.get("data", {}).pop(key, None)
            outputs.get("data_description", {}).pop(key, None)

        # Inserted as regular dict keys; JSON order is cosmetic in HA.
        steps["occupancy"] = {
            "title": labels["occ_title"],
            "description": labels["occ_desc"],
            "data": {
                "occupancy_sensor": labels["sensor"],
                "fallback_room": labels["fallback"],
                "fallback_check_door": labels["door"],
            },
            "data_description": {
                "occupancy_sensor": labels["sensor_desc"],
                "fallback_room": labels["fallback_desc"],
                "fallback_check_door": labels["door_desc"],
            },
        }
        steps["occupancy_source"] = {
            "title": labels["source_title"],
            "description": labels["source_desc"],
            "data": {
                "occupancy_attribute": labels["source"],
            },
            "data_description": {
                "occupancy_attribute": labels["source_field_desc"],
            },
        }

    selector_block = data.setdefault("selector", {})
    selector_block["occupancy_source"] = {
        "options": {
            "__state__": labels["state"],
        }
    }
    resource_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

# Tests
resources_test = ROOT / "tests" / "test_resources.py"
text = resources_test.read_text(encoding="utf-8")
text = text.replace(
    'expected_steps = {"outputs", "notification_profile", "tts", "snapcast", "queue"}',
    'expected_steps = {"outputs", "notification_profile", "tts", "snapcast", "occupancy", "occupancy_source", "queue"}',
)
text = text.replace(
    '    assert manifest["version"] == "0.5.0"\n',
    '    assert manifest["version"] == "0.5.1"\n',
)
resources_test.write_text(text, encoding="utf-8")

occupancy_test = ROOT / "tests" / "test_occupancy_filter.py"
text = occupancy_test.read_text(encoding="utf-8")
text += '''


def test_occupancy_ui_uses_live_dropdown_not_free_text() -> None:
    flow = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    assert "async def async_step_occupancy(" in flow
    assert "async def async_step_occupancy_source(" in flow
    assert 'return ["__state__", *attributes]' in flow
    assert 'translation_key="occupancy_source"' in flow
    source_block = flow[
        flow.index("async def async_step_occupancy_source"):
        flow.index("async def async_step_queue")
    ]
    assert "selector.SelectSelector(" in source_block
    assert "selector.TextSelector()" not in source_block


def test_occupancy_and_fallback_are_not_on_generic_outputs_page() -> None:
    import json

    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    for section in ("config", "options"):
        outputs = strings[section]["step"]["outputs"]["data"]
        assert "occupancy_sensor" not in outputs
        assert "occupancy_attribute" not in outputs
        assert "fallback_room" not in outputs
        assert "fallback_check_door" not in outputs
        occupancy = strings[section]["step"]["occupancy"]["data"]
        assert {"occupancy_sensor", "fallback_room", "fallback_check_door"} <= set(occupancy)
        source = strings[section]["step"]["occupancy_source"]["data"]
        assert set(source) == {"occupancy_attribute"}
'''
occupancy_test.write_text(text, encoding="utf-8")

# Changelog
changelog = ROOT / "CHANGELOG.md"
text = changelog.read_text(encoding="utf-8")
heading = "# Changelog\n\n"
if not text.startswith(heading):
    raise SystemExit("Unexpected changelog header")
entry = '''## 0.5.1 - 2026-10-02

- Moved occupancy and fallback settings out of the generic Outputs page into a
  dedicated translated Occupancy routing step.
- Replaced the free-text occupancy attribute field with a live dropdown built
  from the selected entity's current attributes.
- Added State as an explicit translated dropdown choice; internally it keeps the
  existing empty-attribute representation, so routing behavior is unchanged.
- The occupancy entity is selected first, then the source dropdown is generated
  from that exact entity.
- No queue, routing, availability-timeout, or background-task lifecycle behavior
  changed.

'''
changelog.write_text(heading + entry + text[len(heading):], encoding="utf-8")

print("Applied Announcement Hub 0.5.1 occupancy source UI")
