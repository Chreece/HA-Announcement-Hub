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
replace_once(path, 'VERSION: Final = "0.4.0"', 'VERSION: Final = "0.5.0"')
replace_once(
    path,
    'CONF_OCCUPANCY_ATTRIBUTE: Final = "occupancy_attribute"\n',
    'CONF_OCCUPANCY_ATTRIBUTE: Final = "occupancy_attribute"\n'
    'CONF_FALLBACK_ROOM: Final = "fallback_room"\n'
    'CONF_FALLBACK_CHECK_DOOR: Final = "fallback_check_door"\n',
)
replace_once(
    path,
    'DEFAULT_OCCUPIED_ONLY: Final = True\n',
    'DEFAULT_OCCUPIED_ONLY: Final = True\nDEFAULT_FALLBACK_CHECK_DOOR: Final = True\n',
)

# config_flow.py
path = COMPONENT / "config_flow.py"
replace_once(
    path,
    '    CONF_DISPATCH_ORDER,\n    CONF_IDLE_TIMEOUT,\n',
    '    CONF_DISPATCH_ORDER,\n'
    '    CONF_FALLBACK_CHECK_DOOR,\n'
    '    CONF_FALLBACK_ROOM,\n'
    '    CONF_IDLE_TIMEOUT,\n',
)
replace_once(
    path,
    '    DEFAULT_IDLE_TIMEOUT,\n',
    '    DEFAULT_FALLBACK_CHECK_DOOR,\n    DEFAULT_IDLE_TIMEOUT,\n',
)
replace_once(
    path,
    '                    CONF_OCCUPANCY_ATTRIBUTE: "",\n',
    '                    CONF_OCCUPANCY_ATTRIBUTE: "",\n'
    '                    CONF_FALLBACK_ROOM: None,\n'
    '                    CONF_FALLBACK_CHECK_DOOR: DEFAULT_FALLBACK_CHECK_DOOR,\n',
)
marker = '''                _optional_marker(
                    CONF_OCCUPANCY_ATTRIBUTE,
                    self._value(CONF_OCCUPANCY_ATTRIBUTE, ""),
                ): selector.TextSelector(),
'''
replace_once(
    path,
    marker,
    marker
    + '''                _optional_marker(
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
)

# manager.py
path = COMPONENT / "manager.py"
replace_once(
    path,
    '    ATTR_ENTITY_ID,\n    STATE_OFF,\n',
    '    ATTR_ENTITY_ID,\n    STATE_OFF,\n    STATE_ON,\n',
)
replace_once(
    path,
    '    CONF_IDLE_TIMEOUT,\n',
    '    CONF_FALLBACK_CHECK_DOOR,\n'
    '    CONF_FALLBACK_ROOM,\n'
    '    CONF_IDLE_TIMEOUT,\n',
)
replace_once(
    path,
    '    DEFAULT_IDLE_TIMEOUT,\n',
    '    DEFAULT_FALLBACK_CHECK_DOOR,\n    DEFAULT_IDLE_TIMEOUT,\n',
)

old = '''        player_value = self.settings.get(CONF_TTS_MEDIA_PLAYER)
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
        configured_profiles = self.settings.get(CONF_NOTIFY_PROFILES, {})
        if not isinstance(configured_profiles, Mapping):
            configured_profiles = {}
        notify_output_profiles = {
            output.ref: resolve_notify_profile(
                configured_profiles, output.integration
            )
            for output in notify_records
        }
        snapcast_client_areas = {
            entity_id: entity_area_id(self.hass, entity_id)
            for entity_id in selected[2]
        }
        companion_tts_entry_areas = {
            output.entry_id: output.area_id for output in companion_records
        }
        server_tts_enabled = bool(player and selected[0])
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
'''
new = '''        player_value = self.settings.get(CONF_TTS_MEDIA_PLAYER)
        player = str(player_value) if player_value else None
        base_selected = selected
        all_notify_records = resolve_notify_outputs(self.hass, base_selected[1])
        all_companion_records = resolve_companion_tts_outputs(
            self.hass, base_selected[3]
        )

        def routed_plan(
            area_ids: tuple[str, ...],
            *,
            filter_by_area: bool,
        ) -> tuple[
            tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]],
            tuple[NotifyOutput, ...],
            tuple[CompanionTTSOutput, ...],
            Any,
        ]:
            if filter_by_area:
                effective_areas = set(area_ids)
                routed_notify = tuple(
                    output
                    for output in all_notify_records
                    if output.area_id is not None
                    and output.area_id in effective_areas
                )
                routed_snapcast = tuple(
                    entity_id
                    for entity_id in base_selected[2]
                    if (
                        area_id := entity_area_id(self.hass, entity_id)
                    ) is not None
                    and area_id in effective_areas
                )
                routed_companion = tuple(
                    output
                    for output in all_companion_records
                    if output.area_id is not None
                    and output.area_id in effective_areas
                )
                routed_selected = (
                    base_selected[0],
                    tuple(output.ref for output in routed_notify),
                    routed_snapcast,
                    tuple(output.entry_id for output in routed_companion),
                )
            else:
                routed_notify = all_notify_records
                routed_companion = all_companion_records
                routed_selected = base_selected

            server_tts_enabled = bool(player and routed_selected[0])
            if filter_by_area and server_tts_enabled:
                if configured[2]:
                    server_tts_enabled = bool(routed_selected[2])
                else:
                    player_area = (
                        entity_area_id(self.hass, player) if player else None
                    )
                    server_tts_enabled = (
                        player_area is not None
                        and player_area in set(area_ids)
                    )

            route_plan = build_delivery_plan(
                text_tts=text_tts,
                text_notify=text_notify,
                level=level,
                minimum_tts_level=minimum_tts_level,
                tts_engines=routed_selected[0],
                notify_outputs=routed_selected[1],
                snapcast_clients=routed_selected[2],
                companion_tts_entries=routed_selected[3],
                server_tts_enabled=server_tts_enabled,
            )
            return (
                routed_selected,
                routed_notify,
                routed_companion,
                route_plan,
            )

        selected, notify_records, companion_records, plan = routed_plan(
            output_area_ids,
            filter_by_area=occupancy_filter_active,
        )

        if occupancy_filter_active and not plan.has_output:
            fallback_area_id = self._fallback_area_id()
            if (
                fallback_area_id
                and self._fallback_door_allows(output_area_ids)
            ):
                (
                    fallback_selected,
                    fallback_notify_records,
                    fallback_companion_records,
                    fallback_plan,
                ) = routed_plan((fallback_area_id,), filter_by_area=True)
                if fallback_plan.has_output:
                    output_area_ids = (fallback_area_id,)
                    selected = fallback_selected
                    notify_records = fallback_notify_records
                    companion_records = fallback_companion_records
                    plan = fallback_plan
                    _LOGGER.debug(
                        "Announcement routed to fallback area %s because the "
                        "occupied area(s) had no candidates",
                        fallback_area_id,
                    )

        notify_output_areas = {
            output.ref: output.area_id for output in notify_records
        }
        configured_profiles = self.settings.get(CONF_NOTIFY_PROFILES, {})
        if not isinstance(configured_profiles, Mapping):
            configured_profiles = {}
        notify_output_profiles = {
            output.ref: resolve_notify_profile(
                configured_profiles, output.integration
            )
            for output in notify_records
        }
        snapcast_client_areas = {
            entity_id: entity_area_id(self.hass, entity_id)
            for entity_id in selected[2]
        }
        companion_tts_entry_areas = {
            output.entry_id: output.area_id for output in companion_records
        }

        if not plan.has_output and not occupancy_filter_active:
'''
replace_once(path, old, new)

anchor = '    def _occupied_area_ids(self) -> tuple[str, ...] | None:\n'
text = path.read_text(encoding="utf-8")
if anchor not in text:
    raise SystemExit("manager.py: occupancy helper anchor missing")
helpers = '''    def _fallback_area_id(self) -> str | None:
        """Return the configured fallback room as an area ID."""
        value = str(self.settings.get(CONF_FALLBACK_ROOM, "") or "").strip()
        if not value:
            return None
        registry = ar.async_get(self.hass)
        if registry.async_get_area(value):
            return value
        if area := registry.async_get_area_by_name(value):
            return area.id
        _LOGGER.debug("Configured fallback room %s is not a known area", value)
        return None

    def _fallback_door_allows(self, occupied_area_ids: Sequence[str]) -> bool:
        """Allow fallback when door checking is disabled or an occupied door is open."""
        if not bool(
            self.settings.get(
                CONF_FALLBACK_CHECK_DOOR,
                DEFAULT_FALLBACK_CHECK_DOOR,
            )
        ):
            return True

        occupied = set(occupied_area_ids)
        if not occupied:
            return False

        found_door = False
        for state in self.hass.states.async_all("binary_sensor"):
            if state.attributes.get("device_class") != "door":
                continue
            if entity_area_id(self.hass, state.entity_id) not in occupied:
                continue
            found_door = True
            if state.state == STATE_ON:
                return True

        if not found_door:
            _LOGGER.debug(
                "Fallback blocked: no door binary sensor belongs to occupied area(s) %s",
                sorted(occupied),
            )
        else:
            _LOGGER.debug(
                "Fallback blocked: every occupied-area door is closed or unavailable"
            )
        return False

'''
path.write_text(text.replace(anchor, helpers + anchor, 1), encoding="utf-8")

# strings + translations
translations = {
    "strings.json": (
        "Fallback room",
        "Check occupied-room door before fallback",
        "Optional Home Assistant area used only when occupancy filtering leaves the announcement with zero candidates.",
        "When enabled, fallback is allowed only if at least one occupied target area has a binary_sensor with device_class door that is open. Closed, unknown, unavailable, or missing door sensors block fallback.",
    ),
    "translations/en.json": (
        "Fallback room",
        "Check occupied-room door before fallback",
        "Optional Home Assistant area used only when occupancy filtering leaves the announcement with zero candidates.",
        "When enabled, fallback is allowed only if at least one occupied target area has a binary_sensor with device_class door that is open. Closed, unknown, unavailable, or missing door sensors block fallback.",
    ),
    "translations/de.json": (
        "Fallback-Bereich",
        "Tür des belegten Bereichs vor Fallback prüfen",
        "Optionaler Home-Assistant-Bereich, der nur verwendet wird, wenn nach der Belegungsfilterung keine Kandidaten für die Ankündigung übrig bleiben.",
        "Wenn aktiviert, ist der Fallback nur erlaubt, wenn mindestens ein belegter Zielbereich einen binary_sensor mit device_class door hat, der offen ist. Geschlossene, unbekannte, nicht verfügbare oder fehlende Türsensoren blockieren den Fallback.",
    ),
    "translations/el.json": (
        "Περιοχή fallback",
        "Έλεγχος πόρτας κατειλημμένης περιοχής πριν το fallback",
        "Προαιρετική περιοχή Home Assistant που χρησιμοποιείται μόνο όταν το occupancy filtering αφήσει την ανακοίνωση με μηδέν candidates.",
        "Όταν είναι ενεργό, το fallback επιτρέπεται μόνο αν τουλάχιστον μία κατειλημμένη περιοχή-στόχος έχει binary_sensor με device_class door που είναι ανοιχτός. Κλειστή, unknown, unavailable ή ανύπαρκτη πόρτα μπλοκάρει το fallback.",
    ),
}
for relative, labels in translations.items():
    path = COMPONENT / relative
    data = json.loads(path.read_text(encoding="utf-8"))
    for section in ("config", "options"):
        outputs = data[section]["step"]["outputs"]
        outputs["data"]["fallback_room"] = labels[0]
        outputs["data"]["fallback_check_door"] = labels[1]
        outputs["data_description"]["fallback_room"] = labels[2]
        outputs["data_description"]["fallback_check_door"] = labels[3]
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

# manifest
path = COMPONENT / "manifest.json"
manifest = json.loads(path.read_text(encoding="utf-8"))
if manifest.get("version") != "0.4.0":
    raise SystemExit(f"Unexpected manifest version: {manifest.get('version')}")
manifest["version"] = "0.5.0"
path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

# tests
path = ROOT / "tests" / "test_resources.py"
replace_once(
    path,
    '        "occupancy_attribute",\n',
    '        "occupancy_attribute",\n        "fallback_room",\n        "fallback_check_door",\n',
)
replace_once(
    path,
    '    assert manifest["version"] == "0.4.0"\n',
    '    assert manifest["version"] == "0.5.0"\n',
)

path = ROOT / "tests" / "test_occupancy_filter.py"
text = path.read_text(encoding="utf-8")
text += '''


def test_fallback_requires_zero_candidates_and_optionally_open_door() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    config_flow = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    assert "if occupancy_filter_active and not plan.has_output:" in manager
    assert "def _fallback_area_id(" in manager
    assert "def _fallback_door_allows(" in manager
    assert 'self.hass.states.async_all("binary_sensor")' in manager
    assert 'state.attributes.get("device_class") != "door"' in manager
    assert "state.state == STATE_ON" in manager
    assert "CONF_FALLBACK_ROOM" in config_flow
    assert "CONF_FALLBACK_CHECK_DOOR" in config_flow


def test_fallback_does_not_regress_background_task_lifecycle() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(") == 2
'''
path.write_text(text, encoding="utf-8")

# changelog
path = ROOT / "CHANGELOG.md"
text = path.read_text(encoding="utf-8")
heading = "# Changelog\n\n"
if not text.startswith(heading):
    raise SystemExit("Unexpected changelog header")
entry = '''## 0.5.0 - 2026-10-02

- Added an optional fallback room for occupancy-aware routing.
- Fallback is considered only when the occupancy-filtered announcement has zero
  configured candidates; temporarily unavailable devices remain normal
  candidates and continue to use the availability timeout.
- Added an optional door gate, enabled by default. When enabled, fallback occurs
  only if at least one occupied target area has an open binary sensor with
  `device_class: door`.
- Closed, unavailable, unknown, or missing door sensors block fallback.
- Fallback uses only outputs assigned to the fallback room and preserves service
  restrictions, TTS level policy, Companion App TTS opt-in, and availability
  timeout behavior.
- No new long-lived tasks were introduced; the config-entry background-task
  lifecycle remains unchanged.

'''
path.write_text(heading + entry + text[len(heading):], encoding="utf-8")

# README
path = ROOT / "README.md"
text = path.read_text(encoding="utf-8")
anchor = "## Main action\n"
if anchor not in text:
    raise SystemExit("README anchor missing")
section = '''### Occupancy fallback room

Optionally configure a fallback Home Assistant area. The fallback is evaluated
only when occupancy-aware routing produces zero configured delivery candidates.
Offline candidates do not trigger fallback; they keep using the normal
availability timeout.

When **Check occupied-room door before fallback** is enabled, at least one
occupied target room must contain a `binary_sensor` with
`device_class: door` whose state is `on` (open). Closed (`off`), unknown,
unavailable, or missing door sensors block fallback. Disable the checkbox to
allow zero-candidate fallback regardless of door state.

The fallback room is routed exactly like any other area: only the configured
outputs actually assigned to that area are used, so a fallback room with only
TTS receives TTS and one with only visual notification outputs receives only
those notifications.

'''
path.write_text(text.replace(anchor, section + anchor, 1), encoding="utf-8")

print("Applied Announcement Hub 0.5.0 fallback-room routing")
