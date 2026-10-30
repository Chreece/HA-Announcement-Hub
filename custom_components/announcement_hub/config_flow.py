"""Config and options flows for Announcement Hub."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import probatio

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.components.conversation.agent_manager import get_agent_manager
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
    CONF_DEFAULT_USE_AI,
    CONF_DEFAULT_AI_AGENT,
    CONF_FALLBACK_AI_AGENT,
    CONF_DISPATCH_ORDER,
    CONF_CHANNEL_FALLBACK_MODE,
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
    CONF_SLEEP_ROOMS_ENTITY,
    CONF_SLEEP_ROOMS_ATTRIBUTE,
    CONF_SLEEP_MUTE_TTS,
    CONF_SLEEP_FALLBACK_WRITTEN,
    CONF_SLEEP_FALLBACK_OUTPUTS,
    CONF_PERSON_PROFILES,
    CONF_PERSON_GROUP_LANGUAGE,
    CONF_PERSON_GROUP_VOICE,
    CONF_PERSON_GROUP_TRANSLATE,
    CONF_PERSON_GROUP_AGENT,
    CONF_PERSON_GROUP_TTS_ENGINE,
    CONF_PERSON_GROUP_REWRITE,
    CONF_PERSON_GROUP_ADDRESSEE,
    CONF_PERSON_GROUP_GREETING,
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
    CONF_DIRECT_TTS_ANNOUNCE,
    CONF_TTS_OPTIONS,
    DEFAULT_COMPANION_TTS_MEDIA_STREAM,
    DEFAULT_COMPANION_TTS_WPM,
    DEFAULT_CRITICAL_NOTIFY_DATA,
    DEFAULT_DISPATCH_ORDER,
    DEFAULT_CHANNEL_FALLBACK_MODE,
    DEFAULT_USE_AI,
    DEFAULT_AI_AGENT,
    DEFAULT_FALLBACK_AI_AGENT,
    DEFAULT_FALLBACK_CHECK_DOOR,
    DEFAULT_SLEEP_MUTE_TTS,
    DEFAULT_SLEEP_FALLBACK_WRITTEN,
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
    DEFAULT_DIRECT_TTS_ANNOUNCE,
    DEFAULT_TTS_OPTIONS,
    DISPATCH_ORDERS,
    CHANNEL_FALLBACK_MODES,
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
from .ai_filter import resolve_preferred_assist_agent
from .flow_settings import merge_reconfiguration
from .provider_labels import provider_label
from .sleep_delivery import (
    INTEGRATION_TOKEN_PREFIX,
    sleep_notify_output_options,
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
    tts_engine_supports_voice,
    tts_engine_voice_options,
    tts_media_player_options,
)


_NF_TRANSPARENCY_TO_SELECTOR = {
    "0%": "p0",
    "25%": "p25",
    "50%": "p50",
    "75%": "p75",
    "100%": "p100",
}
_NF_TRANSPARENCY_FROM_SELECTOR = {
    value: key for key, value in _NF_TRANSPARENCY_TO_SELECTOR.items()
}

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


# First-time setup remains a wizard; existing entries offer direct editing.
EDIT_MENU_OPTIONS = (
    "edit_outputs",
    "edit_tts",
    "edit_profiles",
    "edit_general",
    "edit_people",
    "edit_advanced_ai",
    "edit_audio",
    "edit_room_safety",
    "edit_all",
)


class _AnnouncementFlowMixin:
    """Shared multi-page setup for config and options flows."""

    _working: dict[str, Any]
    _editing_existing: bool
    _edit_section: str | None
    _notify_route_outputs: list[Any]
    _notify_route_index: int
    _notify_profile_domains: list[str]
    _notify_profile_index: int
    _person_config_ids: list[str]
    _person_index: int

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

    async def async_step_edit_outputs(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit only the notification outputs and their per-output policies."""
        self._edit_section = "outputs"
        return await self.async_step_outputs()

    async def async_step_edit_tts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit only the configured TTS engines, players, and devices."""
        self._edit_section = "tts"
        return await self.async_step_tts()

    async def async_step_edit_profiles(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit existing provider profiles, including Snapcast when selected."""
        self._edit_section = "profiles"
        self._prepare_notify_profile_steps()
        if expand_snapcast_output_tokens(
            self.hass, list(self._working.get(CONF_SNAPCAST_OUTPUTS, []))
        ):
            self._notify_profile_domains.append("snapcast")
        return await self.async_step_notification_profile()

    async def async_step_edit_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Jump directly to general, occupancy, queue, and AI settings."""
        self._edit_section = "queue"
        return await self.async_step_queue()


    async def async_step_edit_room_safety(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """One area at a time: optional independent presence verification."""
        if user_input is not None:
            area = str(user_input.get("area", "") or "")
            sensor = str(user_input.get("presence_sensor", "") or "")
            use = bool(user_input.get("verify_presence", False))
            from homeassistant.helpers import area_registry as ar
            if area not in ar.async_get(self.hass).areas:
                return self.async_show_form(
                    step_id="edit_room_safety",
                    data_schema=self._room_safety_schema(),
                    errors={"base": "invalid_person_area"},
                )
            if use and not sensor:
                return self.async_show_form(
                    step_id="edit_room_safety",
                    data_schema=self._room_safety_schema(),
                    errors={"base": "invalid_person_presence"},
                )
            sensors = dict(self._working.get("person_room_presence", {}) or {})
            if use:
                sensors[area] = sensor
            else:
                sensors.pop(area, None)
            self._working["person_room_presence"] = sensors
            return await self._async_finish()
        return self.async_show_form(
            step_id="edit_room_safety", data_schema=self._room_safety_schema(),
        )

    @staticmethod
    def _room_safety_schema() -> probatio.Schema:
        return probatio.Schema({
            probatio.Required("area"): selector.AreaSelector(),
            probatio.Required("verify_presence", default=False):
                selector.BooleanSelector(),
            probatio.Optional("presence_sensor"):
                selector.EntitySelector(selector.EntitySelectorConfig(
                    domain="binary_sensor",
                )),
        })

    async def async_step_edit_audio(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optional room-speaker chime and ducking. Shared Snapcast is excluded."""
        keys = (
            "person_output_chime", "person_chime_url",
            "person_chime_delay", "person_output_ducking", "person_duck_factor",
        )
        if user_input is not None:
            url = str(user_input.get("person_chime_url", "") or "")
            if url and not url.startswith("/local/"):
                return self.async_show_form(
                    step_id="edit_audio", data_schema=self._audio_schema(),
                    errors={"base": "invalid_chime_url"},
                )
            for key in keys:
                self._working[key] = user_input.get(key)
            return await self._async_finish()
        return self.async_show_form(
            step_id="edit_audio", data_schema=self._audio_schema(),
        )

    def _audio_schema(self) -> probatio.Schema:
        return probatio.Schema({
            probatio.Required(
                "person_output_chime",
                default=bool(self._working.get("person_output_chime", False)),
            ): selector.BooleanSelector(),
            probatio.Optional(
                "person_chime_url",
                default=str(self._working.get("person_chime_url", "") or ""),
            ): selector.TextSelector(),
            probatio.Required(
                "person_chime_delay",
                default=float(self._working.get("person_chime_delay", 0.5) or 0),
            ): selector.NumberSelector(selector.NumberSelectorConfig(
                min=0, max=10, step=0.5, mode=selector.NumberSelectorMode.BOX,
            )),
            probatio.Required(
                "person_output_ducking",
                default=bool(self._working.get("person_output_ducking", False)),
            ): selector.BooleanSelector(),
            probatio.Required(
                "person_duck_factor",
                default=float(self._working.get("person_duck_factor", 0.35) or 0.35),
            ): selector.NumberSelector(selector.NumberSelectorConfig(
                min=0.1, max=1, step=0.05, mode=selector.NumberSelectorMode.BOX,
            )),
        })

    async def async_step_edit_advanced_ai(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit only safe prompt style preferences; strict AI JSON rules remain fixed."""
        self._edit_section = "advanced_ai"
        current = self._working.get("ai_prompt_templates", {}) or {}
        if user_input is not None:
            from .ai_filter import custom_style_instruction
            try:
                for key in ("rewrite", "translate", "both"):
                    custom_style_instruction(
                        {key: str(user_input.get(key, "") or "")},
                        mode="rewrite" if key != "translate" else "translate",
                        target_language="el" if key != "rewrite" else None,
                        originals={"text_tts": "test", "text_notify": None},
                    )
            except ValueError:
                return self.async_show_form(
                    step_id="edit_advanced_ai",
                    data_schema=self._ai_prompts_schema(current),
                    errors={"base": "invalid_prompt_template"},
                )
            self._working["ai_prompt_templates"] = {
                key: str(user_input.get(key, "") or "").strip()
                for key in ("rewrite", "translate", "both")
            }
            return await self._async_finish()
        return self.async_show_form(
            step_id="edit_advanced_ai",
            data_schema=self._ai_prompts_schema(current),
        )

    @staticmethod
    def _ai_prompts_schema(current: dict[str, str]) -> probatio.Schema:
        return probatio.Schema({
            probatio.Optional(key, default=str(current.get(key, "") or "")):
                selector.TextSelector(selector.TextSelectorConfig(multiline=True))
            for key in ("rewrite", "translate", "both")
        })

    async def async_step_edit_people(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit tracked people and their room tracking / voice settings."""
        self._edit_section = "people"
        return await self.async_step_people()

    def _person_provider_selector(
        self, domain: str, selected: str | None = None,
    ) -> selector.SelectSelector:
        """Pick by human-readable HA provider name, with a global fallback."""
        options = [selector.SelectOptionDict(
            value="", label="Use global default",
        )]
        if domain == "tts":
            choices = tts_engine_options(self.hass)
        else:
            choices = self._ai_agent_options()
        for entry in choices:
            if str(entry["value"]) not in {item["value"] for item in options}:
                options.append(selector.SelectOptionDict(
                    value=str(entry["value"]), label=str(entry["label"]),
                ))
        if selected and selected not in {str(x["value"]) for x in options}:
            options.append(selector.SelectOptionDict(
                value=str(selected), label=f"Unavailable · {selected}",
            ))
        return selector.SelectSelector(selector.SelectSelectorConfig(
            options=options, mode=selector.SelectSelectorMode.DROPDOWN,
        ))

    async def async_step_people(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose persons; person routing remains opt-in only."""
        available = {
            person.entity_id: person
            for person in self.hass.states.async_all("person")
        }
        profiles = self._working.get(CONF_PERSON_PROFILES, {}) or {}
        if not isinstance(profiles, dict):
            profiles = {}
        selected = [person_id for person_id in profiles if person_id in available]
        if user_input is not None:
            selected = [
                person_id for person_id in user_input.get("tracked_people", [])
                if person_id in available
            ]
            self._working[CONF_PERSON_PROFILES] = {
                person_id: dict(profiles.get(person_id, {})) for person_id in selected
            }
            self._working[CONF_PERSON_GROUP_LANGUAGE] = (
                str(user_input.get(CONF_PERSON_GROUP_LANGUAGE, "") or "").strip()
            )
            self._working[CONF_PERSON_GROUP_VOICE] = (
                str(user_input.get(CONF_PERSON_GROUP_VOICE, "") or "").strip()
            )
            self._working[CONF_PERSON_GROUP_TRANSLATE] = bool(
                user_input.get(CONF_PERSON_GROUP_TRANSLATE, False)
            )
            for key in (CONF_PERSON_GROUP_AGENT, CONF_PERSON_GROUP_TTS_ENGINE,
                        CONF_PERSON_GROUP_ADDRESSEE):
                self._working[key] = str(user_input.get(key, "") or "").strip()
            for key in (CONF_PERSON_GROUP_REWRITE, CONF_PERSON_GROUP_GREETING):
                self._working[key] = bool(user_input.get(key, False))
            self._person_config_ids = selected
            self._person_index = 0
            return await self.async_step_person_profile()
        options = [
            selector.SelectOptionDict(
                value=person_id,
                label=str(state.attributes.get("friendly_name") or person_id),
            )
            for person_id, state in sorted(available.items())
        ]
        schema = probatio.Schema({
            probatio.Optional("tracked_people", default=selected):
                _known_multi_select(options),
            probatio.Optional(
                CONF_PERSON_GROUP_LANGUAGE,
                default=str(self._working.get(CONF_PERSON_GROUP_LANGUAGE) or ""),
            ): selector.TextSelector(),
            probatio.Optional(
                CONF_PERSON_GROUP_VOICE,
                default=str(self._working.get(CONF_PERSON_GROUP_VOICE) or ""),
            ): selector.TextSelector(),
            probatio.Required(
                CONF_PERSON_GROUP_TRANSLATE,
                default=bool(self._working.get(CONF_PERSON_GROUP_TRANSLATE, False)),
            ): selector.BooleanSelector(),
            probatio.Optional(
                CONF_PERSON_GROUP_AGENT,
                default=str(self._working.get(CONF_PERSON_GROUP_AGENT) or ""),
            ): self._person_provider_selector(
                "ai", str(self._working.get(CONF_PERSON_GROUP_AGENT) or "")
            ),
            probatio.Optional(
                CONF_PERSON_GROUP_TTS_ENGINE,
                default=str(self._working.get(CONF_PERSON_GROUP_TTS_ENGINE) or ""),
            ): self._person_provider_selector(
                "tts", str(self._working.get(CONF_PERSON_GROUP_TTS_ENGINE) or "")
            ),
            probatio.Required(
                CONF_PERSON_GROUP_REWRITE,
                default=bool(self._working.get(CONF_PERSON_GROUP_REWRITE, False)),
            ): selector.BooleanSelector(),
            probatio.Optional(
                CONF_PERSON_GROUP_ADDRESSEE,
                default=str(self._working.get(CONF_PERSON_GROUP_ADDRESSEE) or ""),
            ): selector.TextSelector(),
            probatio.Required(
                CONF_PERSON_GROUP_GREETING,
                default=bool(self._working.get(CONF_PERSON_GROUP_GREETING, False)),
            ): selector.BooleanSelector(),
        })
        return self.async_show_form(step_id="people", data_schema=schema)

    async def async_step_person_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a room sensor and optional language/voice per person."""
        if self._person_index >= len(self._person_config_ids):
            return await self._async_finish()
        person_id = self._person_config_ids[self._person_index]
        person = self.hass.states.get(person_id)
        profiles = self._working.get(CONF_PERSON_PROFILES, {}) or {}
        current = dict(profiles.get(person_id, {}))
        if user_input is not None:
            destination_options = {
                "mobile": "destination_mobile",
                "watch": "destination_watch",
                "tablet": "destination_tablet",
                "other": "destination_other",
            }
            permitted = {
                item["value"].removeprefix("entity:")
                for item in notify_output_options(self.hass)
            } | {
                item["value"] for item in tts_media_player_options(self.hass)
            }
            destinations = {}
            for slot, key in destination_options.items():
                values = user_input.get(key, [])
                if any(value not in permitted for value in values):
                    return self.async_show_form(
                        step_id="person_profile",
                        data_schema=self._person_profile_schema(current),
                        errors={"base": "invalid_person_output"},
                        description_placeholders={"person_name": person_id},
                    )
                destinations[slot] = list(dict.fromkeys(values))
            profiles[person_id] = {
                "tracker": str(user_input.get("tracker", "") or "").strip(),
                "language": str(user_input.get("language", "") or "").strip(),
                "voice": str(user_input.get("voice", "") or "").strip(),
                "translate": bool(user_input.get("translate", False)),
                "rewrite": bool(user_input.get("rewrite", False)),
                "ai_agent": str(user_input.get("ai_agent", "") or "").strip(),
                "tts_engine": str(user_input.get("tts_engine", "") or "").strip(),
                "greeting": bool(user_input.get("greeting", False)),
                "address": str(user_input.get("address", "") or "").strip(),
                "enabled": bool(user_input.get("enabled", True)),
                "presence_sensor": str(user_input.get("presence_sensor", "") or "").strip(),
                "verify_presence": bool(user_input.get("verify_presence", False)),
                "ignore_home": bool(user_input.get("ignore_home", False)),
                "destinations": destinations,
            }
            self._working[CONF_PERSON_PROFILES] = profiles
            self._person_index += 1
            return await self.async_step_person_profile()
        schema = self._person_profile_schema(current)
        return self.async_show_form(
            step_id="person_profile",
            data_schema=schema,
            description_placeholders={
                "person_name": (
                    str(person.attributes.get("friendly_name") or person_id)
                    if person else person_id
                )
            },
        )

    def _person_profile_schema(self, current: dict[str, Any]) -> probatio.Schema:
        """Offer only eligible HA outputs as named personal destination slots."""
        available: dict[str, str] = {}
        for item in (*notify_output_options(self.hass), *tts_media_player_options(self.hass)):
            available[item["value"].removeprefix("entity:")] = item["label"]
        choices = [
            selector.SelectOptionDict(value=key, label=label)
            for key, label in sorted(available.items())
        ]
        previous = current.get("destinations") or {}
        if not isinstance(previous, dict):
            previous = {}
        fields: dict[Any, Any] = {
            _optional_marker("tracker", current.get("tracker")):
                selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["sensor", "device_tracker"])
                ),
            probatio.Optional(
                "language", default=current.get("language", "")
            ): selector.TextSelector(),
            probatio.Optional(
                "voice", default=current.get("voice", "")
            ): selector.TextSelector(),
            probatio.Required(
                "translate", default=bool(current.get("translate", False))
            ): selector.BooleanSelector(),
            probatio.Required(
                "ignore_home", default=bool(current.get("ignore_home", False))
            ): selector.BooleanSelector(),
            probatio.Required(
                "enabled", default=bool(current.get("enabled", True))
            ): selector.BooleanSelector(),
            _optional_marker(
                "presence_sensor", current.get("presence_sensor")
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            probatio.Required(
                "verify_presence", default=bool(current.get("verify_presence", False))
            ): selector.BooleanSelector(),
            probatio.Required(
                "rewrite", default=bool(current.get("rewrite", False))
            ): selector.BooleanSelector(),
            probatio.Optional(
                "ai_agent", default=current.get("ai_agent", "")
            ): self._person_provider_selector("ai", current.get("ai_agent")),
            probatio.Optional(
                "tts_engine", default=current.get("tts_engine", "")
            ): self._person_provider_selector("tts", current.get("tts_engine")),
            probatio.Required(
                "greeting", default=bool(current.get("greeting", False))
            ): selector.BooleanSelector(),
            probatio.Optional(
                "address", default=current.get("address", "")
            ): selector.TextSelector(),
        }
        for slot in ("mobile", "watch", "tablet", "other"):
            key = "destination_" + slot
            saved = [v for v in previous.get(slot, []) if v in available]
            fields[probatio.Optional(key, default=saved)] = _known_multi_select(choices)
        return probatio.Schema(fields)


    async def async_step_edit_all(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Provide the existing complete edit wizard if requested."""
        self._edit_section = None
        return await self.async_step_outputs()

    async def async_step_outputs(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: discover and configure notification outputs."""
        options = notify_output_options(self.hass)
        known = [str(item["value"]) for item in options]
        if self._editing_existing:
            # Keep selected outputs even if their entities temporarily vanished.
            # Otherwise opening and saving this page could erase those targets.
            for ref in self._working.get(CONF_NOTIFY_OUTPUTS, []):
                if ref not in known:
                    options.append(
                        selector.SelectOptionDict(value=ref, label=ref)
                    )
                    known.append(ref)
        # First-time setup auto-selects discovered notification outputs.
        # Reconfiguration instead keeps existing selections and opt-outs.
        selected_default = list(known)
        if self._editing_existing:
            # Preserve existing choices instead of silently enabling new devices.
            selected_default = [
                ref for ref in self._working.get(CONF_NOTIFY_OUTPUTS, [])
                if ref in known
            ]

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
                if (
                    records.get(ref) is not None
                    and records[ref].area_id is None
                )
                or (
                    records.get(ref) is None
                    and not (
                        isinstance(policies.get(ref), dict)
                        and policies[ref].get(NOTIFY_POLICY_SCOPE)
                        == NOTIFY_SCOPE_ROOM
                    )
                )
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
                if self._edit_section == "outputs":
                    return await self._async_finish()
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
            if isinstance(profile, dict)
            and (self._editing_existing or domain in domains)
        }
        # Keep profiles for temporarily missing providers when reconfiguring.
        # Only the currently discovered profiles are shown for editing.
        self._notify_profile_index = 0

    async def async_step_notification_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure splitting, read timing, and native provider options."""
        if self._notify_profile_index >= len(self._notify_profile_domains):
            if self._edit_section == "profiles":
                return await self._async_finish()
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
                if integration == INTEGRATION_NFANDROIDTV:
                    selector_value = str(
                        user_input.get(PROFILE_NF_TRANSPARENCY, "")
                    )
                    if selector_value in _NF_TRANSPARENCY_FROM_SELECTOR:
                        user_input = {
                            **user_input,
                            PROFILE_NF_TRANSPARENCY:
                                _NF_TRANSPARENCY_FROM_SELECTOR[selector_value],
                        }
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
                        default=_NF_TRANSPARENCY_TO_SELECTOR.get(
                            str(current[PROFILE_NF_TRANSPARENCY]), "p0"
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(_NF_TRANSPARENCY_TO_SELECTOR.values()),
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
        """Step 2: configure one TTS engine and physical output roles."""
        errors: dict[str, str] = {}

        engine_options = tts_engine_options(self.hass)
        engine_ids = [str(item["value"]) for item in engine_options]
        configured_engine = next(
            (
                value
                for value in self._value(CONF_TTS_ENGINES, [])
                if value in engine_ids
            ),
            None,
        )
        default_engine = tts_default_engine(self.hass)
        engine_default = configured_engine or (
            default_engine if default_engine in engine_ids else None
        )

        language_values = (
            list(tts_engine_languages(self.hass, [engine_default]))
            if engine_default
            else []
        )
        configured_language = str(
            self._value(CONF_TTS_LANGUAGE, DEFAULT_TTS_LANGUAGE) or ""
        )
        if configured_language in language_values:
            language_default = configured_language
        elif engine_default:
            preferred_language = tts_default_language(
                self.hass, [engine_default]
            )
            language_default = (
                preferred_language
                if preferred_language in language_values
                else (language_values[0] if language_values else None)
            )
        else:
            language_default = None

        configured_tts_options = dict(
            self._value(CONF_TTS_OPTIONS, DEFAULT_TTS_OPTIONS) or {}
        )
        voice_supported = tts_engine_supports_voice(
            self.hass, engine_default
        )
        voice_options = tts_engine_voice_options(
            self.hass, engine_default, language_default
        )
        voice_values = {
            str(item["value"]) for item in voice_options
        }
        configured_voice = str(
            configured_tts_options.get("voice", "") or ""
        )
        if configured_voice and (
            not voice_values or configured_voice in voice_values
        ):
            voice_default = configured_voice
        else:
            voice_default = tts_default_voice(
                self.hass, engine_default, language_default
            )

        # Voice gets its own field whenever the engine says it supports one.
        # Keep only the remaining provider-specific options in the object editor.
        additional_tts_options = (
            {
                key: value
                for key, value in configured_tts_options.items()
                if key != "voice"
            }
            if voice_supported
            else configured_tts_options
        )

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
            selected_engine = str(
                user_input.get(CONF_TTS_ENGINES, "") or ""
            )
            engine = (
                selected_engine
                if selected_engine in engine_ids
                else None
            )
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
            submitted_language = str(
                user_input.get(CONF_TTS_LANGUAGE, "") or ""
            )

            # Persist the non-engine controls before a provider refresh so a
            # second render of this same step does not discard user choices.
            self._working[CONF_TTS_ENGINES] = [engine] if engine else []
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
                CONF_DIRECT_TTS_ANNOUNCE,
                CONF_TTS_CACHE,
                CONF_COMPANION_TTS_OUTPUTS,
                CONF_COMPANION_TTS_MEDIA_STREAM,
                CONF_COMPANION_TTS_WPM,
            ):
                if key in user_input:
                    self._working[key] = user_input[key]

            engine_changed = engine != engine_default
            if engine_changed:
                new_languages = (
                    list(tts_engine_languages(self.hass, [engine]))
                    if engine
                    else []
                )
                if submitted_language in new_languages:
                    self._working[CONF_TTS_LANGUAGE] = submitted_language
                else:
                    self._working.pop(CONF_TTS_LANGUAGE, None)
                refreshed_options = dict(additional_tts_options)
                refreshed_options.pop("voice", None)
                self._working[CONF_TTS_OPTIONS] = refreshed_options
                return await self.async_step_tts()

            language_changed = (
                submitted_language
                and submitted_language != (language_default or "")
            )
            if language_changed:
                self._working[CONF_TTS_LANGUAGE] = submitted_language
                refreshed_options = dict(additional_tts_options)
                refreshed_options.pop("voice", None)
                self._working[CONF_TTS_OPTIONS] = refreshed_options
                return await self.async_step_tts()

            if (direct or snapcast) and not engine:
                errors["base"] = "tts_engine_required"
            elif snapcast and not shared_player:
                errors["base"] = "snapcast_tts_path_required"
            elif shared_player and shared_player in direct:
                errors["base"] = "tts_player_role_overlap"
            else:
                if submitted_language:
                    self._working[CONF_TTS_LANGUAGE] = submitted_language
                else:
                    self._working.pop(CONF_TTS_LANGUAGE, None)

                submitted_options = dict(
                    user_input.get(
                        CONF_TTS_OPTIONS, additional_tts_options
                    )
                    or {}
                )
                if voice_supported:
                    selected_voice = str(
                        user_input.get(CONF_TTS_VOICE, "") or ""
                    )
                    if selected_voice and (
                        not voice_values
                        or selected_voice in voice_values
                    ):
                        submitted_options["voice"] = selected_voice
                    else:
                        submitted_options.pop("voice", None)
                self._working[CONF_TTS_OPTIONS] = submitted_options

                if self._edit_section == "tts":
                    return await self._async_finish()
                self._prepare_notify_profile_steps()
                if snapcast:
                    self._notify_profile_domains.append("snapcast")
                return await self.async_step_notification_profile()

        fields: dict[probatio.Marker, Any] = {
            _optional_marker(
                CONF_TTS_ENGINES,
                engine_default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=engine_options,
                    multiple=False,
                    custom_value=False,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
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

        if voice_supported:
            marker = _optional_marker(
                CONF_TTS_VOICE,
                voice_default,
            )
            if voice_options:
                fields[marker] = selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=voice_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            else:
                # Keep voice available for providers that accept the option but
                # cannot enumerate values through Home Assistant.
                fields[marker] = selector.TextSelector()

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
                probatio.Required(
                    CONF_DIRECT_TTS_ANNOUNCE,
                    default=self._value(
                        CONF_DIRECT_TTS_ANNOUNCE, DEFAULT_DIRECT_TTS_ANNOUNCE
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

    def _sleep_rooms_attribute_options(self) -> list[str]:
        """State plus live attributes; retain an existing offline selection."""
        entity = str(self._working.get(CONF_SLEEP_ROOMS_ENTITY, "") or "").strip()
        state = self.hass.states.get(entity) if entity else None
        attributes = sorted(str(key) for key in (state.attributes if state else {}))
        current = str(self._working.get(CONF_SLEEP_ROOMS_ATTRIBUTE, "") or "")
        if current and current not in attributes:
            attributes.append(current)
        return ["state", *attributes]

    def _occupancy_attribute_options(self) -> list[str]:
        """Return State plus live attributes for the selected occupancy entity."""
        sensor = str(self._working.get(CONF_OCCUPANCY_SENSOR, "") or "").strip()
        state = self.hass.states.get(sensor) if sensor else None
        attributes = sorted(str(key) for key in (state.attributes if state else {}))
        return ["state", *attributes]

    async def async_step_occupancy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure occupancy-aware routing and optional fallback."""
        if user_input is not None:
            self._store_step(
                user_input,
                {
                    CONF_OCCUPANCY_SENSOR: None,
                    CONF_SLEEP_ROOMS_ENTITY: None,
                    CONF_FALLBACK_ROOM: None,
                    CONF_FALLBACK_CHECK_DOOR: DEFAULT_FALLBACK_CHECK_DOOR,
                },
            )
            if self._working.get(CONF_OCCUPANCY_SENSOR):
                return await self.async_step_occupancy_source()
            self._working[CONF_OCCUPANCY_ATTRIBUTE] = ""
            return await self.async_step_sleep_rooms()

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
            return await self.async_step_sleep_rooms()

        options = self._occupancy_attribute_options()
        if user_input is not None:
            source = str(user_input.get(CONF_OCCUPANCY_ATTRIBUTE, "state"))
            self._working[CONF_OCCUPANCY_ATTRIBUTE] = (
                "" if source == "state" else source
            )
            return await self.async_step_sleep_rooms()

        current = str(self._working.get(CONF_OCCUPANCY_ATTRIBUTE, "") or "")
        default = current if current in options else "state"
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

    async def async_step_sleep_rooms(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the entity that reports WHERE people are sleeping right now."""
        if user_input is not None:
            entity = str(user_input.get(CONF_SLEEP_ROOMS_ENTITY, "") or "").strip()
            self._working[CONF_SLEEP_ROOMS_ENTITY] = entity or None
            self._working[CONF_SLEEP_ROOMS_ATTRIBUTE] = ""
            self._sleep_source_from_queue = False
            if entity:
                return await self.async_step_sleep_rooms_source()
            return await self.async_step_queue()
        return self.async_show_form(
            step_id="sleep_rooms",
            data_schema=probatio.Schema({
                _optional_marker(
                    CONF_SLEEP_ROOMS_ENTITY,
                    self._value(CONF_SLEEP_ROOMS_ENTITY, None),
                ): selector.EntitySelector(),
            }),
        )

    async def async_step_sleep_rooms_source(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select state or a live list-bearing attribute from the sleep entity."""
        entity = str(self._working.get(CONF_SLEEP_ROOMS_ENTITY, "") or "").strip()
        if not entity:
            self._working[CONF_SLEEP_ROOMS_ATTRIBUTE] = ""
            if self._sleep_source_from_queue:
                self._sleep_source_from_queue = False
                return await self._async_finish()
            return await self.async_step_queue()
        options = self._sleep_rooms_attribute_options()
        errors: dict[str, str] = {}
        if user_input is not None:
            source = str(user_input.get(CONF_SLEEP_ROOMS_ATTRIBUTE, "state"))
            if source in options:
                self._working[CONF_SLEEP_ROOMS_ATTRIBUTE] = (
                    "" if source == "state" else source
                )
                if self._sleep_source_from_queue:
                    self._sleep_source_from_queue = False
                    return await self._async_finish()
                return await self.async_step_queue()
            errors["base"] = "invalid_sleep_source"
        current = str(self._working.get(CONF_SLEEP_ROOMS_ATTRIBUTE, "") or "")
        default = current if current in options else "state"
        schema = probatio.Schema({
            probatio.Required(
                CONF_SLEEP_ROOMS_ATTRIBUTE, default=default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value="state", label=provider_label(self.hass, "state")
                        ),
                        *[
                            selector.SelectOptionDict(value=key, label=key)
                            for key in options if key != "state"
                        ],
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })
        return self.async_show_form(
            step_id="sleep_rooms_source",
            data_schema=schema,
            description_placeholders={"entity": entity},
            errors=errors,
        )

    def _ai_agent_options(self) -> list[selector.SelectOptionDict]:
        """Offer conversation agents and AI Task entities in one selector."""
        preferred_id, _, preferred_error = resolve_preferred_assist_agent(
            self.hass
        )
        if preferred_id:
            preferred_state = self.hass.states.get(preferred_id)
            preferred_name = (
                preferred_state.name if preferred_state else preferred_id
            )
            preferred_label = provider_label(self.hass, "preferred", name=preferred_name)
        elif preferred_error == "preferred_assist_agent_not_generative":
            preferred_label = provider_label(self.hass, "built_in")
        else:
            preferred_label = provider_label(self.hass, "unavailable")
        options = [
            selector.SelectOptionDict(
                value=DEFAULT_AI_AGENT, label=preferred_label
            )
        ]
        seen = {DEFAULT_AI_AGENT}
        for state in sorted(
            self.hass.states.async_all("conversation"),
            key=lambda state: (state.name or state.entity_id).casefold(),
        ):
            if state.entity_id in seen:
                continue
            seen.add(state.entity_id)
            options.append(
                selector.SelectOptionDict(
                    value=state.entity_id,
                    label=state.name or state.entity_id,
                )
            )
        for state in sorted(
            self.hass.states.async_all("ai_task"),
            key=lambda state: (state.name or state.entity_id).casefold(),
        ):
            if state.entity_id in seen:
                continue
            seen.add(state.entity_id)
            options.append(
                selector.SelectOptionDict(
                    value=state.entity_id,
                    label=provider_label(self.hass, "task", name=state.name or state.entity_id),
                )
            )
        # HA also supports agents that are not represented by entities.
        for agent in get_agent_manager(self.hass).async_get_agent_info():
            if agent.id in seen:
                continue
            seen.add(agent.id)
            options.append(
                selector.SelectOptionDict(
                    value=agent.id,
                    label=agent.name or agent.id,
                )
            )
        selected = str(
            self._value(CONF_DEFAULT_AI_AGENT, DEFAULT_AI_AGENT)
            or DEFAULT_AI_AGENT
        )
        if selected not in seen:
            options.append(
                selector.SelectOptionDict(
                    value=selected, label=provider_label(self.hass, "agent_unavailable", name=selected)
                )
            )
        return options

    def _ai_fallback_agent_options(self) -> list[selector.SelectOptionDict]:
        """Offer an original-message fallback or any discovered AI agent."""
        choices = [
            selector.SelectOptionDict(
                value=DEFAULT_FALLBACK_AI_AGENT,
                label=provider_label(self.hass, "original"),
            ),
            *self._ai_agent_options(),
        ]
        configured = str(
            self._value(CONF_FALLBACK_AI_AGENT, DEFAULT_FALLBACK_AI_AGENT)
            or DEFAULT_FALLBACK_AI_AGENT
        )
        if configured not in {choice["value"] for choice in choices}:
            choices.append(
                selector.SelectOptionDict(
                    value=configured,
                    label=provider_label(self.hass, "backup_unavailable", name=configured),
                )
            )
        return choices

    def _sleep_written_recipient_options(
        self,
    ) -> tuple[list[dict[str, str]], list[str]]:
        """Offer configured supported integrations first, then their devices.

        A selected integration expands only to already configured Announcement
        Hub notification outputs. Never re-enable outputs the owner disabled.
        Preserve existing offline selections in the UI without broadening them.
        """
        configured_refs = expand_notify_output_tokens(
            self.hass, list(self._value(CONF_NOTIFY_OUTPUTS, []) or [])
        )
        catalog = resolve_notify_outputs(self.hass, configured_refs)
        labels = {
            str(option["value"]): str(option["label"])
            for option in notify_output_options(self.hass)
        }
        options = sleep_notify_output_options(catalog, labels)
        known = {str(option["value"]) for option in options}
        saved = self._value(CONF_SLEEP_FALLBACK_OUTPUTS, None)
        if saved is None:
            default_mobile = f"{INTEGRATION_TOKEN_PREFIX}{INTEGRATION_MOBILE_APP}"
            selected = [default_mobile] if default_mobile in known else []
        else:
            selected = (
                [saved] if isinstance(saved, str) else list(saved or [])
            )
            for token in selected:
                if token not in known:
                    options.append(
                        selector.SelectOptionDict(
                            value=token, label=f"Unavailable · {token}"
                        )
                    )
                    known.add(token)
        return options, list(dict.fromkeys(selected))

    async def async_step_queue(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 4: general routing, presence, fallback, and queue options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            incoming_sensor = user_input.get(CONF_OCCUPANCY_SENSOR)
            had_source_field = CONF_OCCUPANCY_ATTRIBUTE in user_input
            previous_sleep_entity = str(
                self._working.get(CONF_SLEEP_ROOMS_ENTITY, "") or ""
            ).strip()
            incoming_sleep_entity = str(
                user_input.get(CONF_SLEEP_ROOMS_ENTITY, "") or ""
            ).strip()
            for key, default in (
                (CONF_DEFAULT_TITLE, DEFAULT_TITLE),
                (CONF_DEFAULT_USE_AI, DEFAULT_USE_AI),
                (CONF_DEFAULT_AI_AGENT, DEFAULT_AI_AGENT),
                (CONF_FALLBACK_AI_AGENT, DEFAULT_FALLBACK_AI_AGENT),
                (CONF_CRITICAL_NOTIFY_DATA, {}),
                (CONF_OCCUPANCY_SENSOR, None),
                (CONF_SLEEP_ROOMS_ENTITY, None),
                (CONF_SLEEP_MUTE_TTS, DEFAULT_SLEEP_MUTE_TTS),
                (CONF_SLEEP_FALLBACK_WRITTEN, DEFAULT_SLEEP_FALLBACK_WRITTEN),
                (CONF_FALLBACK_ROOM, None),
                (CONF_FALLBACK_CHECK_DOOR, DEFAULT_FALLBACK_CHECK_DOOR),
                (CONF_FALLBACK_DOOR_LABEL, None),
                (CONF_CHANNEL_FALLBACK_MODE, DEFAULT_CHANNEL_FALLBACK_MODE),
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
                source = str(user_input.get(CONF_OCCUPANCY_ATTRIBUTE, "state"))
                self._working[CONF_OCCUPANCY_ATTRIBUTE] = (
                    "" if source == "state" else source
                )
            else:
                self._working[CONF_OCCUPANCY_ATTRIBUTE] = ""

            if not incoming_sleep_entity or incoming_sleep_entity != previous_sleep_entity:
                self._working[CONF_SLEEP_ROOMS_ATTRIBUTE] = ""
            elif CONF_SLEEP_ROOMS_ATTRIBUTE in user_input:
                sleep_source = str(user_input[CONF_SLEEP_ROOMS_ATTRIBUTE])
                self._working[CONF_SLEEP_ROOMS_ATTRIBUTE] = (
                    "" if sleep_source == "state" else sleep_source
                )

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
            available_options, default_sleep_recipients = (
                self._sleep_written_recipient_options()
            )
            valid_targets = {
                str(option["value"]) for option in available_options
            }
            choices = user_input.get(
                CONF_SLEEP_FALLBACK_OUTPUTS, default_sleep_recipients
            )
            if isinstance(choices, str):
                choices = [choices]
            choices = list(dict.fromkeys(str(item) for item in (choices or [])))
            if any(choice not in valid_targets for choice in choices):
                errors["base"] = "invalid_sleep_fallback_target"
            else:
                self._working[CONF_SLEEP_FALLBACK_OUTPUTS] = choices

            if not (
                self._working.get(CONF_NOTIFY_OUTPUTS)
                or self._working.get(CONF_COMPANION_TTS_OUTPUTS)
                or has_tts
            ):
                errors["base"] = "output_required"
            if not errors:
                if incoming_sleep_entity and incoming_sleep_entity != previous_sleep_entity:
                    self._sleep_source_from_queue = True
                    return await self.async_step_sleep_rooms_source()
                return await self._async_finish()

        sensor = str(self._value(CONF_OCCUPANCY_SENSOR, "") or "").strip()
        sleep_entity = str(self._value(CONF_SLEEP_ROOMS_ENTITY, "") or "").strip()
        fields: dict[probatio.Marker, Any] = {
            probatio.Required(
                CONF_DEFAULT_TITLE,
                default=self._value(CONF_DEFAULT_TITLE, DEFAULT_TITLE),
            ): selector.TextSelector(),
            probatio.Required(
                CONF_DEFAULT_USE_AI,
                default=self._value(CONF_DEFAULT_USE_AI, DEFAULT_USE_AI),
            ): selector.BooleanSelector(),
            probatio.Required(
                CONF_DEFAULT_AI_AGENT,
                default=self._value(CONF_DEFAULT_AI_AGENT, DEFAULT_AI_AGENT),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._ai_agent_options(),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            probatio.Required(
                CONF_FALLBACK_AI_AGENT,
                default=self._value(
                    CONF_FALLBACK_AI_AGENT, DEFAULT_FALLBACK_AI_AGENT
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._ai_fallback_agent_options(),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            probatio.Optional(
                CONF_CRITICAL_NOTIFY_DATA,
                default=self._value(CONF_CRITICAL_NOTIFY_DATA, {}),
            ): selector.ObjectSelector(),
            _optional_marker(
                CONF_OCCUPANCY_SENSOR,
                self._value(CONF_OCCUPANCY_SENSOR, None),
            ): selector.EntitySelector(),
            _optional_marker(
                CONF_SLEEP_ROOMS_ENTITY,
                self._value(CONF_SLEEP_ROOMS_ENTITY, None),
            ): selector.EntitySelector(),
        }

        if sensor:
            state = self.hass.states.get(sensor)
            attributes = sorted(str(key) for key in (state.attributes if state else {}))
            options = [
                selector.SelectOptionDict(value="state", label=provider_label(self.hass, "state")),
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
                    default=current if current in values else "state",
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        if sleep_entity:
            sleep_options = self._sleep_rooms_attribute_options()
            current_sleep_source = str(
                self._value(CONF_SLEEP_ROOMS_ATTRIBUTE, "") or ""
            )
            fields[
                probatio.Required(
                    CONF_SLEEP_ROOMS_ATTRIBUTE,
                    default=(
                        current_sleep_source
                        if current_sleep_source in sleep_options else "state"
                    ),
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value="state", label=provider_label(self.hass, "state")
                        ),
                        *[
                            selector.SelectOptionDict(value=key, label=key)
                            for key in sleep_options if key != "state"
                        ],
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        sleep_target_options, sleep_target_defaults = (
            self._sleep_written_recipient_options()
        )
        fields.update(
            {
                probatio.Required(
                    CONF_SLEEP_MUTE_TTS,
                    default=self._value(
                        CONF_SLEEP_MUTE_TTS, DEFAULT_SLEEP_MUTE_TTS
                    ),
                ): selector.BooleanSelector(),
                probatio.Required(
                    CONF_SLEEP_FALLBACK_WRITTEN,
                    default=self._value(
                        CONF_SLEEP_FALLBACK_WRITTEN,
                        DEFAULT_SLEEP_FALLBACK_WRITTEN,
                    ),
                ): selector.BooleanSelector(),
                probatio.Optional(
                    CONF_SLEEP_FALLBACK_OUTPUTS,
                    default=sleep_target_defaults,
                ): _known_multi_select(sleep_target_options),
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
                    CONF_CHANNEL_FALLBACK_MODE,
                    default=self._value(
                        CONF_CHANNEL_FALLBACK_MODE, DEFAULT_CHANNEL_FALLBACK_MODE
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(CHANNEL_FALLBACK_MODES),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="channel_fallback_mode",
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
        self._editing_existing = False
        self._edit_section = None
        self._notify_route_outputs = []
        self._notify_route_index = 0
        self._notify_profile_domains = []
        self._notify_profile_index = 0
        self._person_config_ids = []
        self._person_index = 0
        self._sleep_source_from_queue = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_outputs()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show navigation choices instead of restarting first-time setup."""
        entry = self._get_reconfigure_entry()
        self._editing_existing = True
        if not self._working:
            self._working = {**entry.data, **entry.options}
        return self.async_show_menu(
            step_id="reconfigure", menu_options=list(EDIT_MENU_OPTIONS)
        )

    async def _async_finish(self) -> ConfigFlowResult:
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            data, options = merge_reconfiguration(
                entry.data, entry.options, self._working
            )
            # Avoid duplicate reloads: manager's entry update listener applies
            # changed settings live (HA 2026.6+ recommends this helper).
            return self.async_update_and_abort(
                entry, data=data, options=options
            )
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
        self._editing_existing = True
        self._edit_section = None
        self._notify_route_outputs = []
        self._notify_route_index = 0
        self._notify_profile_domains = []
        self._notify_profile_index = 0
        self._person_config_ids = []
        self._person_index = 0
        self._sleep_source_from_queue = False

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._working = {
            **self.config_entry.data,
            **self.config_entry.options,
        }
        return self.async_show_menu(
            step_id="init", menu_options=list(EDIT_MENU_OPTIONS)
        )

    async def _async_finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._working)
