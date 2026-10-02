"""Constants for Announcement Hub."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "announcement_hub"
NAME: Final = "Announcement Hub"
VERSION: Final = "0.3.4"
PLATFORMS: Final = [Platform.SENSOR]

SERVICE_SEND: Final = "send"
SERVICE_CLEAR_QUEUE: Final = "clear_queue"
SERVICE_CANCEL: Final = "cancel"

ATTR_TEXT_TTS: Final = "text_tts"
ATTR_TEXT_NOTIFY: Final = "text_notify"
ATTR_OUTPUT: Final = "output"
ATTR_SERVICE: Final = "service"
ATTR_LEVEL: Final = "level"
ATTR_TITLE: Final = "title"
ATTR_NOTIFY_DATA: Final = "notify_data"
ATTR_LANGUAGE: Final = "language"
ATTR_TTS_OPTIONS: Final = "tts_options"
ATTR_COMPANION_TTS: Final = "companion_tts"
ATTR_JOB_ID: Final = "job_id"
ATTR_INCLUDE_CURRENT: Final = "include_current"

LEVEL_CRITICAL: Final = "critical"
LEVEL_ERROR: Final = "error"
LEVEL_WARNING: Final = "warning"
LEVEL_INFO: Final = "info"
LEVEL_SUCCESS: Final = "success"
LEVEL_DEBUG: Final = "debug"
LEVELS: Final = (
    LEVEL_CRITICAL,
    LEVEL_ERROR,
    LEVEL_WARNING,
    LEVEL_INFO,
    LEVEL_SUCCESS,
    LEVEL_DEBUG,
)
LEVEL_PRIORITY: Final = {
    LEVEL_DEBUG: 0,
    LEVEL_INFO: 1,
    LEVEL_SUCCESS: 1,
    LEVEL_WARNING: 2,
    LEVEL_ERROR: 3,
    LEVEL_CRITICAL: 4,
}
TTS_LEVEL_NEVER: Final = "never"
TTS_MIN_LEVELS: Final = (
    LEVEL_DEBUG,
    LEVEL_INFO,
    LEVEL_WARNING,
    LEVEL_ERROR,
    LEVEL_CRITICAL,
    TTS_LEVEL_NEVER,
)

PROVIDER_TTS_ALIAS: Final = "tts"
PROVIDER_NOTIFY_ALIAS: Final = "notify"
PROVIDER_SNAPCAST_ALIAS: Final = "snapcast"
PROVIDER_COMPANION_TTS_ALIAS: Final = "companion_tts"
PROVIDER_ALL_ALIAS: Final = "all"
TARGET_INTEGRATION_PREFIX: Final = "integration:"
TARGET_ENTRY_PREFIX: Final = "entry:"
TARGET_ENTITY_PREFIX: Final = "entity:"
TARGET_SERVICE_PREFIX: Final = "service:"

# Output-centric configuration. Every selected item is an output; there is no
# allowed/default split. Integration and config-entry selectors are expanded to
# concrete entities/services when a job is queued so the room binding is frozen.
CONF_NOTIFY_OUTPUTS: Final = "notify_outputs"
CONF_SNAPCAST_OUTPUTS: Final = "snapcast_outputs"
CONF_COMPANION_TTS_OUTPUTS: Final = "companion_tts_outputs"
CONF_TTS_ENGINES: Final = "tts_engines"
CONF_TTS_MEDIA_PLAYER: Final = "tts_media_player"
CONF_TTS_CACHE: Final = "tts_cache"
CONF_TTS_LANGUAGE: Final = "tts_language"
CONF_TTS_OPTIONS: Final = "tts_options"
CONF_TTS_MIN_LEVEL: Final = "tts_min_level"
CONF_COMPANION_TTS_MEDIA_STREAM: Final = "companion_tts_media_stream"
CONF_COMPANION_TTS_WPM: Final = "companion_tts_words_per_minute"
CONF_DEFAULT_TITLE: Final = "default_title"
CONF_CRITICAL_NOTIFY_DATA: Final = "critical_notify_data"
CONF_NOTIFY_PROFILES: Final = "notify_profiles"

# Per-integration visual output profile fields. Profiles are keyed by the
# integration domain that owns the concrete notify output.
PROFILE_DEFAULT: Final = "default"
PROFILE_MAX_LENGTH: Final = "max_length"
PROFILE_READING_WPM: Final = "reading_words_per_minute"
PROFILE_MIN_DISPLAY: Final = "minimum_display_seconds"
PROFILE_MAX_DISPLAY: Final = "maximum_display_seconds"
PROFILE_DISPLAY_BUFFER: Final = "display_buffer_seconds"
PROFILE_PART_GAP: Final = "part_gap_seconds"
PROFILE_SHOW_PART_NUMBER: Final = "show_part_number"
PROFILE_INTEGRATION_DATA: Final = "integration_data"
PROFILE_REPLACE_PARTS: Final = "replace_parts"
PROFILE_NF_POSITION: Final = "position"
PROFILE_NF_FONTSIZE: Final = "fontsize"
PROFILE_NF_COLOR: Final = "color"
PROFILE_NF_TRANSPARENCY: Final = "transparency"
PROFILE_NF_INTERRUPT: Final = "interrupt"

INTEGRATION_NFANDROIDTV: Final = "nfandroidtv"
INTEGRATION_MOBILE_APP: Final = "mobile_app"

NFANDROIDTV_POSITIONS: Final = (
    "bottom-right",
    "bottom-left",
    "top-right",
    "top-left",
    "center",
)
NFANDROIDTV_FONTSIZES: Final = ("small", "medium", "large", "max")
NFANDROIDTV_COLORS: Final = (
    "grey",
    "black",
    "indigo",
    "green",
    "red",
    "cyan",
    "teal",
    "amber",
    "pink",
)
NFANDROIDTV_TRANSPARENCIES: Final = ("0%", "25%", "50%", "75%", "100%")

CONF_SNAPCAST_SOURCE: Final = "snapcast_source"
CONF_SNAPCAST_ONLY_SOURCE: Final = "snapcast_only_source"
CONF_SNAPCAST_SETTLE_DELAY: Final = "snapcast_settle_delay"
CONF_SNAPCAST_VERIFY_TIMEOUT: Final = "snapcast_verify_timeout"
CONF_SNAPCAST_RESTORE: Final = "snapcast_restore"

CONF_DISPATCH_ORDER: Final = "dispatch_order"
CONF_QUEUE_MAX: Final = "queue_max"
CONF_OUTPUT_AVAILABILITY_TIMEOUT: Final = "output_availability_timeout"
CONF_IDLE_TIMEOUT: Final = "idle_timeout"
CONF_START_TIMEOUT: Final = "start_timeout"
CONF_PLAYBACK_TIMEOUT: Final = "playback_timeout"
CONF_POST_PLAY_DELAY: Final = "post_play_delay"

DISPATCH_NOTIFY_THEN_TTS: Final = "notify_then_tts"
DISPATCH_TTS_THEN_NOTIFY: Final = "tts_then_notify"
DISPATCH_ORDERS: Final = (
    DISPATCH_NOTIFY_THEN_TTS,
    DISPATCH_TTS_THEN_NOTIFY,
)

COMPANION_STREAM_DEFAULT: Final = "default"
COMPANION_STREAM_MUSIC: Final = "music_stream"
COMPANION_STREAM_ALARM: Final = "alarm_stream"
COMPANION_STREAM_ALARM_MAX: Final = "alarm_stream_max"
COMPANION_STREAMS: Final = (
    COMPANION_STREAM_DEFAULT,
    COMPANION_STREAM_MUSIC,
    COMPANION_STREAM_ALARM,
    COMPANION_STREAM_ALARM_MAX,
)

DEFAULT_TTS_CACHE: Final = True
DEFAULT_TTS_LANGUAGE: Final = ""
DEFAULT_TTS_OPTIONS: Final = {}
DEFAULT_TTS_MIN_LEVEL: Final = LEVEL_DEBUG
DEFAULT_COMPANION_TTS_MEDIA_STREAM: Final = COMPANION_STREAM_DEFAULT
DEFAULT_COMPANION_TTS_WPM: Final = 150
DEFAULT_TITLE: Final = "Notification"
DEFAULT_CRITICAL_NOTIFY_DATA: Final = {}
DEFAULT_NOTIFY_MAX_LENGTH: Final = 0
DEFAULT_NFANDROIDTV_MAX_LENGTH: Final = 193
DEFAULT_MOBILE_APP_MAX_LENGTH: Final = 500
DEFAULT_NOTIFY_READING_WPM: Final = 200
DEFAULT_NOTIFY_MIN_DISPLAY: Final = 3.0
DEFAULT_NOTIFY_MAX_DISPLAY: Final = 30.0
DEFAULT_NOTIFY_DISPLAY_BUFFER: Final = 1.0
DEFAULT_NOTIFY_PART_GAP: Final = 0.15
DEFAULT_NOTIFY_SHOW_PART_NUMBER: Final = True
DEFAULT_NOTIFY_REPLACE_PARTS: Final = True
DEFAULT_NFANDROIDTV_POSITION: Final = "bottom-right"
DEFAULT_NFANDROIDTV_FONTSIZE: Final = "medium"
DEFAULT_NFANDROIDTV_COLOR: Final = "grey"
DEFAULT_NFANDROIDTV_TRANSPARENCY: Final = "25%"
DEFAULT_NFANDROIDTV_INTERRUPT: Final = False
DEFAULT_SNAPCAST_SOURCE: Final = "TTS"
DEFAULT_SNAPCAST_ONLY_SOURCE: Final = True
DEFAULT_SNAPCAST_SETTLE_DELAY: Final = 0.25
DEFAULT_SNAPCAST_VERIFY_TIMEOUT: Final = 5.0
DEFAULT_SNAPCAST_RESTORE: Final = True
DEFAULT_DISPATCH_ORDER: Final = DISPATCH_NOTIFY_THEN_TTS
DEFAULT_QUEUE_MAX: Final = 100
DEFAULT_OUTPUT_AVAILABILITY_TIMEOUT: Final = 5.0
DEFAULT_IDLE_TIMEOUT: Final = 180.0
DEFAULT_START_TIMEOUT: Final = 10.0
DEFAULT_PLAYBACK_TIMEOUT: Final = 300.0
DEFAULT_POST_PLAY_DELAY: Final = 0.15

# Legacy 0.1 keys retained only for config-entry migration.
LEGACY_CONF_ALLOWED_TTS: Final = "allowed_tts_entities"
LEGACY_CONF_DEFAULT_TTS: Final = "default_tts_entities"
LEGACY_CONF_ALLOWED_NOTIFY_ENTITIES: Final = "allowed_notify_entities"
LEGACY_CONF_DEFAULT_NOTIFY_ENTITIES: Final = "default_notify_entities"
LEGACY_CONF_ALLOWED_NOTIFY_SERVICES: Final = "allowed_notify_services"
LEGACY_CONF_DEFAULT_NOTIFY_SERVICES: Final = "default_notify_services"
LEGACY_CONF_SNAPCAST_ENABLED: Final = "snapcast_enabled"
LEGACY_CONF_SNAPCAST_CLIENTS: Final = "snapcast_clients"

STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = f"{DOMAIN}.queue"

EVENT_QUEUED: Final = f"{DOMAIN}_queued"
EVENT_STARTED: Final = f"{DOMAIN}_started"
EVENT_CHANNEL_STARTED: Final = f"{DOMAIN}_channel_started"
EVENT_CHANNEL_FINISHED: Final = f"{DOMAIN}_channel_finished"
EVENT_CHANNEL_FAILED: Final = f"{DOMAIN}_channel_failed"
EVENT_FINISHED: Final = f"{DOMAIN}_finished"
EVENT_FAILED: Final = f"{DOMAIN}_failed"
EVENT_CANCELLED: Final = f"{DOMAIN}_cancelled"
EVENT_QUEUE_CLEARED: Final = f"{DOMAIN}_queue_cleared"

SIGNAL_UPDATE: Final = f"{DOMAIN}_update"
