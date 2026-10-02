from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(".")
C = ROOT / "custom_components" / "announcement_hub"


def rep(path: Path, old: str, new: str, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    found = text.count(old)
    if found != count:
        raise SystemExit(f"{path}: expected {count} matches, found {found}: {old[:120]!r}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def replace_between(path: Path, start: str, end: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    i = text.index(start)
    j = text.index(end, i)
    path.write_text(text[:i] + new + text[j:], encoding="utf-8")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
p = C / "const.py"
rep(p, 'VERSION: Final = "0.7.0"', 'VERSION: Final = "0.8.0"')
rep(
    p,
    'CONF_NOTIFY_POLICIES: Final = "notify_policies"\n',
    'CONF_NOTIFY_POLICIES: Final = "notify_policies"\n'
    'CONF_NOTIFY_ROOM_OUTPUTS: Final = "notify_room_outputs"\n'
    'CONF_NOTIFY_INFO_OUTPUTS: Final = "notify_info_outputs"\n'
    'CONF_NOTIFY_WARNING_OUTPUTS: Final = "notify_warning_outputs"\n'
    'CONF_NOTIFY_ERROR_OUTPUTS: Final = "notify_error_outputs"\n'
    'CONF_NOTIFY_CRITICAL_OUTPUTS: Final = "notify_critical_outputs"\n',
)
rep(
    p,
    'CONF_TTS_ROOM_PLAYERS: Final = "tts_room_players"\n',
    'CONF_TTS_ROOM_PLAYERS: Final = "tts_room_players"\n'
    'CONF_TTS_AREA_PLAYERS: Final = "tts_area_players"\n'
    'CONF_TTS_PLAYER_POLICIES: Final = "tts_player_policies"\n',
)
rep(
    p,
    'CONF_FALLBACK_CHECK_DOOR: Final = "fallback_check_door"\n',
    'CONF_FALLBACK_CHECK_DOOR: Final = "fallback_check_door"\n'
    'CONF_FALLBACK_DOOR_LABEL: Final = "fallback_door_label"\n',
)

# ---------------------------------------------------------------------------
# Discovery helpers: concrete entities, device labels, languages, defaults
# ---------------------------------------------------------------------------
p = C / "outputs.py"
rep(
    p,
    "from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN\n",
    "from homeassistant.components import tts\n"
    "from homeassistant.components.media_player import MediaPlayerEntityFeature\n"
    "from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN\n",
)

anchor = "def entity_name(hass: HomeAssistant, entity_id: str) -> str:\n"
text = p.read_text(encoding="utf-8")
i = text.index(anchor)
helper = '''def entity_device_name(hass: HomeAssistant, entity_id: str) -> str:
    """Return the device/config-entry name behind an entity."""
    reg_entry = er.async_get(hass).async_get(entity_id)
    if reg_entry is None:
        return "No device"
    if device_id := getattr(reg_entry, "device_id", None):
        if device := dr.async_get(hass).async_get(device_id):
            return str(
                getattr(device, "name_by_user", None)
                or getattr(device, "name", None)
                or entity_id
            )
    if entry := _entry(hass, _entity_config_entry_id(reg_entry)):
        return str(entry.title)
    return "No device"


def concrete_entity_options(
    hass: HomeAssistant,
    *,
    entity_domain: str,
    integration: str | None = None,
) -> list[SelectOption]:
    """Return only concrete supported entities with integration/device/entity labels."""
    options: list[SelectOption] = []
    for item in _enabled_registry_entries(
        hass, entity_domain=entity_domain, integration=integration
    ):
        entity_id = item.entity_id
        owner = _integration_for_registry_entry(hass, item) or "unknown"
        options.append(
            SelectOption(
                f"{TARGET_ENTITY_PREFIX}{entity_id}",
                f"{owner.replace('_', ' ').title()} · "
                f"{entity_device_name(hass, entity_id)} · "
                f"{entity_name(hass, entity_id)}",
            )
        )
    return sorted(options, key=lambda item: item.label.casefold())


def tts_default_engine(hass: HomeAssistant) -> str | None:
    """Return Home Assistant's preferred/default concrete TTS entity."""
    try:
        engine = tts.async_default_engine(hass)
    except (KeyError, AttributeError):
        return None
    return str(engine) if engine and str(engine).startswith("tts.") else None


def tts_media_player_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return non-Snapcast media players capable of direct play-media TTS."""
    result: list[SelectOption] = []
    for item in _enabled_registry_entries(hass, entity_domain="media_player"):
        if _integration_for_registry_entry(hass, item) == "snapcast":
            continue
        state = hass.states.get(item.entity_id)
        if state is None:
            continue
        features = int(state.attributes.get("supported_features", 0) or 0)
        if not features & int(MediaPlayerEntityFeature.PLAY_MEDIA):
            continue
        owner = _integration_for_registry_entry(hass, item) or "unknown"
        result.append(
            SelectOption(
                item.entity_id,
                f"{owner.replace('_', ' ').title()} · "
                f"{entity_device_name(hass, item.entity_id)} · "
                f"{entity_name(hass, item.entity_id)} · "
                f"{area_name(hass, entity_area_id(hass, item.entity_id))}",
            )
        )
    return [item.as_dict() for item in sorted(result, key=lambda x: x.label.casefold())]


'''
p.write_text(text[:i] + helper + text[i:], encoding="utf-8")

replace_between(
    p,
    "def notify_output_options(hass: HomeAssistant) -> list[dict[str, str]]:\n",
    "\ndef snapcast_output_options",
    '''def notify_output_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return concrete recognised notification entities only."""
    return [
        option.as_dict()
        for option in concrete_entity_options(hass, entity_domain="notify")
    ]


''',
)

replace_between(
    p,
    "def snapcast_output_options(hass: HomeAssistant) -> list[dict[str, str]]:\n",
    "\ndef companion_tts_output_options",
    '''def snapcast_output_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return concrete Snapcast client entities only."""
    return [
        option.as_dict()
        for option in concrete_entity_options(
            hass,
            entity_domain="media_player",
            integration="snapcast",
        )
        if "group" not in option["value"].casefold()
    ]


''',
)

replace_between(
    p,
    "def tts_engine_options(hass: HomeAssistant) -> list[dict[str, str]]:\n",
    "\ndef _expand_entity_tokens",
    '''def tts_engine_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return concrete TTS engines with their advertised languages."""
    component = hass.data.get(getattr(tts, "DATA_COMPONENT", "tts_entity_component"))
    options: list[SelectOption] = []
    for item in _enabled_registry_entries(hass, entity_domain="tts"):
        entity_id = item.entity_id
        owner = _integration_for_registry_entry(hass, item) or "unknown"
        languages: list[str] = []
        default_language: str | None = None
        entity = component.get_entity(entity_id) if component is not None else None
        if entity is not None:
            with suppress(Exception):
                languages = list(entity.supported_languages or [])
            with suppress(Exception):
                default_language = str(entity.default_language or "") or None
        language_label = ""
        if languages:
            shown = [
                f"{lang}*" if lang == default_language else str(lang)
                for lang in languages
            ]
            language_label = " · " + ", ".join(shown)
        options.append(
            SelectOption(
                entity_id,
                f"{owner.replace('_', ' ').title()} · "
                f"{entity_name(hass, entity_id)}{language_label}",
            )
        )
    return [item.as_dict() for item in sorted(options, key=lambda x: x.label.casefold())]


''',
)
# outputs.py needs suppress
rep(p, "from dataclasses import dataclass\n", "from contextlib import suppress\nfrom dataclasses import dataclass\n")

# ---------------------------------------------------------------------------
# Config flow imports
# ---------------------------------------------------------------------------
p = C / "config_flow.py"
for old, new in [
    (
        "    CONF_NOTIFY_OUTPUTS,\n    CONF_NOTIFY_POLICIES,\n",
        "    CONF_NOTIFY_OUTPUTS,\n"
        "    CONF_NOTIFY_POLICIES,\n"
        "    CONF_NOTIFY_ROOM_OUTPUTS,\n"
        "    CONF_NOTIFY_INFO_OUTPUTS,\n"
        "    CONF_NOTIFY_WARNING_OUTPUTS,\n"
        "    CONF_NOTIFY_ERROR_OUTPUTS,\n"
        "    CONF_NOTIFY_CRITICAL_OUTPUTS,\n",
    ),
    (
        "    CONF_FALLBACK_CHECK_DOOR,\n    CONF_FALLBACK_ROOM,\n",
        "    CONF_FALLBACK_CHECK_DOOR,\n"
        "    CONF_FALLBACK_DOOR_LABEL,\n"
        "    CONF_FALLBACK_ROOM,\n",
    ),
    (
        "    CONF_TTS_MEDIA_PLAYER,\n    CONF_TTS_ROOM_PLAYERS,\n",
        "    CONF_TTS_MEDIA_PLAYER,\n"
        "    CONF_TTS_ROOM_PLAYERS,\n"
        "    CONF_TTS_AREA_PLAYERS,\n"
        "    CONF_TTS_PLAYER_POLICIES,\n",
    ),
]:
    rep(p, old, new)

rep(
    p,
    "    snapcast_output_options,\n    tts_engine_options,\n",
    "    snapcast_output_options,\n"
    "    tts_default_engine,\n"
    "    tts_engine_options,\n"
    "    tts_media_player_options,\n",
)

# strict recognised-only multiselect
anchor = "class _AnnouncementFlowMixin:\n"
text = p.read_text(encoding="utf-8")
known_select = '''def _known_multi_select(
    options: list[dict[str, str]],
) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            multiple=True,
            custom_value=False,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


'''
p.write_text(text.replace(anchor, known_select + anchor, 1), encoding="utf-8")

# ---------------------------------------------------------------------------
# Step 1: Notifications — all discovery + room/movable + minimum level
# ---------------------------------------------------------------------------
replace_between(
    p,
    "    async def async_step_outputs(\n",
    "\n\n    def _prepare_notify_routing_steps",
    '''    async def async_step_outputs(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: discover and configure notification outputs."""
        options = notify_output_options(self.hass)
        known = [str(item["value"]) for item in options]
        initial = CONF_NOTIFY_OUTPUTS not in self._working
        selected_default = (
            known
            if initial
            else [value for value in self._value(CONF_NOTIFY_OUTPUTS, []) if value in known]
        )

        records = {
            output.ref: output
            for output in resolve_notify_outputs(self.hass, known)
        }
        policies = self._working.get(CONF_NOTIFY_POLICIES, {})
        if not isinstance(policies, dict):
            policies = {}

        room_default: list[str] = []
        levels: dict[str, list[str]] = {
            "info": [], "warning": [], "error": [], "critical": []
        }
        for ref in selected_default:
            output = records.get(ref)
            policy = policies.get(ref, {})
            if not isinstance(policy, dict):
                policy = {}
            scope = str(
                policy.get(
                    NOTIFY_POLICY_SCOPE,
                    NOTIFY_SCOPE_ROOM if output and output.area_id else NOTIFY_SCOPE_GENERAL,
                )
            )
            if scope == NOTIFY_SCOPE_ROOM:
                room_default.append(ref)
            minimum = str(
                policy.get(NOTIFY_POLICY_MIN_LEVEL, DEFAULT_NOTIFY_MIN_LEVEL)
            )
            if minimum in levels:
                levels[minimum].append(ref)

        errors: dict[str, str] = {}
        if user_input is not None:
            selected = [
                value for value in user_input.get(CONF_NOTIFY_OUTPUTS, [])
                if value in known
            ]
            selected_set = set(selected)
            room = set(user_input.get(CONF_NOTIFY_ROOM_OUTPUTS, [])) & selected_set
            level_sets = {
                "info": set(user_input.get(CONF_NOTIFY_INFO_OUTPUTS, [])) & selected_set,
                "warning": set(user_input.get(CONF_NOTIFY_WARNING_OUTPUTS, [])) & selected_set,
                "error": set(user_input.get(CONF_NOTIFY_ERROR_OUTPUTS, [])) & selected_set,
                "critical": set(user_input.get(CONF_NOTIFY_CRITICAL_OUTPUTS, [])) & selected_set,
            }
            assigned: set[str] = set()
            duplicate = False
            for values in level_sets.values():
                if assigned & values:
                    duplicate = True
                assigned |= values
            no_area = [
                ref for ref in room
                if (records.get(ref) is None or records[ref].area_id is None)
            ]
            if duplicate:
                errors["base"] = "notify_level_overlap"
            elif no_area:
                errors["base"] = "room_notify_area_required"
            else:
                new_policies: dict[str, dict[str, str]] = {}
                for ref in selected:
                    minimum = DEFAULT_NOTIFY_MIN_LEVEL
                    for candidate in ("info", "warning", "error", "critical"):
                        if ref in level_sets[candidate]:
                            minimum = candidate
                            break
                    new_policies[ref] = {
                        NOTIFY_POLICY_SCOPE: (
                            NOTIFY_SCOPE_ROOM if ref in room else NOTIFY_SCOPE_GENERAL
                        ),
                        NOTIFY_POLICY_MIN_LEVEL: minimum,
                    }
                self._working[CONF_NOTIFY_OUTPUTS] = selected
                self._working[CONF_NOTIFY_POLICIES] = new_policies
                return await self.async_step_tts()

        schema = probatio.Schema(
            {
                probatio.Optional(
                    CONF_NOTIFY_OUTPUTS,
                    default=selected_default,
                ): _known_multi_select(options),
                probatio.Optional(
                    CONF_NOTIFY_ROOM_OUTPUTS,
                    default=room_default,
                ): _known_multi_select(options),
                probatio.Optional(
                    CONF_NOTIFY_INFO_OUTPUTS,
                    default=levels["info"],
                ): _known_multi_select(options),
                probatio.Optional(
                    CONF_NOTIFY_WARNING_OUTPUTS,
                    default=levels["warning"],
                ): _known_multi_select(options),
                probatio.Optional(
                    CONF_NOTIFY_ERROR_OUTPUTS,
                    default=levels["error"],
                ): _known_multi_select(options),
                probatio.Optional(
                    CONF_NOTIFY_CRITICAL_OUTPUTS,
                    default=levels["critical"],
                ): _known_multi_select(options),
            }
        )
        return self.async_show_form(
            step_id="outputs",
            data_schema=schema,
            errors=errors,
        )
''',
)

# ---------------------------------------------------------------------------
# Step 2: TTS outputs
# ---------------------------------------------------------------------------
replace_between(
    p,
    "    async def async_step_tts(\n",
    "\n    async def async_step_snapcast",
    '''    async def async_step_tts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: configure TTS engines and physical output roles."""
        errors: dict[str, str] = {}
        engine_options = tts_engine_options(self.hass)
        engine_ids = [str(item["value"]) for item in engine_options]
        if CONF_TTS_ENGINES in self._working:
            engine_default = [
                value for value in self._value(CONF_TTS_ENGINES, []) if value in engine_ids
            ]
        else:
            default_engine = tts_default_engine(self.hass)
            engine_default = [default_engine] if default_engine in engine_ids else []

        direct_options = tts_media_player_options(self.hass)
        direct_ids = [str(item["value"]) for item in direct_options]
        direct_default = [
            value for value in self._value(CONF_TTS_ROOM_PLAYERS, [])
            if value in direct_ids
        ]
        policies = self._working.get(CONF_TTS_PLAYER_POLICIES, {})
        if not isinstance(policies, dict):
            policies = {}
        area_default = []
        for entity_id in direct_default:
            policy = policies.get(entity_id, {})
            scope = (
                str(policy.get(NOTIFY_POLICY_SCOPE))
                if isinstance(policy, dict) and policy.get(NOTIFY_POLICY_SCOPE)
                else (
                    NOTIFY_SCOPE_ROOM
                    if entity_area_id(self.hass, entity_id)
                    else NOTIFY_SCOPE_GENERAL
                )
            )
            if scope == NOTIFY_SCOPE_ROOM:
                area_default.append(entity_id)

        snap_options = snapcast_output_options(self.hass)
        snap_ids = [
            str(item["value"]).removeprefix("entity:")
            for item in snap_options
        ]
        snap_default = [
            value for value in expand_snapcast_output_tokens(
                self.hass, self._value(CONF_SNAPCAST_OUTPUTS, [])
            )
            if value in snap_ids
        ]

        if user_input is not None:
            engines = [v for v in user_input.get(CONF_TTS_ENGINES, []) if v in engine_ids]
            direct = [v for v in user_input.get(CONF_TTS_ROOM_PLAYERS, []) if v in direct_ids]
            area_players = set(user_input.get(CONF_TTS_AREA_PLAYERS, [])) & set(direct)
            snapcast_refs = list(user_input.get(CONF_SNAPCAST_OUTPUTS, []))
            snapcast = list(expand_snapcast_output_tokens(self.hass, snapcast_refs))
            shared_player = user_input.get(CONF_TTS_MEDIA_PLAYER)
            if (direct or snapcast) and not engines:
                errors["base"] = "tts_engine_required"
            elif snapcast and not shared_player:
                errors["base"] = "snapcast_tts_path_required"
            else:
                no_area = [
                    entity_id for entity_id in area_players
                    if entity_area_id(self.hass, entity_id) is None
                ]
                if no_area:
                    errors["base"] = "room_tts_area_required"
                else:
                    self._working[CONF_TTS_ENGINES] = engines
                    self._working[CONF_TTS_ROOM_PLAYERS] = direct
                    self._working[CONF_TTS_PLAYER_POLICIES] = {
                        entity_id: {
                            NOTIFY_POLICY_SCOPE: (
                                NOTIFY_SCOPE_ROOM
                                if entity_id in area_players
                                else NOTIFY_SCOPE_GENERAL
                            )
                        }
                        for entity_id in direct
                    }
                    self._working[CONF_SNAPCAST_OUTPUTS] = snapcast_refs
                    self._working[CONF_TTS_MEDIA_PLAYER] = shared_player
                    for key in (
                        CONF_TTS_MIN_LEVEL,
                        CONF_TTS_CACHE,
                        CONF_TTS_LANGUAGE,
                        CONF_TTS_OPTIONS,
                        CONF_COMPANION_TTS_OUTPUTS,
                        CONF_COMPANION_TTS_MEDIA_STREAM,
                        CONF_COMPANION_TTS_WPM,
                    ):
                        if key in user_input:
                            self._working[key] = user_input[key]
                    self._prepare_notify_profile_steps()
                    if snapcast:
                        self._notify_profile_domains.append("snapcast")
                    return await self.async_step_notification_profile()

        fields: dict[probatio.Marker, Any] = {
            probatio.Optional(
                CONF_TTS_ENGINES,
                default=engine_default,
            ): _known_multi_select(engine_options),
            probatio.Optional(
                CONF_TTS_ROOM_PLAYERS,
                default=direct_default,
            ): _known_multi_select(direct_options),
            probatio.Optional(
                CONF_TTS_AREA_PLAYERS,
                default=area_default,
            ): _known_multi_select(direct_options),
        }

        if snap_options:
            fields[
                probatio.Optional(
                    CONF_SNAPCAST_OUTPUTS,
                    default=[
                        f"entity:{entity_id}" for entity_id in snap_default
                    ],
                )
            ] = _known_multi_select(snap_options)
            fields[
                _optional_marker(
                    CONF_TTS_MEDIA_PLAYER,
                    self._value(CONF_TTS_MEDIA_PLAYER, None),
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="media_player")
            )

        fields.update(
            {
                probatio.Required(
                    CONF_TTS_MIN_LEVEL,
                    default=self._value(CONF_TTS_MIN_LEVEL, DEFAULT_TTS_MIN_LEVEL),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(TTS_MIN_LEVELS),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="tts_min_level",
                    )
                ),
                probatio.Required(
                    CONF_TTS_CACHE,
                    default=self._value(CONF_TTS_CACHE, DEFAULT_TTS_CACHE),
                ): selector.BooleanSelector(),
                _optional_marker(
                    CONF_TTS_LANGUAGE,
                    self._value(CONF_TTS_LANGUAGE, DEFAULT_TTS_LANGUAGE),
                ): selector.TextSelector(),
                probatio.Optional(
                    CONF_TTS_OPTIONS,
                    default=self._value(CONF_TTS_OPTIONS, DEFAULT_TTS_OPTIONS),
                ): selector.ObjectSelector(),
                probatio.Optional(
                    CONF_COMPANION_TTS_OUTPUTS,
                    default=self._value(CONF_COMPANION_TTS_OUTPUTS, []),
                ): _multi_select(companion_tts_output_options(self.hass)),
                probatio.Required(
                    CONF_COMPANION_TTS_MEDIA_STREAM,
                    default=self._value(
                        CONF_COMPANION_TTS_MEDIA_STREAM,
                        DEFAULT_COMPANION_TTS_MEDIA_STREAM,
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(COMPANION_STREAMS),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="companion_tts_media_stream",
                    )
                ),
                probatio.Required(
                    CONF_COMPANION_TTS_WPM,
                    default=self._value(
                        CONF_COMPANION_TTS_WPM,
                        DEFAULT_COMPANION_TTS_WPM,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60,
                        max=300,
                        step=5,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="wpm",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="tts", data_schema=probatio.Schema(fields), errors=errors)
''',
)

# Need entity_area_id/expand_snapcast in config flow imports.
rep(
    p,
    "    companion_tts_output_options,\n    expand_notify_output_tokens,\n",
    "    companion_tts_output_options,\n"
    "    entity_area_id,\n"
    "    expand_notify_output_tokens,\n"
    "    expand_snapcast_output_tokens,\n",
)

# ---------------------------------------------------------------------------
# Step 3: integration options. Existing notification profile loop + Snapcast.
# ---------------------------------------------------------------------------
# completion route
rep(
    p,
    "        if self._notify_profile_index >= len(self._notify_profile_domains):\n            return await self.async_step_tts()\n",
    "        if self._notify_profile_index >= len(self._notify_profile_domains):\n            return await self.async_step_queue()\n",
)

# Inject Snapcast branch after current profile/error declarations.
needle = '''        current = resolve_notify_profile(profiles, integration)
        errors: dict[str, str] = {}

        if user_input is not None:
'''
replacement = '''        current = resolve_notify_profile(profiles, integration)
        errors: dict[str, str] = {}

        if integration == "snapcast":
            if user_input is not None:
                self._store_step(
                    user_input,
                    {
                        CONF_SNAPCAST_SOURCE: DEFAULT_SNAPCAST_SOURCE,
                        CONF_SNAPCAST_ONLY_SOURCE: DEFAULT_SNAPCAST_ONLY_SOURCE,
                        CONF_SNAPCAST_SETTLE_DELAY: DEFAULT_SNAPCAST_SETTLE_DELAY,
                        CONF_SNAPCAST_VERIFY_TIMEOUT: DEFAULT_SNAPCAST_VERIFY_TIMEOUT,
                        CONF_SNAPCAST_RESTORE: DEFAULT_SNAPCAST_RESTORE,
                    },
                )
                self._notify_profile_index += 1
                return await self.async_step_notification_profile()
            return self.async_show_form(
                step_id="notification_profile",
                data_schema=probatio.Schema(
                    {
                        probatio.Required(
                            CONF_SNAPCAST_SOURCE,
                            default=self._value(CONF_SNAPCAST_SOURCE, DEFAULT_SNAPCAST_SOURCE),
                        ): selector.TextSelector(),
                        probatio.Required(
                            CONF_SNAPCAST_ONLY_SOURCE,
                            default=self._value(CONF_SNAPCAST_ONLY_SOURCE, DEFAULT_SNAPCAST_ONLY_SOURCE),
                        ): selector.BooleanSelector(),
                        probatio.Required(
                            CONF_SNAPCAST_SETTLE_DELAY,
                            default=self._value(CONF_SNAPCAST_SETTLE_DELAY, DEFAULT_SNAPCAST_SETTLE_DELAY),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(min=0, max=10, step=0.05, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
                        ),
                        probatio.Required(
                            CONF_SNAPCAST_VERIFY_TIMEOUT,
                            default=self._value(CONF_SNAPCAST_VERIFY_TIMEOUT, DEFAULT_SNAPCAST_VERIFY_TIMEOUT),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(min=0.5, max=30, step=0.5, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
                        ),
                        probatio.Required(
                            CONF_SNAPCAST_RESTORE,
                            default=self._value(CONF_SNAPCAST_RESTORE, DEFAULT_SNAPCAST_RESTORE),
                        ): selector.BooleanSelector(),
                    }
                ),
                description_placeholders={"integration": "Snapcast"},
            )

        if user_input is not None:
'''
rep(p, needle, replacement)

# ---------------------------------------------------------------------------
# Step 4: general options — queue + occupancy + fallback + label.
# ---------------------------------------------------------------------------
replace_between(
    p,
    "    async def async_step_queue(\n",
    "\n\nclass AnnouncementHubConfigFlow",
    '''    async def async_step_queue(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 4: general routing, presence, fallback, and queue options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            incoming_sensor = user_input.get(CONF_OCCUPANCY_SENSOR)
            had_source_field = CONF_OCCUPANCY_ATTRIBUTE in user_input
            for key, default in (
                (CONF_DEFAULT_TITLE, DEFAULT_TITLE),
                (CONF_CRITICAL_NOTIFY_DATA, {}),
                (CONF_OCCUPANCY_SENSOR, None),
                (CONF_FALLBACK_ROOM, None),
                (CONF_FALLBACK_CHECK_DOOR, DEFAULT_FALLBACK_CHECK_DOOR),
                (CONF_FALLBACK_DOOR_LABEL, None),
                (CONF_DISPATCH_ORDER, DEFAULT_DISPATCH_ORDER),
                (CONF_QUEUE_MAX, DEFAULT_QUEUE_MAX),
                (CONF_OUTPUT_AVAILABILITY_TIMEOUT, DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT),
                (CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT),
                (CONF_START_TIMEOUT, DEFAULT_START_TIMEOUT),
                (CONF_PLAYBACK_TIMEOUT, DEFAULT_PLAYBACK_TIMEOUT),
                (CONF_POST_PLAY_DELAY, DEFAULT_POST_PLAY_DELAY),
            ):
                self._working[key] = user_input.get(key, default)

            if incoming_sensor:
                if not had_source_field:
                    return await self.async_step_queue()
                source = str(user_input.get(CONF_OCCUPANCY_ATTRIBUTE, "__state__"))
                self._working[CONF_OCCUPANCY_ATTRIBUTE] = (
                    "" if source == "__state__" else source
                )
            else:
                self._working[CONF_OCCUPANCY_ATTRIBUTE] = ""

            has_tts = bool(
                self._working.get(CONF_TTS_ENGINES)
                and (
                    self._working.get(CONF_TTS_ROOM_PLAYERS)
                    or (
                        self._working.get(CONF_TTS_MEDIA_PLAYER)
                        and self._working.get(CONF_SNAPCAST_OUTPUTS)
                    )
                )
            )
            if not (
                self._working.get(CONF_NOTIFY_OUTPUTS)
                or self._working.get(CONF_COMPANION_TTS_OUTPUTS)
                or has_tts
            ):
                errors["base"] = "output_required"
            else:
                return await self._async_finish()

        sensor = str(self._value(CONF_OCCUPANCY_SENSOR, "") or "").strip()
        fields: dict[probatio.Marker, Any] = {
            probatio.Required(
                CONF_DEFAULT_TITLE,
                default=self._value(CONF_DEFAULT_TITLE, DEFAULT_TITLE),
            ): selector.TextSelector(),
            probatio.Optional(
                CONF_CRITICAL_NOTIFY_DATA,
                default=self._value(CONF_CRITICAL_NOTIFY_DATA, {}),
            ): selector.ObjectSelector(),
            _optional_marker(
                CONF_OCCUPANCY_SENSOR,
                self._value(CONF_OCCUPANCY_SENSOR, None),
            ): selector.EntitySelector(),
        }

        if sensor:
            state = self.hass.states.get(sensor)
            attributes = sorted(str(key) for key in (state.attributes if state else {}))
            options = [
                selector.SelectOptionDict(value="__state__", label="State"),
                *[
                    selector.SelectOptionDict(value=key, label=key)
                    for key in attributes
                ],
            ]
            current = str(self._value(CONF_OCCUPANCY_ATTRIBUTE, "") or "")
            values = {item["value"] for item in options}
            fields[
                probatio.Required(
                    CONF_OCCUPANCY_ATTRIBUTE,
                    default=current if current in values else "__state__",
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        fields.update(
            {
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
                _optional_marker(
                    CONF_FALLBACK_DOOR_LABEL,
                    self._value(CONF_FALLBACK_DOOR_LABEL, None),
                ): selector.LabelSelector(),
                probatio.Required(
                    CONF_DISPATCH_ORDER,
                    default=self._value(CONF_DISPATCH_ORDER, DEFAULT_DISPATCH_ORDER),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(DISPATCH_ORDERS),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="dispatch_order",
                    )
                ),
                probatio.Required(
                    CONF_QUEUE_MAX,
                    default=self._value(CONF_QUEUE_MAX, DEFAULT_QUEUE_MAX),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=1000, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
                probatio.Required(
                    CONF_OUTPUT_AVAILABILITY_TIMEOUT,
                    default=self._value(CONF_OUTPUT_AVAILABILITY_TIMEOUT, DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=300, step=0.5, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
                ),
                probatio.Required(
                    CONF_IDLE_TIMEOUT,
                    default=self._value(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=1800, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
                ),
                probatio.Required(
                    CONF_START_TIMEOUT,
                    default=self._value(CONF_START_TIMEOUT, DEFAULT_START_TIMEOUT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=120, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
                ),
                probatio.Required(
                    CONF_PLAYBACK_TIMEOUT,
                    default=self._value(CONF_PLAYBACK_TIMEOUT, DEFAULT_PLAYBACK_TIMEOUT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=3600, step=5, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
                ),
                probatio.Required(
                    CONF_POST_PLAY_DELAY,
                    default=self._value(CONF_POST_PLAY_DELAY, DEFAULT_POST_PLAY_DELAY),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=10, step=0.05, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
                ),
            }
        )
        return self.async_show_form(
            step_id="queue",
            data_schema=probatio.Schema(fields),
            errors=errors,
        )


''',
)

# ---------------------------------------------------------------------------
# Runtime: direct TTS room/general policy + optional door label
# ---------------------------------------------------------------------------
p = C / "manager.py"
for old, new in [
    (
        "    CONF_FALLBACK_CHECK_DOOR,\n    CONF_FALLBACK_ROOM,\n",
        "    CONF_FALLBACK_CHECK_DOOR,\n"
        "    CONF_FALLBACK_DOOR_LABEL,\n"
        "    CONF_FALLBACK_ROOM,\n",
    ),
    (
        "    CONF_TTS_MEDIA_PLAYER,\n    CONF_TTS_ROOM_PLAYERS,\n",
        "    CONF_TTS_MEDIA_PLAYER,\n"
        "    CONF_TTS_ROOM_PLAYERS,\n"
        "    CONF_TTS_PLAYER_POLICIES,\n",
    ),
]:
    rep(p, old, new)

rep(
    p,
    "from homeassistant.helpers import area_registry as ar\n",
    "from homeassistant.helpers import area_registry as ar\n"
    "from homeassistant.helpers import entity_registry as er\n",
)

# TTS policy helper before enqueue
anchor = "    def _notify_policy(\n"
text = p.read_text(encoding="utf-8")
i = text.index(anchor)
tts_policy = '''    def _tts_player_scope(self, entity_id: str) -> str:
        """Return room/general scope for one direct TTS media player."""
        configured = self.settings.get(CONF_TTS_PLAYER_POLICIES, {})
        if isinstance(configured, Mapping):
            policy = configured.get(entity_id, {})
            if isinstance(policy, Mapping):
                scope = str(policy.get(NOTIFY_POLICY_SCOPE, ""))
                if scope in {NOTIFY_SCOPE_ROOM, NOTIFY_SCOPE_GENERAL}:
                    return scope
        return (
            NOTIFY_SCOPE_ROOM
            if entity_area_id(self.hass, entity_id)
            else NOTIFY_SCOPE_GENERAL
        )


'''
p.write_text(text[:i] + tts_policy + text[i:], encoding="utf-8")

rep(
    p,
    '''                routed_room_tts = tuple(
                    entity_id
                    for entity_id in all_room_tts_players
                    if (
                        area_id := entity_area_id(self.hass, entity_id)
                    ) is not None
                    and area_id in effective_areas
                )
''',
    '''                routed_room_tts = tuple(
                    entity_id
                    for entity_id in all_room_tts_players
                    if (
                        self._tts_player_scope(entity_id) == NOTIFY_SCOPE_GENERAL
                        or (
                            (area_id := entity_area_id(self.hass, entity_id))
                            is not None
                            and area_id in effective_areas
                        )
                    )
                )
''',
)

rep(
    p,
    '''        room_tts_player_areas = {
            entity_id: entity_area_id(self.hass, entity_id)
            for entity_id in selected[2]
        }
''',
    '''        room_tts_player_areas = {
            entity_id: (
                None
                if self._tts_player_scope(entity_id) == NOTIFY_SCOPE_GENERAL
                else entity_area_id(self.hass, entity_id)
            )
            for entity_id in selected[2]
        }
''',
)

# None area means General, so it bypasses job area checks.
rep(
    p,
    '''            if job.outputs and area_id not in set(job.outputs):
                continue
''',
    '''            if (
                job.outputs
                and area_id is not None
                and area_id not in set(job.outputs)
            ):
                continue
''',
    count=1,
)
rep(
    p,
    '''            if not job.outputs
            or job.room_tts_player_areas.get(
                player, entity_area_id(self.hass, player)
            )
            in set(job.outputs)
''',
    '''            if (
                not job.outputs
                or job.room_tts_player_areas.get(
                    player, entity_area_id(self.hass, player)
                )
                is None
                or job.room_tts_player_areas.get(
                    player, entity_area_id(self.hass, player)
                )
                in set(job.outputs)
            )
''',
)

# Door label filter.
needle = '''        found_door = False
        for state in self.hass.states.async_all("binary_sensor"):
            if state.attributes.get("device_class") != "door":
                continue
'''
replacement = '''        found_door = False
        required_label = str(
            self.settings.get(CONF_FALLBACK_DOOR_LABEL, "") or ""
        ).strip()
        entity_registry = er.async_get(self.hass)
        for state in self.hass.states.async_all("binary_sensor"):
            if state.attributes.get("device_class") != "door":
                continue
            if required_label:
                reg_entry = entity_registry.async_get(state.entity_id)
                if (
                    reg_entry is None
                    or required_label not in getattr(reg_entry, "labels", set())
                ):
                    continue
'''
rep(p, needle, replacement)

# ---------------------------------------------------------------------------
# Migration defaults
# ---------------------------------------------------------------------------
p = C / "__init__.py"
rep(
    p,
    "    CONF_NOTIFY_POLICIES,\n    CONF_NOTIFY_PROFILES,\n",
    "    CONF_NOTIFY_POLICIES,\n"
    "    CONF_NOTIFY_PROFILES,\n"
    "    CONF_TTS_PLAYER_POLICIES,\n",
)
rep(
    p,
    "    migrated.setdefault(CONF_TTS_ROOM_PLAYERS, [])\n"
    "    migrated.setdefault(CONF_NOTIFY_POLICIES, {})\n"
    "    migrated.setdefault(CONF_NOTIFY_PROFILES, {})\n",
    "    migrated.setdefault(CONF_TTS_ROOM_PLAYERS, [])\n"
    "    migrated.setdefault(CONF_NOTIFY_POLICIES, {})\n"
    "    migrated.setdefault(CONF_NOTIFY_PROFILES, {})\n"
    "    migrated.setdefault(CONF_TTS_PLAYER_POLICIES, {})\n",
)
rep(
    p,
    "        migrated.setdefault(CONF_NOTIFY_POLICIES, {})\n"
    "        migrated.setdefault(CONF_NOTIFY_PROFILES, {})\n",
    "        migrated.setdefault(CONF_NOTIFY_POLICIES, {})\n"
    "        migrated.setdefault(CONF_NOTIFY_PROFILES, {})\n"
    "        migrated.setdefault(CONF_TTS_PLAYER_POLICIES, {})\n",
)

# ---------------------------------------------------------------------------
# Resources: expose exactly four conceptual setup steps
# ---------------------------------------------------------------------------
locales = {
    "strings.json": {
        "s1_title": "1. Notification outputs",
        "s1_desc": "All recognised notification entities are selected automatically. Deselect devices you do not want, mark room-bound devices, and assign higher minimum levels where needed. Selected devices not listed in a higher-level field use Debug.",
        "notify": "Notification devices",
        "room": "Room-based notification devices",
        "info": "Minimum Info / Success",
        "warning": "Minimum Warning",
        "error": "Minimum Error",
        "critical": "Minimum Critical",
        "s2_title": "2. TTS outputs",
        "s2_desc": "Choose TTS engines, direct media-player outputs, and—when Snapcast is available—synchronised room clients plus their shared driving media player.",
        "engines": "TTS engines (languages shown; * = engine default)",
        "direct": "Direct TTS media players",
        "direct_room": "Room-based direct TTS players",
        "shared": "Shared media player driving Snapcast",
        "snap": "Snapcast room clients",
        "s3_title": "3. Integration options: {integration}",
        "s3_desc": "Options exposed by the selected integration.",
        "s4_title": "4. General options",
        "s4_desc": "Presence routing, fallback behavior, optional door-label filtering, notification defaults, and queue/timeouts.",
        "occ": "Room-presence entity",
        "occ_src": "Read occupied rooms from",
        "fallback": "Fallback room",
        "door": "Check occupied-room door before fallback",
        "door_label": "Door entity label (optional)",
        "level_overlap": "A notification device can have only one minimum-level assignment.",
        "room_notify_area": "A room-based notification device must have a Home Assistant area.",
        "room_tts_area": "A room-based direct TTS media player must have a Home Assistant area.",
    },
    "translations/en.json": {},
    "translations/de.json": {
        "s1_title": "1. Benachrichtigungsausgänge",
        "s1_desc": "Alle erkannten Benachrichtigungsentitäten sind automatisch ausgewählt. Nicht benötigte Geräte abwählen, raumgebundene Geräte markieren und bei Bedarf höhere Mindeststufen zuweisen. Nicht höher zugewiesene Geräte verwenden Debug.",
        "notify": "Benachrichtigungsgeräte",
        "room": "Raumgebundene Benachrichtigungsgeräte",
        "info": "Mindestens Info / Erfolg",
        "warning": "Mindestens Warnung",
        "error": "Mindestens Fehler",
        "critical": "Mindestens Kritisch",
        "s2_title": "2. TTS-Ausgänge",
        "s2_desc": "TTS-Engines, direkte Mediaplayer-Ausgänge und – wenn Snapcast verfügbar ist – synchronisierte Raum-Clients samt gemeinsamem steuernden Mediaplayer auswählen.",
        "engines": "TTS-Engines (Sprachen angezeigt; * = Engine-Standard)",
        "direct": "Direkte TTS-Mediaplayer",
        "direct_room": "Raumgebundene direkte TTS-Player",
        "shared": "Gemeinsamer Mediaplayer für Snapcast",
        "snap": "Snapcast-Raumclients",
        "s3_title": "3. Integrationsoptionen: {integration}",
        "s3_desc": "Optionen der ausgewählten Integration.",
        "s4_title": "4. Allgemeine Optionen",
        "s4_desc": "Anwesenheitsrouting, Fallback, optionaler Tür-Label-Filter, Benachrichtigungsstandards und Queue/Timeouts.",
        "occ": "Entität für Raumbelegung",
        "occ_src": "Belegte Räume lesen aus",
        "fallback": "Fallback-Bereich",
        "door": "Tür des belegten Bereichs vor Fallback prüfen",
        "door_label": "Label der Türentität (optional)",
        "level_overlap": "Ein Benachrichtigungsgerät darf nur einer Mindeststufe zugeordnet sein.",
        "room_notify_area": "Ein raumgebundenes Benachrichtigungsgerät benötigt einen Home-Assistant-Bereich.",
        "room_tts_area": "Ein raumgebundener direkter TTS-Mediaplayer benötigt einen Home-Assistant-Bereich.",
    },
    "translations/el.json": {
        "s1_title": "1. Έξοδοι ειδοποιήσεων",
        "s1_desc": "Όλες οι αναγνωρισμένες οντότητες ειδοποιήσεων επιλέγονται αυτόματα. Αποεπίλεξε ό,τι δεν χρειάζεσαι, όρισε ποιες είναι ανά δωμάτιο και βάλε υψηλότερο ελάχιστο επίπεδο όπου θέλεις. Όσες δεν μπουν σε υψηλότερη βαθμίδα χρησιμοποιούν Debug.",
        "notify": "Συσκευές ειδοποιήσεων",
        "room": "Συσκευές ειδοποιήσεων ανά δωμάτιο",
        "info": "Ελάχιστο Πληροφορία / Επιτυχία",
        "warning": "Ελάχιστο Προειδοποίηση",
        "error": "Ελάχιστο Σφάλμα",
        "critical": "Ελάχιστο Κρίσιμο",
        "s2_title": "2. Έξοδοι TTS",
        "s2_desc": "Επίλεξε μηχανές TTS, άμεσους media players και—όταν υπάρχει Snapcast—τους συγχρονισμένους clients ανά δωμάτιο μαζί με τον κοινό media player που τους τροφοδοτεί.",
        "engines": "Μηχανές TTS (φαίνονται οι γλώσσες· * = προεπιλογή μηχανής)",
        "direct": "Άμεσοι media players TTS",
        "direct_room": "Άμεσοι TTS players ανά δωμάτιο",
        "shared": "Κοινός media player που τροφοδοτεί το Snapcast",
        "snap": "Snapcast clients ανά δωμάτιο",
        "s3_title": "3. Επιλογές ενσωμάτωσης: {integration}",
        "s3_desc": "Επιλογές που παρέχει η επιλεγμένη ενσωμάτωση.",
        "s4_title": "4. Γενικές επιλογές",
        "s4_desc": "Παρουσία δωματίων, fallback, προαιρετικό label για αισθητήρες πόρτας, προεπιλογές ειδοποιήσεων και queue/timeouts.",
        "occ": "Οντότητα παρουσίας δωματίων",
        "occ_src": "Ανάγνωση κατειλημμένων δωματίων από",
        "fallback": "Εφεδρική περιοχή",
        "door": "Έλεγχος πόρτας πριν το fallback",
        "door_label": "Label οντότητας πόρτας (προαιρετικό)",
        "level_overlap": "Μια συσκευή ειδοποίησης μπορεί να ανήκει μόνο σε ένα ελάχιστο επίπεδο.",
        "room_notify_area": "Μια συσκευή ειδοποίησης ανά δωμάτιο πρέπει να έχει περιοχή στο Home Assistant.",
        "room_tts_area": "Ένας άμεσος TTS media player ανά δωμάτιο πρέπει να έχει περιοχή στο Home Assistant.",
    },
}
locales["translations/en.json"] = dict(locales["strings.json"])

for rel, L in locales.items():
    q = C / rel
    data = json.loads(q.read_text(encoding="utf-8"))
    old_cfg = data["config"]["step"]
    old_opt = data["options"]["step"]

    def build_steps(old):
        profile = old["notification_profile"]
        # Snapcast options are now part of this conceptual step too.
        for key, label in {
            "snapcast_source": "Announcement source name",
            "snapcast_only_source": "Manage only clients on this source",
            "snapcast_settle_delay": "Routing settle delay",
            "snapcast_verify_timeout": "Routing verification timeout",
            "snapcast_restore": "Restore previous mute states",
        }.items():
            profile.setdefault("data", {})[key] = label
            profile.setdefault("data_description", {})[key] = label
        profile["title"] = L["s3_title"]
        profile["description"] = L["s3_desc"]

        tts_step = old["tts"]
        tts_step["title"] = L["s2_title"]
        tts_step["description"] = L["s2_desc"]
        tts_step["data"]["tts_engines"] = L["engines"]
        tts_step["data"]["tts_room_players"] = L["direct"]
        tts_step["data"]["tts_area_players"] = L["direct_room"]
        tts_step["data"]["tts_media_player"] = L["shared"]
        tts_step["data"]["snapcast_outputs"] = L["snap"]

        queue = old["queue"]
        queue["title"] = L["s4_title"]
        queue["description"] = L["s4_desc"]
        queue["data"].update(
            {
                "default_title": old["outputs"]["data"].get("default_title", "Default title"),
                "critical_notify_data": old["outputs"]["data"].get("critical_notify_data", "Critical notification data"),
                "occupancy_sensor": L["occ"],
                "occupancy_attribute": L["occ_src"],
                "fallback_room": L["fallback"],
                "fallback_check_door": L["door"],
                "fallback_door_label": L["door_label"],
            }
        )
        queue["data_description"].update(
            {
                "default_title": old["outputs"]["data_description"].get("default_title", ""),
                "critical_notify_data": old["outputs"]["data_description"].get("critical_notify_data", ""),
                "occupancy_sensor": L["occ"],
                "occupancy_attribute": L["occ_src"],
                "fallback_room": L["fallback"],
                "fallback_check_door": L["door"],
                "fallback_door_label": L["door_label"],
            }
        )

        outputs = {
            "title": L["s1_title"],
            "description": L["s1_desc"],
            "data": {
                "notify_outputs": L["notify"],
                "notify_room_outputs": L["room"],
                "notify_info_outputs": L["info"],
                "notify_warning_outputs": L["warning"],
                "notify_error_outputs": L["error"],
                "notify_critical_outputs": L["critical"],
            },
            "data_description": {
                "notify_outputs": L["notify"],
                "notify_room_outputs": L["room"],
                "notify_info_outputs": L["info"],
                "notify_warning_outputs": L["warning"],
                "notify_error_outputs": L["error"],
                "notify_critical_outputs": L["critical"],
            },
        }
        return {
            "outputs": outputs,
            "tts": tts_step,
            "notification_profile": profile,
            "queue": queue,
        }

    data["config"]["step"] = build_steps(old_cfg)
    data["options"]["step"] = build_steps(old_opt)
    data["config"].setdefault("error", {})["notify_level_overlap"] = L["level_overlap"]
    data["options"].setdefault("error", {})["notify_level_overlap"] = L["level_overlap"]
    data["config"]["error"]["room_notify_area_required"] = L["room_notify_area"]
    data["options"]["error"]["room_notify_area_required"] = L["room_notify_area"]
    data["config"]["error"]["room_tts_area_required"] = L["room_tts_area"]
    data["options"]["error"]["room_tts_area_required"] = L["room_tts_area"]
    q.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# Update superseded regression contracts to the four-step UI.
p = ROOT / "tests" / "test_notify_routing_policy.py"
text = p.read_text(encoding="utf-8")
text = text.replace(
'''def test_translations_expose_scope_and_level_choices() -> None:
    strings=json.loads((C/"strings.json").read_text())
    for section in ("config","options"):
        assert "notification_routing" in strings[section]["step"]
    assert set(strings["selector"]["notify_scope"]["options"])=={"room","general"}
    assert set(strings["selector"]["notify_level"]["options"])=={
        "debug","info","warning","error","critical"
    }
''',
'''def test_translations_expose_scope_and_level_choices() -> None:
    strings=json.loads((C/"strings.json").read_text())
    for section in ("config","options"):
        outputs = strings[section]["step"]["outputs"]["data"]
        assert "notify_room_outputs" in outputs
        assert "notify_info_outputs" in outputs
        assert "notify_warning_outputs" in outputs
        assert "notify_error_outputs" in outputs
        assert "notify_critical_outputs" in outputs
''',
)
p.write_text(text, encoding="utf-8")

p = ROOT / "tests" / "test_occupancy_filter.py"
text = p.read_text(encoding="utf-8")
start = text.index("def test_occupancy_ui_uses_live_dropdown_not_free_text()")
text = text[:start] + '''def test_occupancy_ui_uses_live_dropdown_not_free_text() -> None:
    flow = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    queue_block = flow[
        flow.index("async def async_step_queue"):
        flow.index("class AnnouncementHubConfigFlow")
    ]
    assert "CONF_OCCUPANCY_SENSOR" in queue_block
    assert "CONF_OCCUPANCY_ATTRIBUTE" in queue_block
    assert 'value="__state__"' in queue_block
    assert "selector.SelectSelector(" in queue_block


def test_occupancy_and_fallback_live_on_general_options_page() -> None:
    import json

    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    for section in ("config", "options"):
        outputs = strings[section]["step"]["outputs"]["data"]
        assert "occupancy_sensor" not in outputs
        queue = strings[section]["step"]["queue"]["data"]
        assert {
            "occupancy_sensor",
            "occupancy_attribute",
            "fallback_room",
            "fallback_check_door",
            "fallback_door_label",
        } <= set(queue)
'''
p.write_text(text, encoding="utf-8")

p = ROOT / "tests" / "test_resources.py"
text = p.read_text(encoding="utf-8")
text = text.replace(
    'expected_steps = {"outputs", "notification_routing", "notification_profile", "tts", "snapcast", "occupancy", "occupancy_source", "queue"}',
    'expected_steps = {"outputs", "tts", "notification_profile", "queue"}',
)
text = text.replace('assert manifest["version"] == "0.7.0"', 'assert manifest["version"] == "0.8.0"')
text = text.replace(
'''        "notify_outputs",
        "snapcast_outputs",
        "companion_tts_outputs",
        "tts_engines",
        "tts_room_players",
        "tts_min_level",
''',
'''        "notify_outputs",
        "notify_room_outputs",
        "notify_info_outputs",
        "notify_warning_outputs",
        "notify_error_outputs",
        "notify_critical_outputs",
        "snapcast_outputs",
        "companion_tts_outputs",
        "tts_engines",
        "tts_room_players",
        "tts_area_players",
        "tts_min_level",
''',
)
text = text.replace(
'''        "fallback_check_door",
        "max_length",
''',
'''        "fallback_check_door",
        "fallback_door_label",
        "max_length",
''',
)
p.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Manifest / tests / changelog
# ---------------------------------------------------------------------------
p = C / "manifest.json"
manifest = json.loads(p.read_text(encoding="utf-8"))
if manifest.get("version") != "0.7.0":
    raise SystemExit(f"Unexpected manifest version: {manifest.get('version')}")
manifest["version"] = "0.8.0"
p.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

p = ROOT / "tests" / "test_resources.py"
text = p.read_text(encoding="utf-8")
text = text.replace(
    'expected_steps = {"outputs", "notification_routing", "notification_profile", "tts", "snapcast", "occupancy", "occupancy_source", "queue"}',
    'expected_steps = {"outputs", "tts", "notification_profile", "queue"}',
)
text = text.replace(
    'assert manifest["version"] == "0.7.0"',
    'assert manifest["version"] == "0.8.0"',
)
p.write_text(text, encoding="utf-8")

(ROOT / "tests" / "test_four_step_setup.py").write_text(
'''"""Contracts for the four-stage auto-discovery setup flow."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "custom_components" / "announcement_hub"


def test_only_four_visible_setup_steps_remain() -> None:
    strings = json.loads((C / "strings.json").read_text())
    expected = {"outputs", "tts", "notification_profile", "queue"}
    assert set(strings["config"]["step"]) == expected
    assert set(strings["options"]["step"]) == expected


def test_notify_step_auto_discovers_concrete_entities_and_groups_policies() -> None:
    flow = (C / "config_flow.py").read_text()
    outputs = (C / "outputs.py").read_text()
    assert "selected_default = (" in flow
    assert "if initial" in flow
    assert "CONF_NOTIFY_ROOM_OUTPUTS" in flow
    assert "CONF_NOTIFY_INFO_OUTPUTS" in flow
    assert "concrete recognised notification entities only" in outputs
    assert "entity_device_name" in outputs


def test_tts_step_uses_ha_default_languages_and_role_discovery() -> None:
    flow = (C / "config_flow.py").read_text()
    outputs = (C / "outputs.py").read_text()
    assert "tts_default_engine(self.hass)" in flow
    assert "tts_media_player_options(self.hass)" in flow
    assert "snapcast_output_options(self.hass)" in flow
    assert "supported_languages" in outputs
    assert "tts.async_default_engine" in outputs


def test_general_step_has_presence_fallback_door_label_and_timeouts() -> None:
    flow = (C / "config_flow.py").read_text()
    assert "selector.EntitySelector()" in flow
    assert "selector.LabelSelector()" in flow
    assert "CONF_FALLBACK_DOOR_LABEL" in flow
    assert "CONF_OUTPUT_AVAILABILITY_TIMEOUT" in flow


def test_general_direct_tts_players_bypass_room_filter() -> None:
    manager = (C / "manager.py").read_text()
    assert "def _tts_player_scope(" in manager
    assert "NOTIFY_SCOPE_GENERAL" in manager
    assert "area_id is not None" in manager


def test_no_startup_task_regression() -> None:
    manager = (C / "manager.py").read_text()
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(") == 2
''',
encoding="utf-8",
)

p = ROOT / "CHANGELOG.md"
text = p.read_text(encoding="utf-8")
head = "# Changelog\n\n"
entry = '''## 0.8.0 - 2026-10-02

- Reworked setup into four conceptual stages: Notification outputs, TTS outputs,
  per-integration options, and General options.
- Notification discovery now lists concrete supported entities as
  Integration · Device · Entity and selects all recognised outputs by default on
  first setup. Room/movable scope and minimum notification level are configured
  on the same page through grouped multi-selects.
- TTS discovery now lists concrete TTS engines with advertised languages and
  automatically selects Home Assistant's default engine when available.
- When Snapcast clients are discovered, the TTS page offers those room clients
  plus the shared media player that drives their synchronized stream.
- Non-Snapcast media players with play-media support are offered as direct TTS
  outputs. Area-bound players default to Room scope; area-less players default
  to General scope.
- TTS keeps one global minimum level.
- Integration-specific visual options and Snapcast routing behavior are grouped
  under the third setup stage.
- General options now combine queue/timeouts, room-presence entity and
  state/attribute source, fallback room, door checking, and an optional Home
  Assistant label that restricts which door entities may authorize fallback.
- General direct TTS outputs bypass occupancy filtering; Room outputs continue
  to follow occupied/fallback areas.

'''
if not text.startswith(head):
    raise SystemExit("Unexpected changelog header")
p.write_text(head + entry + text[len(head):], encoding="utf-8")

print("Applied Announcement Hub 0.8.0 four-step auto-discovery setup")
