"""Config and options flows for Announcement Hub."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import probatio

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    COMPANION_STREAMS,
    CONF_COMPANION_TTS_MEDIA_STREAM,
    CONF_COMPANION_TTS_OUTPUTS,
    CONF_COMPANION_TTS_WPM,
    CONF_CRITICAL_NOTIFY_DATA,
    CONF_DEFAULT_TITLE,
    CONF_DISPATCH_ORDER,
    CONF_FALLBACK_CHECK_DOOR,
    CONF_FALLBACK_DOOR_LABEL,
    CONF_FALLBACK_ROOM,
    CONF_IDLE_TIMEOUT,
    CONF_NOTIFY_OUTPUTS,
    CONF_NOTIFY_POLICIES,
    CONF_NOTIFY_ROOM_OUTPUTS,
    CONF_NOTIFY_INFO_OUTPUTS,
    CONF_NOTIFY_WARNING_OUTPUTS,
    CONF_NOTIFY_ERROR_OUTPUTS,
    CONF_NOTIFY_CRITICAL_OUTPUTS,
    CONF_NOTIFY_PROFILES,
    CONF_OCCUPANCY_ATTRIBUTE,
    CONF_OCCUPANCY_SENSOR,
    CONF_OUTPUT_AVAILABILITY_TIMEOUT,
    CONF_PLAYBACK_TIMEOUT,
    CONF_POST_PLAY_DELAY,
    CONF_QUEUE_MAX,
    CONF_SNAPCAST_ONLY_SOURCE,
    CONF_SNAPCAST_OUTPUTS,
    CONF_SNAPCAST_RESTORE,
    CONF_SNAPCAST_SETTLE_DELAY,
    CONF_SNAPCAST_SOURCE,
    CONF_SNAPCAST_VERIFY_TIMEOUT,
    CONF_START_TIMEOUT,
    CONF_TTS_CACHE,
    CONF_TTS_ENGINES,
    CONF_TTS_LANGUAGE,
    CONF_TTS_VOICE,
    CONF_TTS_MEDIA_PLAYER,
    CONF_TTS_ROOM_PLAYERS,
    CONF_TTS_AREA_PLAYERS,
    CONF_TTS_PLAYER_POLICIES,
    CONF_TTS_MIN_LEVEL,
    CONF_TTS_OPTIONS,
    DEFAULT_COMPANION_TTS_MEDIA_STREAM,
    DEFAULT_COMPANION_TTS_WPM,
    DEFAULT_CRITICAL_NOTIFY_DATA,
    DEFAULT_DISPATCH_ORDER,
    DEFAULT_FALLBACK_CHECK_DOOR,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_NOTIFY_MIN_LEVEL,
    DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT,
    DEFAULT_PLAYBACK_TIMEOUT,
    DEFAULT_POST_PLAY_DELAY,
    DEFAULT_QUEUE_MAX,
    DEFAULT_SNAPCAST_ONLY_SOURCE,
    DEFAULT_SNAPCAST_RESTORE,
    DEFAULT_SNAPCAST_SETTLE_DELAY,
    DEFAULT_SNAPCAST_SOURCE,
    DEFAULT_SNAPCAST_VERIFY_TIMEOUT,
    DEFAULT_START_TIMEOUT,
    DEFAULT_TITLE,
    DEFAULT_TTS_CACHE,
    DEFAULT_TTS_LANGUAGE,
    DEFAULT_TTS_MIN_LEVEL,
    DEFAULT_TTS_OPTIONS,
    DISPATCH_ORDERS,
    INTEGRATION_MOBILE_APP,
    INTEGRATION_NFANDROIDTV,
    NFANDROIDTV_COLORS,
    NFANDROIDTV_FONTSIZES,
    NFANDROIDTV_POSITIONS,
    NFANDROIDTV_TRANSPARENCIES,
    PROFILE_DEFAULT,
    PROFILE_DISPLAY_BUFFER,
    PROFILE_INTEGRATION_DATA,
    PROFILE_MAX_DISPLAY,
    PROFILE_MAX_LENGTH,
    PROFILE_MIN_DISPLAY,
    PROFILE_NF_COLOR,
    PROFILE_NF_FONTSIZE,
    PROFILE_NF_INTERRUPT,
    PROFILE_NF_POSITION,
    PROFILE_NF_TRANSPARENCY,
    PROFILE_PART_GAP,
    PROFILE_READING_WPM,
    PROFILE_REPLACE_PARTS,
    PROFILE_SHOW_PART_NUMBER,
    DOMAIN,
    NAME,
    NOTIFY_MIN_LEVELS,
    NOTIFY_POLICY_MIN_LEVEL,
    NOTIFY_POLICY_SCOPE,
    NOTIFY_SCOPES,
    NOTIFY_SCOPE_GENERAL,
    NOTIFY_SCOPE_ROOM,
    TTS_MIN_LEVELS,
)
from .message_parts import (
    integration_label,
    normalise_notify_profile,
    resolve_notify_profile,
)
from .outputs import (
    companion_tts_output_options,
    entity_area_id,
    expand_notify_output_tokens,
    expand_snapcast_output_tokens,
    notify_output_options,
    area_name,
    resolve_notify_outputs,
    snapcast_output_options,
    tts_default_engine,
    tts_default_language,
    tts_default_voice,
    tts_engine_languages,
    tts_engine_options,
    tts_engine_voice_options,
    tts_media_player_options,
)


def _optional_marker(key: str, value: str | None) -> probatio.Marker:
    if value:
        return probatio.Optional(key, default=value)
    return probatio.Optional(key)


def _multi_select(
    options: list[dict[str, str]],
) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            multiple=True,
            custom_value=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _known_multi_select(
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


class _AnnouncementFlowMixin:
    """Shared multi-page setup for config and options flows."""

    _working: dict[str, Any]
    _notify_route_outputs: list[Any]
    _notify_route_index: int
    _notify_profile_domains: list[str]
    _notify_profile_index: int

    @abstractmethod
    async def _async_finish(self) -> ConfigFlowResult:
        """Finish the concrete flow."""

    def _value(self, key: str, default: Any) -> Any:
        return self._working.get(key, default)

    def _store_step(
        self,
        user_input: dict[str, Any],
        neutral_values: dict[str, Any],
    ) -> None:
        self._working.update(neutral_values)
        self._working.update(user_input)

    async def async_step_outputs(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: discover and configure notification outputs."""
        options = notify_output_options(self.hass)
        known = [str(item["value"]) for item in options]
        # Discovery is authoritative for the setup UI: every currently
        # supported notify entity is preselected whenever this page opens.
        # The user can deselect unwanted outputs before submitting.
        selected_default = list(known)

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


    def _prepare_notify_profile_steps(self) -> None:
        refs = expand_notify_output_tokens(
            self.hass,
            list(self._working.get(CONF_NOTIFY_OUTPUTS, [])),
        )
        domains = {
            output.integration or PROFILE_DEFAULT
            for output in resolve_notify_outputs(self.hass, refs)
        }
        self._notify_profile_domains = sorted(
            domains,
            key=lambda domain: integration_label(domain).casefold(),
        )
        configured_profiles = self._working.get(CONF_NOTIFY_PROFILES, {})
        if not isinstance(configured_profiles, dict):
            configured_profiles = {}
        self._working[CONF_NOTIFY_PROFILES] = {
            domain: profile
            for domain, profile in configured_profiles.items()
            if domain in domains and isinstance(profile, dict)
        }
        self._notify_profile_index = 0

    async def async_step_notification_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure splitting, read timing, and native provider options."""
        if self._notify_profile_index >= len(self._notify_profile_domains):
            return await self.async_step_queue()

        integration = self._notify_profile_domains[self._notify_profile_index]
        profiles = dict(self._working.get(CONF_NOTIFY_PROFILES, {}) or {})
        current = resolve_notify_profile(profiles, integration)
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
                description_placeholders={
                    "integration": "Snapcast",
                    "integration_purpose": "Snapcast audio routing",
                },
            )

        if user_input is not None:
            minimum = float(user_input.get(PROFILE_MIN_DISPLAY, 0))
            maximum = float(user_input.get(PROFILE_MAX_DISPLAY, 0))
            if maximum < minimum:
                errors["base"] = "display_time_order"
            else:
                profiles[integration] = normalise_notify_profile(
                    user_input, integration
                )
                self._working[CONF_NOTIFY_PROFILES] = profiles
                self._notify_profile_index += 1
                return await self.async_step_notification_profile()

        fields: dict[probatio.Marker, Any] = {
            probatio.Required(
                PROFILE_MAX_LENGTH,
                default=current[PROFILE_MAX_LENGTH],
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=10000,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="characters",
                )
            ),
            probatio.Required(
                PROFILE_READING_WPM,
                default=current[PROFILE_READING_WPM],
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=60,
                    max=600,
                    step=5,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="wpm",
                )
            ),
            probatio.Required(
                PROFILE_MIN_DISPLAY,
                default=current[PROFILE_MIN_DISPLAY],
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=120,
                    step=0.5,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            probatio.Required(
                PROFILE_MAX_DISPLAY,
                default=current[PROFILE_MAX_DISPLAY],
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.5,
                    max=600,
                    step=0.5,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            probatio.Required(
                PROFILE_DISPLAY_BUFFER,
                default=current[PROFILE_DISPLAY_BUFFER],
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=30,
                    step=0.25,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            probatio.Required(
                PROFILE_PART_GAP,
                default=current[PROFILE_PART_GAP],
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=10,
                    step=0.05,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            probatio.Required(
                PROFILE_SHOW_PART_NUMBER,
                default=current[PROFILE_SHOW_PART_NUMBER],
            ): selector.BooleanSelector(),
            probatio.Optional(
                PROFILE_INTEGRATION_DATA,
                default=current.get(PROFILE_INTEGRATION_DATA, {}),
            ): selector.ObjectSelector(),
        }

        if integration == INTEGRATION_NFANDROIDTV:
            fields.update(
                {
                    probatio.Required(
                        PROFILE_NF_POSITION,
                        default=current[PROFILE_NF_POSITION],
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(NFANDROIDTV_POSITIONS),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="nfandroidtv_position",
                        )
                    ),
                    probatio.Required(
                        PROFILE_NF_FONTSIZE,
                        default=current[PROFILE_NF_FONTSIZE],
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(NFANDROIDTV_FONTSIZES),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="nfandroidtv_fontsize",
                        )
                    ),
                    probatio.Required(
                        PROFILE_NF_COLOR,
                        default=current[PROFILE_NF_COLOR],
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(NFANDROIDTV_COLORS),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="nfandroidtv_color",
                        )
                    ),
                    probatio.Required(
                        PROFILE_NF_TRANSPARENCY,
                        default=current[PROFILE_NF_TRANSPARENCY],
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(NFANDROIDTV_TRANSPARENCIES),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="nfandroidtv_transparency",
                        )
                    ),
                    probatio.Required(
                        PROFILE_NF_INTERRUPT,
                        default=current[PROFILE_NF_INTERRUPT],
                    ): selector.BooleanSelector(),
                }
            )
        elif integration == INTEGRATION_MOBILE_APP:
            fields[
                probatio.Required(
                    PROFILE_REPLACE_PARTS,
                    default=current[PROFILE_REPLACE_PARTS],
                )
            ] = selector.BooleanSelector()

        return self.async_show_form(
            step_id="notification_profile",
            data_schema=probatio.Schema(fields),
            errors=errors,
            description_placeholders={
                "integration": integration_label(integration)
            },
        )

    async def async_step_tts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: configure TTS engines and physical output roles."""
        errors: dict[str, str] = {}

        engine_options = tts_engine_options(self.hass)
        engine_ids = [str(item["value"]) for item in engine_options]
        configured_engines = [
            value
            for value in self._value(CONF_TTS_ENGINES, [])
            if value in engine_ids
        ]
        default_engine = tts_default_engine(self.hass)
        engine_default = configured_engines or (
            [default_engine] if default_engine in engine_ids else []
        )

        # Language and voice belong directly to the selected TTS engine. Home
        # Assistant config flows are not live-reactive, so the currently saved
        # or default engine drives the first render; reopening the step after an
        # engine change refreshes the provider-advertised language/voice lists.
        language_engines = engine_default or engine_ids
        language_values = list(
            tts_engine_languages(self.hass, language_engines)
        )
        configured_language = str(
            self._value(CONF_TTS_LANGUAGE, DEFAULT_TTS_LANGUAGE) or ""
        )
        if configured_language in language_values:
            language_default = configured_language
        else:
            preferred_language = tts_default_language(
                self.hass, language_engines
            )
            language_default = (
                preferred_language
                if preferred_language in language_values
                else None
            )

        configured_tts_options = dict(
            self._value(CONF_TTS_OPTIONS, DEFAULT_TTS_OPTIONS) or {}
        )
        voice_engine = (
            engine_default[0] if len(engine_default) == 1 else None
        )
        voice_options = tts_engine_voice_options(
            self.hass, voice_engine, language_default
        )
        voice_values = {
            str(item["value"]) for item in voice_options
        }
        configured_voice = str(
            configured_tts_options.get("voice", "") or ""
        )
        if configured_voice in voice_values:
            voice_default = configured_voice
        else:
            voice_default = tts_default_voice(
                self.hass, voice_engine, language_default
            )
        additional_tts_options = (
            {
                key: value
                for key, value in configured_tts_options.items()
                if key != "voice"
            }
            if voice_options
            else configured_tts_options
        )

        # The UI exposes one direct-player concept only: players bound to a
        # Home Assistant room. The old "all direct players + room subset" pair
        # was redundant and made it unclear which selector actually routed TTS.
        all_direct_options = tts_media_player_options(self.hass)
        direct_options = [
            item
            for item in all_direct_options
            if entity_area_id(self.hass, str(item["value"])) is not None
        ]
        direct_ids = [str(item["value"]) for item in direct_options]
        configured_direct = [
            value
            for value in self._value(CONF_TTS_ROOM_PLAYERS, [])
            if value in direct_ids
        ]
        policies = self._working.get(CONF_TTS_PLAYER_POLICIES, {})
        if not isinstance(policies, dict):
            policies = {}
        area_default: list[str] = []
        for entity_id in configured_direct:
            policy = policies.get(entity_id, {})
            scope = (
                str(policy.get(NOTIFY_POLICY_SCOPE))
                if isinstance(policy, dict)
                and policy.get(NOTIFY_POLICY_SCOPE)
                else NOTIFY_SCOPE_ROOM
            )
            if scope == NOTIFY_SCOPE_ROOM:
                area_default.append(entity_id)

        snap_options = snapcast_output_options(self.hass)
        snap_ids = [
            str(item["value"]).removeprefix("entity:")
            for item in snap_options
        ]
        snap_default = [
            value
            for value in expand_snapcast_output_tokens(
                self.hass,
                self._value(CONF_SNAPCAST_OUTPUTS, []),
            )
            if value in snap_ids
        ]

        if user_input is not None:
            engines = [
                value
                for value in user_input.get(CONF_TTS_ENGINES, [])
                if value in engine_ids
            ]
            direct = [
                value
                for value in user_input.get(CONF_TTS_AREA_PLAYERS, [])
                if value in direct_ids
            ]
            snapcast_refs = list(
                user_input.get(CONF_SNAPCAST_OUTPUTS, [])
            )
            snapcast = list(
                expand_snapcast_output_tokens(
                    self.hass, snapcast_refs
                )
            )
            shared_player = user_input.get(CONF_TTS_MEDIA_PLAYER)

            if (direct or snapcast) and not engines:
                errors["base"] = "tts_engine_required"
            elif snapcast and not shared_player:
                errors["base"] = "snapcast_tts_path_required"
            else:
                self._working[CONF_TTS_ENGINES] = engines
                self._working[CONF_TTS_ROOM_PLAYERS] = direct
                self._working[CONF_TTS_PLAYER_POLICIES] = {
                    entity_id: {
                        NOTIFY_POLICY_SCOPE: NOTIFY_SCOPE_ROOM
                    }
                    for entity_id in direct
                }
                self._working.pop(CONF_TTS_AREA_PLAYERS, None)
                self._working[CONF_SNAPCAST_OUTPUTS] = snapcast_refs
                self._working[CONF_TTS_MEDIA_PLAYER] = shared_player

                for key in (
                    CONF_TTS_MIN_LEVEL,
                    CONF_TTS_CACHE,
                    CONF_TTS_LANGUAGE,
                    CONF_COMPANION_TTS_OUTPUTS,
                    CONF_COMPANION_TTS_MEDIA_STREAM,
                    CONF_COMPANION_TTS_WPM,
                ):
                    if key in user_input:
                        self._working[key] = user_input[key]

                submitted_options = dict(
                    user_input.get(
                        CONF_TTS_OPTIONS, additional_tts_options
                    )
                    or {}
                )
                if voice_options:
                    selected_voice = str(
                        user_input.get(CONF_TTS_VOICE, "") or ""
                    )
                    if selected_voice in voice_values:
                        submitted_options["voice"] = selected_voice
                    else:
                        submitted_options.pop("voice", None)
                self._working[CONF_TTS_OPTIONS] = submitted_options

                self._prepare_notify_profile_steps()
                if snapcast:
                    self._notify_profile_domains.append("snapcast")
                return await self.async_step_notification_profile()

        # Keep engine-specific controls together and at the top of the page.
        fields: dict[probatio.Marker, Any] = {
            probatio.Optional(
                CONF_TTS_ENGINES,
                default=engine_default,
            ): _known_multi_select(engine_options),
            _optional_marker(
                CONF_TTS_LANGUAGE,
                language_default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=language_values,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
        if voice_options:
            fields[
                _optional_marker(
                    CONF_TTS_VOICE,
                    voice_default,
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=voice_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        fields[
            probatio.Optional(
                CONF_TTS_OPTIONS,
                default=additional_tts_options,
            )
        ] = selector.ObjectSelector()

        fields[
            probatio.Optional(
                CONF_TTS_AREA_PLAYERS,
                default=area_default,
            )
        ] = _known_multi_select(direct_options)

        if snap_options:
            fields[
                probatio.Optional(
                    CONF_SNAPCAST_OUTPUTS,
                    default=[
                        f"entity:{entity_id}"
                        for entity_id in snap_default
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
                    default=self._value(
                        CONF_TTS_MIN_LEVEL, DEFAULT_TTS_MIN_LEVEL
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(TTS_MIN_LEVELS),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="tts_min_level",
                    )
                ),
                probatio.Required(
                    CONF_TTS_CACHE,
                    default=self._value(
                        CONF_TTS_CACHE, DEFAULT_TTS_CACHE
                    ),
                ): selector.BooleanSelector(),
                probatio.Optional(
                    CONF_COMPANION_TTS_OUTPUTS,
                    default=self._value(
                        CONF_COMPANION_TTS_OUTPUTS, []
                    ),
                ): _multi_select(
                    companion_tts_output_options(self.hass)
                ),
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
        return self.async_show_form(
            step_id="tts",
            data_schema=probatio.Schema(fields),
            errors=errors,
        )

    async def async_step_snapcast(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure routing details for selected Snapcast outputs."""
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
            return await self.async_step_occupancy()

        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_SNAPCAST_SOURCE,
                    default=self._value(
                        CONF_SNAPCAST_SOURCE, DEFAULT_SNAPCAST_SOURCE
                    ),
                ): selector.TextSelector(),
                probatio.Required(
                    CONF_SNAPCAST_ONLY_SOURCE,
                    default=self._value(
                        CONF_SNAPCAST_ONLY_SOURCE,
                        DEFAULT_SNAPCAST_ONLY_SOURCE,
                    ),
                ): selector.BooleanSelector(),
                probatio.Required(
                    CONF_SNAPCAST_SETTLE_DELAY,
                    default=self._value(
                        CONF_SNAPCAST_SETTLE_DELAY,
                        DEFAULT_SNAPCAST_SETTLE_DELAY,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10,
                        step=0.05,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                probatio.Required(
                    CONF_SNAPCAST_VERIFY_TIMEOUT,
                    default=self._value(
                        CONF_SNAPCAST_VERIFY_TIMEOUT,
                        DEFAULT_SNAPCAST_VERIFY_TIMEOUT,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.5,
                        max=30,
                        step=0.5,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                probatio.Required(
                    CONF_SNAPCAST_RESTORE,
                    default=self._value(
                        CONF_SNAPCAST_RESTORE, DEFAULT_SNAPCAST_RESTORE
                    ),
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="snapcast", data_schema=schema)

    def _occupancy_attribute_options(self) -> list[str]:
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

    async def async_step_queue(
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




class AnnouncementHubConfigFlow(
    _AnnouncementFlowMixin, config_entries.ConfigFlow, domain=DOMAIN
):
    """Create the single Announcement Hub instance."""

    VERSION = 3

    def __init__(self) -> None:
        self._working = {}
        self._notify_route_outputs = []
        self._notify_route_index = 0
        self._notify_profile_domains = []
        self._notify_profile_index = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_outputs()

    async def _async_finish(self) -> ConfigFlowResult:
        return self.async_create_entry(title=NAME, data=self._working)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "AnnouncementHubOptionsFlow":
        return AnnouncementHubOptionsFlow()


class AnnouncementHubOptionsFlow(_AnnouncementFlowMixin, OptionsFlow):
    """Edit output and queue settings."""

    def __init__(self) -> None:
        self._working = {}
        self._notify_route_outputs = []
        self._notify_route_index = 0
        self._notify_profile_domains = []
        self._notify_profile_index = 0

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._working = {
            **self.config_entry.data,
            **self.config_entry.options,
        }
        return await self.async_step_outputs()

    async def _async_finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._working)
