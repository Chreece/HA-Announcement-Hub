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


# const.py
path = COMPONENT / "const.py"
replace_once(path, 'VERSION: Final = "0.3.4"', 'VERSION: Final = "0.4.0"')
replace_once(
    path,
    'ATTR_COMPANION_TTS: Final = "companion_tts"\n',
    'ATTR_COMPANION_TTS: Final = "companion_tts"\nATTR_OCCUPIED_ONLY: Final = "occupied_only"\n',
)
replace_once(
    path,
    'CONF_NOTIFY_PROFILES: Final = "notify_profiles"\n',
    'CONF_NOTIFY_PROFILES: Final = "notify_profiles"\nCONF_OCCUPANCY_SENSOR: Final = "occupancy_sensor"\nCONF_OCCUPANCY_ATTRIBUTE: Final = "occupancy_attribute"\n',
)
replace_once(
    path,
    'DEFAULT_CRITICAL_NOTIFY_DATA: Final = {}\n',
    'DEFAULT_CRITICAL_NOTIFY_DATA: Final = {}\nDEFAULT_OCCUPIED_ONLY: Final = True\n',
)

# config_flow.py
path = COMPONENT / "config_flow.py"
replace_once(
    path,
    '    CONF_NOTIFY_PROFILES,\n',
    '    CONF_NOTIFY_PROFILES,\n    CONF_OCCUPANCY_ATTRIBUTE,\n    CONF_OCCUPANCY_SENSOR,\n',
)
replace_once(
    path,
    '                    CONF_CRITICAL_NOTIFY_DATA: {},\n',
    '                    CONF_CRITICAL_NOTIFY_DATA: {},\n                    CONF_OCCUPANCY_SENSOR: None,\n                    CONF_OCCUPANCY_ATTRIBUTE: "",\n',
)
marker = '''                probatio.Optional(
                    CONF_CRITICAL_NOTIFY_DATA,
                    default=self._value(
                        CONF_CRITICAL_NOTIFY_DATA,
                        DEFAULT_CRITICAL_NOTIFY_DATA,
                    ),
                ): selector.ObjectSelector(),
'''
replace_once(
    path,
    marker,
    marker
    + '''                _optional_marker(
                    CONF_OCCUPANCY_SENSOR,
                    self._value(CONF_OCCUPANCY_SENSOR, None),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                _optional_marker(
                    CONF_OCCUPANCY_ATTRIBUTE,
                    self._value(CONF_OCCUPANCY_ATTRIBUTE, ""),
                ): selector.TextSelector(),
''',
)

# __init__.py
path = COMPONENT / "__init__.py"
replace_once(
    path,
    '    ATTR_NOTIFY_DATA,\n',
    '    ATTR_NOTIFY_DATA,\n    ATTR_OCCUPIED_ONLY,\n',
)
replace_once(
    path,
    '    DEFAULT_COMPANION_TTS_WPM,\n    DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT,\n',
    '    DEFAULT_COMPANION_TTS_WPM,\n    DEFAULT_OCCUPIED_ONLY,\n    DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT,\n',
)
replace_once(
    path,
    '            probatio.Optional(ATTR_COMPANION_TTS, default=False): bool,\n',
    '            probatio.Optional(ATTR_COMPANION_TTS, default=False): bool,\n            probatio.Optional(ATTR_OCCUPIED_ONLY, default=DEFAULT_OCCUPIED_ONLY): bool,\n',
)
replace_once(
    path,
    '            companion_tts=call.data[ATTR_COMPANION_TTS],\n',
    '            companion_tts=call.data[ATTR_COMPANION_TTS],\n            occupied_only=call.data[ATTR_OCCUPIED_ONLY],\n',
)

# manager.py
path = COMPONENT / "manager.py"
replace_once(path, "import logging\n", "import json\nimport logging\n")
replace_once(path, "import math\n", "import math\nimport re\n")
replace_once(
    path,
    '    CONF_NOTIFY_PROFILES,\n',
    '    CONF_NOTIFY_PROFILES,\n    CONF_OCCUPANCY_ATTRIBUTE,\n    CONF_OCCUPANCY_SENSOR,\n',
)
signature = '''async def async_enqueue(
        self,
        *,
        text_tts: str | None,
        text_notify: str | None,
        outputs: Sequence[str] | str | None,
        requested_services: Sequence[str] | str | None,
        level: str,
        title: str | None,
        notify_data: Mapping[str, Any] | None,
        language: str | None,
        tts_options: Mapping[str, Any] | None,
        companion_tts: bool,
    ) -> AnnouncementJob:'''
replace_once(
    path,
    signature,
    signature.replace(
        "        companion_tts: bool,\n",
        "        companion_tts: bool,\n        occupied_only: bool,\n",
    ),
)
replace_once(
    path,
    '''        output_area_ids = self._resolve_area_ids(self._ensure_list(outputs))
        requested = self._ensure_list(requested_services)
        configured = self._configured_outputs()
        selected = self._select_requested_outputs(
            requested,
            level=level,
            tts_engines=configured[0],
            notify_outputs=configured[1],
            snapcast_clients=configured[2],
            companion_entries=configured[3],
            companion_tts=bool(companion_tts),
        )
''',
    '''        requested_output_area_ids = self._resolve_area_ids(
            self._ensure_list(outputs)
        )
        occupied_area_ids = self._occupied_area_ids() if occupied_only else None
        occupancy_filter_active = occupied_area_ids is not None
        if occupancy_filter_active:
            occupied_set = set(occupied_area_ids)
            output_area_ids = (
                tuple(
                    area_id
                    for area_id in requested_output_area_ids
                    if area_id in occupied_set
                )
                if requested_output_area_ids
                else occupied_area_ids
            )
        else:
            output_area_ids = requested_output_area_ids

        requested = self._ensure_list(requested_services)
        configured = self._configured_outputs()
        selected = self._select_requested_outputs(
            requested,
            level=level,
            tts_engines=configured[0],
            notify_outputs=configured[1],
            snapcast_clients=configured[2],
            companion_entries=configured[3],
            companion_tts=bool(companion_tts),
        )
''',
)
replace_once(
    path,
    '''        player_value = self.settings.get(CONF_TTS_MEDIA_PLAYER)
        player = str(player_value) if player_value else None
        notify_records = resolve_notify_outputs(self.hass, selected[1])
        companion_records = resolve_companion_tts_outputs(self.hass, selected[3])
        notify_output_areas = {
            output.ref: output.area_id for output in notify_records
        }
''',
    '''        player_value = self.settings.get(CONF_TTS_MEDIA_PLAYER)
        player = str(player_value) if player_value else None
        notify_records = resolve_notify_outputs(self.hass, selected[1])
        companion_records = resolve_companion_tts_outputs(self.hass, selected[3])

        if occupancy_filter_active:
            effective_areas = set(output_area_ids)
            notify_records = tuple(
                output
                for output in notify_records
                if output.area_id is not None and output.area_id in effective_areas
            )
            snapcast_clients = tuple(
                entity_id
                for entity_id in selected[2]
                if (area_id := entity_area_id(self.hass, entity_id)) is not None
                and area_id in effective_areas
            )
            companion_records = tuple(
                output
                for output in companion_records
                if output.area_id is not None and output.area_id in effective_areas
            )
            selected = (
                selected[0],
                tuple(output.ref for output in notify_records),
                snapcast_clients,
                tuple(output.entry_id for output in companion_records),
            )

        notify_output_areas = {
            output.ref: output.area_id for output in notify_records
        }
''',
)
replace_once(
    path,
    '''        plan = build_delivery_plan(
            text_tts=text_tts,
            text_notify=text_notify,
            level=level,
            minimum_tts_level=minimum_tts_level,
            tts_engines=selected[0],
            notify_outputs=selected[1],
            snapcast_clients=selected[2],
            companion_tts_entries=selected[3],
            server_tts_enabled=bool(player and selected[0]),
        )
        if not plan.has_output:
''',
    '''        server_tts_enabled = bool(player and selected[0])
        if occupancy_filter_active and server_tts_enabled:
            if configured[2]:
                server_tts_enabled = bool(selected[2])
            else:
                player_area = entity_area_id(self.hass, player) if player else None
                server_tts_enabled = (
                    player_area is not None and player_area in set(output_area_ids)
                )

        plan = build_delivery_plan(
            text_tts=text_tts,
            text_notify=text_notify,
            level=level,
            minimum_tts_level=minimum_tts_level,
            tts_engines=selected[0],
            notify_outputs=selected[1],
            snapcast_clients=selected[2],
            companion_tts_entries=selected[3],
            server_tts_enabled=server_tts_enabled,
        )
        if not plan.has_output and not occupancy_filter_active:
''',
)
anchor = '    def _resolve_area_ids(self, values: Sequence[str]) -> tuple[str, ...]:\n'
text = path.read_text(encoding="utf-8")
if anchor not in text:
    raise SystemExit("manager.py: area resolver anchor missing")
helper = '''    def _occupied_area_ids(self) -> tuple[str, ...] | None:
        """Resolve occupied areas from the configured sensor state or attribute."""
        sensor = str(self.settings.get(CONF_OCCUPANCY_SENSOR, "") or "").strip()
        if not sensor:
            return None
        state = self.hass.states.get(sensor)
        if state is None or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            _LOGGER.debug("Occupancy sensor %s is unavailable", sensor)
            return ()

        attribute = str(
            self.settings.get(CONF_OCCUPANCY_ATTRIBUTE, "") or ""
        ).strip()
        raw: Any = state.attributes.get(attribute) if attribute else state.state
        values = self._occupancy_values(raw)
        if not values:
            return ()

        registry = ar.async_get(self.hass)
        areas = registry.async_list_areas()
        by_name = {area.name.casefold(): area.id for area in areas}
        by_alias = {
            alias.casefold(): area.id
            for area in areas
            for alias in (area.aliases or set())
        }
        resolved: list[str] = []
        unknown: list[str] = []
        for value in values:
            if registry.async_get_area(value):
                resolved.append(value)
                continue
            key = value.casefold()
            if area_id := by_name.get(key) or by_alias.get(key):
                resolved.append(area_id)
            else:
                unknown.append(value)

        if unknown:
            _LOGGER.debug(
                "Occupancy source %s reported unknown area value(s): %s",
                sensor,
                unknown,
            )
        return tuple(dict.fromkeys(resolved))

    @staticmethod
    def _occupancy_values(raw: Any) -> list[str]:
        """Normalise a state/attribute into area names or IDs."""
        if raw is None:
            return []
        if isinstance(raw, Mapping):
            return [
                str(key).strip()
                for key, enabled in raw.items()
                if enabled and str(key).strip()
            ]
        if isinstance(raw, (list, tuple, set)):
            return [str(item).strip() for item in raw if str(item).strip()]

        value = str(raw).strip()
        if not value:
            return []
        if value.startswith("[") and value.endswith("]"):
            try:
                decoded = json.loads(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                decoded = None
            if isinstance(decoded, list):
                return [
                    str(item).strip()
                    for item in decoded
                    if str(item).strip()
                ]
        return [
            part.strip().strip("'\\\"")
            for part in re.split(r"[,;\\n]+", value)
            if part.strip().strip("'\\\"")
        ]

'''
path.write_text(text.replace(anchor, helper + anchor, 1), encoding="utf-8")

# services.yaml
path = COMPONENT / "services.yaml"
replace_once(
    path,
    '''        companion_tts:
          default: false
          selector:
            boolean:
''',
    '''        companion_tts:
          default: false
          selector:
            boolean:
        occupied_only:
          default: true
          selector:
            boolean:
''',
)

# strings and translations
translations = {
    "strings.json": (
        "Occupied-areas sensor",
        "Occupied-areas attribute",
        "Optional sensor whose state contains occupied Home Assistant area names/IDs, for example Wohnzimmer,Gästezimmer. When configured, occupied-only delivery can automatically restrict outputs to those areas.",
        "Optional attribute on the occupied-areas sensor that contains the area list. Leave empty to use the sensor state itself.",
        "Only occupied areas",
        "Default: enabled. When an occupied-areas sensor is configured, restrict this announcement to outputs belonging to the currently occupied areas. An explicit output list is intersected with occupancy. Disable to ignore occupancy for this call.",
    ),
    "translations/en.json": (
        "Occupied-areas sensor",
        "Occupied-areas attribute",
        "Optional sensor whose state contains occupied Home Assistant area names/IDs, for example Wohnzimmer,Gästezimmer. When configured, occupied-only delivery can automatically restrict outputs to those areas.",
        "Optional attribute on the occupied-areas sensor that contains the area list. Leave empty to use the sensor state itself.",
        "Only occupied areas",
        "Default: enabled. When an occupied-areas sensor is configured, restrict this announcement to outputs belonging to the currently occupied areas. An explicit output list is intersected with occupancy. Disable to ignore occupancy for this call.",
    ),
    "translations/de.json": (
        "Sensor für belegte Bereiche",
        "Attribut für belegte Bereiche",
        "Optionaler Sensor, dessen Zustand belegte Home-Assistant-Bereiche als Namen/IDs enthält, z. B. Wohnzimmer,Gästezimmer. Bei Konfiguration kann die Ausgabe automatisch auf diese Bereiche beschränkt werden.",
        "Optionales Attribut des Belegungssensors, das die Bereichsliste enthält. Leer lassen, um den Sensorzustand selbst zu verwenden.",
        "Nur belegte Bereiche",
        "Standard: aktiviert. Wenn ein Belegungssensor konfiguriert ist, wird diese Ankündigung auf Ausgaben in aktuell belegten Bereichen beschränkt. Eine explizite Bereichsauswahl wird mit der Belegung geschnitten. Deaktivieren, um die Belegung für diesen Aufruf zu ignorieren.",
    ),
    "translations/el.json": (
        "Αισθητήρας κατειλημμένων περιοχών",
        "Χαρακτηριστικό κατειλημμένων περιοχών",
        "Προαιρετικός αισθητήρας του οποίου η κατάσταση περιέχει ονόματα/ID κατειλημμένων περιοχών του Home Assistant, π.χ. Wohnzimmer,Gästezimmer. Όταν ρυθμιστεί, η έξοδος μπορεί να περιορίζεται αυτόματα σε αυτές τις περιοχές.",
        "Προαιρετικό attribute του αισθητήρα που περιέχει τη λίστα περιοχών. Άφησέ το κενό για χρήση της ίδιας της κατάστασης του αισθητήρα.",
        "Μόνο κατειλημμένες περιοχές",
        "Προεπιλογή: ενεργό. Όταν έχει ρυθμιστεί αισθητήρας κατειλημμένων περιοχών, η ανακοίνωση περιορίζεται σε outputs που ανήκουν στις περιοχές που είναι τώρα κατειλημμένες. Αν δοθούν ρητά output areas, χρησιμοποιείται η τομή τους με την παρουσία. Απενεργοποίησέ το για να αγνοηθεί η παρουσία σε αυτή την κλήση.",
    ),
}
for relative, labels in translations.items():
    path = COMPONENT / relative
    data = json.loads(path.read_text(encoding="utf-8"))
    for section in ("config", "options"):
        outputs = data[section]["step"]["outputs"]
        outputs["data"]["occupancy_sensor"] = labels[0]
        outputs["data"]["occupancy_attribute"] = labels[1]
        outputs["data_description"]["occupancy_sensor"] = labels[2]
        outputs["data_description"]["occupancy_attribute"] = labels[3]
        queue_desc = outputs
    data["services"]["send"]["fields"]["occupied_only"] = {
        "name": labels[4],
        "description": labels[5],
    }
    # Keep v0.3.4 silent-timeout behavior accurately documented.
    queue = data["config"]["step"]["queue"]["data_description"]
    if "output_availability_timeout" in queue:
        queue["output_availability_timeout"] = (
            "Available outputs are delivered immediately. Unavailable or temporarily "
            "failing outputs are retried during this window and silently skipped if "
            "they still cannot receive the announcement."
            if relative.endswith("en.json") or relative == "strings.json"
            else queue["output_availability_timeout"]
        )
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# manifest
path = COMPONENT / "manifest.json"
manifest = json.loads(path.read_text(encoding="utf-8"))
if manifest.get("version") != "0.3.4":
    raise SystemExit(f"Unexpected manifest version: {manifest.get('version')}")
manifest["version"] = "0.4.0"
path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

# tests
path = ROOT / "tests" / "test_resources.py"
replace_once(
    path,
    '        "output_availability_timeout",\n',
    '        "output_availability_timeout",\n        "occupancy_sensor",\n        "occupancy_attribute",\n',
)
replace_once(
    path,
    '    assert companion_tts["default"] is False\n    assert "boolean" in companion_tts["selector"]\n',
    '    assert companion_tts["default"] is False\n    assert "boolean" in companion_tts["selector"]\n    occupied_only = services["send"]["fields"]["routing"]["fields"]["occupied_only"]\n    assert occupied_only["default"] is True\n    assert "boolean" in occupied_only["selector"]\n',
)
replace_once(
    path,
    '    assert manifest["version"] == "0.3.4"\n',
    '    assert manifest["version"] == "0.4.0"\n',
)

(ROOT / "tests" / "test_occupancy_filter.py").write_text(
    '''"""Regression contracts for occupied-area output filtering."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def test_occupancy_source_supports_state_attribute_and_common_list_formats() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "def _occupied_area_ids(" in manager
    assert "CONF_OCCUPANCY_SENSOR" in manager
    assert "CONF_OCCUPANCY_ATTRIBUTE" in manager
    assert "state.attributes.get(attribute) if attribute else state.state" in manager
    assert "json.loads(value)" in manager
    assert 're.split(r"[,;\\\\n]+", value)' in manager


def test_occupancy_filter_is_applied_before_job_is_frozen() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "occupancy_filter_active = occupied_area_ids is not None" in manager
    assert "if output.area_id is not None and output.area_id in effective_areas" in manager
    assert "server_tts_enabled = bool(selected[2])" in manager
    assert "if not plan.has_output and not occupancy_filter_active:" in manager


def test_occupied_only_defaults_true_and_does_not_touch_task_lifecycle() -> None:
    init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "ATTR_OCCUPIED_ONLY" in init
    assert "default=DEFAULT_OCCUPIED_ONLY" in init
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(") == 2
''',
    encoding="utf-8",
)

# changelog
path = ROOT / "CHANGELOG.md"
text = path.read_text(encoding="utf-8")
heading = "# Changelog\n\n"
if not text.startswith(heading):
    raise SystemExit("Unexpected changelog header")
entry = '''## 0.4.0 - 2026-10-02

- Added an optional occupied-areas sensor with an optional attribute containing
  Home Assistant area names/IDs.
- Added `occupied_only` to `announcement_hub.send`, enabled by default.
  Explicit output areas are intersected with occupancy; an omitted output targets
  the currently occupied areas.
- Occupancy filtering is capability-neutral: each occupied area receives only
  the configured output types actually present in that area.
- Outputs without an area are excluded while occupied-only filtering is active.
- An unavailable occupancy sensor or an empty occupied-area list is a silent
  no-op, never a broadcast fallback.
- Existing unavailable-output retry/timeout behavior and config-entry background
  task lifecycle remain unchanged.

'''
path.write_text(heading + entry + text[len(heading):], encoding="utf-8")

# README
path = ROOT / "README.md"
text = path.read_text(encoding="utf-8")
anchor = "## Main action\n"
if anchor not in text:
    raise SystemExit("README anchor missing")
section = '''## Occupancy-aware routing

Optionally configure an occupied-areas sensor. Its state can contain comma,
semicolon, or newline-separated Home Assistant area names/IDs, or a configured
attribute can contain a list of areas.

`announcement_hub.send` defaults to `occupied_only: true`. With a configured
occupancy sensor, omitted `output` targets the occupied areas; explicit areas
are intersected with occupancy. Filtering is capability-neutral, so a room with
only TTS receives speech and a room with only visual notify outputs receives only
those notifications. Unavailable outputs still wait for the configured
availability timeout and are silently skipped afterward.

Use `occupied_only: false` to ignore occupancy for one call. Without a
configured occupancy sensor, the option has no effect.

'''
path.write_text(text.replace(anchor, section + anchor, 1), encoding="utf-8")

print("Applied Announcement Hub 0.4.0 occupancy-aware routing")
