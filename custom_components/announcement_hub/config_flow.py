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
    CONF_IDLE_TIMEOUT,
    CONF_NOTIFY_OUTPUTS,
    CONF_NOTIFY_PROFILES,
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
    CONF_TTS_MEDIA_PLAYER,
    CONF_TTS_MIN_LEVEL,
    CONF_TTS_OPTIONS,
    DEFAULT_COMPANION_TTS_MEDIA_STREAM,
    DEFAULT_COMPANION_TTS_WPM,
    DEFAULT_CRITICAL_NOTIFY_DATA,
    DEFAULT_DISPATCH_ORDER,
    DEFAULT_IDLE_TIMEOUT,
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
    TTS_MIN_LEVELS,
)
from .message_parts import (
    integration_label,
    normalise_notify_profile,
    resolve_notify_profile,
)
from .outputs import (
    companion_tts_output_options,
    expand_notify_output_tokens,
    notify_output_options,
    resolve_notify_outputs,
    snapcast_output_options,
    tts_engine_options,
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


class _AnnouncementFlowMixin:
    """Shared multi-page setup for config and options flows."""

    _working: dict[str, Any]
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
        """Select physical visual, Snapcast, and Companion outputs."""
        if user_input is not None:
            self._store_step(
                user_input,
                {
                    CONF_NOTIFY_OUTPUTS: [],
                    CONF_SNAPCAST_OUTPUTS: [],
                    CONF_COMPANION_TTS_OUTPUTS: [],
                    CONF_DEFAULT_TITLE: DEFAULT_TITLE,
                    CONF_CRITICAL_NOTIFY_DATA: {},
                },
            )
            self._prepare_notify_profile_steps()
            return await self.async_step_notification_profile()

        schema = probatio.Schema(
            {
                probatio.Optional(
                    CONF_NOTIFY_OUTPUTS,
                    default=self._value(CONF_NOTIFY_OUTPUTS, []),
                ): _multi_select(notify_output_options(self.hass)),
                probatio.Optional(
                    CONF_SNAPCAST_OUTPUTS,
                    default=self._value(CONF_SNAPCAST_OUTPUTS, []),
                ): _multi_select(snapcast_output_options(self.hass)),
                probatio.Optional(
                    CONF_COMPANION_TTS_OUTPUTS,
                    default=self._value(CONF_COMPANION_TTS_OUTPUTS, []),
                ): _multi_select(companion_tts_output_options(self.hass)),
                probatio.Required(
                    CONF_DEFAULT_TITLE,
                    default=self._value(CONF_DEFAULT_TITLE, DEFAULT_TITLE),
                ): selector.TextSelector(),
                probatio.Optional(
                    CONF_CRITICAL_NOTIFY_DATA,
                    default=self._value(
                        CONF_CRITICAL_NOTIFY_DATA,
                        DEFAULT_CRITICAL_NOTIFY_DATA,
                    ),
                ): selector.ObjectSelector(),
            }
        )
        return self.async_show_form(step_id="outputs", data_schema=schema)


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
            return await self.async_step_tts()

        integration = self._notify_profile_domains[self._notify_profile_index]
        profiles = dict(self._working.get(CONF_NOTIFY_PROFILES, {}) or {})
        current = resolve_notify_profile(profiles, integration)
        errors: dict[str, str] = {}

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
        """Configure speech generation and the shared playback path."""
        errors: dict[str, str] = {}
        if user_input is not None:
            engines = list(user_input.get(CONF_TTS_ENGINES, []))
            player = user_input.get(CONF_TTS_MEDIA_PLAYER)
            snapcast = list(self._working.get(CONF_SNAPCAST_OUTPUTS, []))
            if engines and not player:
                errors["base"] = "tts_player_required"
            elif player and not engines:
                errors["base"] = "tts_engine_required"
            elif snapcast and (not engines or not player):
                errors["base"] = "snapcast_tts_path_required"
            else:
                self._store_step(
                    user_input,
                    {
                        CONF_TTS_ENGINES: [],
                        CONF_TTS_MEDIA_PLAYER: None,
                        CONF_TTS_MIN_LEVEL: DEFAULT_TTS_MIN_LEVEL,
                        CONF_TTS_CACHE: DEFAULT_TTS_CACHE,
                        CONF_TTS_LANGUAGE: DEFAULT_TTS_LANGUAGE,
                        CONF_TTS_OPTIONS: {},
                        CONF_COMPANION_TTS_MEDIA_STREAM: (
                            DEFAULT_COMPANION_TTS_MEDIA_STREAM
                        ),
                        CONF_COMPANION_TTS_WPM: DEFAULT_COMPANION_TTS_WPM,
                    },
                )
                return await self.async_step_snapcast()

        schema = probatio.Schema(
            {
                probatio.Optional(
                    CONF_TTS_ENGINES,
                    default=self._value(CONF_TTS_ENGINES, []),
                ): _multi_select(tts_engine_options(self.hass)),
                _optional_marker(
                    CONF_TTS_MEDIA_PLAYER,
                    self._value(CONF_TTS_MEDIA_PLAYER, None),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="media_player")
                ),
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
            step_id="tts", data_schema=schema, errors=errors
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
            return await self.async_step_queue()

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

    async def async_step_queue(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure serialization and availability/playback timeouts."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._store_step(
                user_input,
                {
                    CONF_DISPATCH_ORDER: DEFAULT_DISPATCH_ORDER,
                    CONF_QUEUE_MAX: DEFAULT_QUEUE_MAX,
                    CONF_OUTPUT_AVAILABILITY_TIMEOUT: (
                        DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT
                    ),
                    CONF_IDLE_TIMEOUT: DEFAULT_IDLE_TIMEOUT,
                    CONF_START_TIMEOUT: DEFAULT_START_TIMEOUT,
                    CONF_PLAYBACK_TIMEOUT: DEFAULT_PLAYBACK_TIMEOUT,
                    CONF_POST_PLAY_DELAY: DEFAULT_POST_PLAY_DELAY,
                },
            )
            has_server_tts = bool(
                self._working.get(CONF_TTS_ENGINES)
                and self._working.get(CONF_TTS_MEDIA_PLAYER)
            )
            if not (
                self._working.get(CONF_NOTIFY_OUTPUTS)
                or self._working.get(CONF_COMPANION_TTS_OUTPUTS)
                or has_server_tts
            ):
                errors["base"] = "output_required"
            else:
                return await self._async_finish()

        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_DISPATCH_ORDER,
                    default=self._value(
                        CONF_DISPATCH_ORDER, DEFAULT_DISPATCH_ORDER
                    ),
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
                    selector.NumberSelectorConfig(
                        min=1,
                        max=1000,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                probatio.Required(
                    CONF_OUTPUT_AVAILABILITY_TIMEOUT,
                    default=self._value(
                        CONF_OUTPUT_AVAILABILITY_TIMEOUT,
                        DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=300,
                        step=0.5,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                probatio.Required(
                    CONF_IDLE_TIMEOUT,
                    default=self._value(
                        CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=1800,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                probatio.Required(
                    CONF_START_TIMEOUT,
                    default=self._value(
                        CONF_START_TIMEOUT, DEFAULT_START_TIMEOUT
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=120,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                probatio.Required(
                    CONF_PLAYBACK_TIMEOUT,
                    default=self._value(
                        CONF_PLAYBACK_TIMEOUT, DEFAULT_PLAYBACK_TIMEOUT
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5,
                        max=3600,
                        step=5,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                probatio.Required(
                    CONF_POST_PLAY_DELAY,
                    default=self._value(
                        CONF_POST_PLAY_DELAY, DEFAULT_POST_PLAY_DELAY
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
            }
        )
        return self.async_show_form(
            step_id="queue", data_schema=schema, errors=errors
        )


class AnnouncementHubConfigFlow(
    _AnnouncementFlowMixin, config_entries.ConfigFlow, domain=DOMAIN
):
    """Create the single Announcement Hub instance."""

    VERSION = 3

    def __init__(self) -> None:
        self._working = {}
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
