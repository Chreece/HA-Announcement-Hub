"""Notify integration selectors and provider-specific tap-action contracts."""

from __future__ import annotations

import ast
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from textwrap import dedent
import json

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"

spec = spec_from_file_location(
    "announcement_hub_notify_click_action_test",
    COMPONENT / "notify_click_action.py",
)
assert spec is not None and spec.loader is not None
click = module_from_spec(spec)
spec.loader.exec_module(click)


@pytest.mark.parametrize(
    "link",
    [
        "/lovelace/cameras",
        "https://example.com/home",
        "app://io.homeassistant.companion.android",
        "entityId:binary_sensor.front_door",
    ],
)
def test_mobile_app_receives_both_supported_platform_keys(link: str) -> None:
    before = {"tag": "alert", "priority": "high"}
    result = click.mobile_click_action_data(
        before, click_action=link, integration="mobile_app"
    )
    assert result == {
        **before,
        "clickAction": link,  # Android
        "url": link,  # iOS / macOS
    }
    assert before == {"tag": "alert", "priority": "high"}


@pytest.mark.parametrize(
    "service",
    ["notify.mobile_app_phone", "notify.mobile_app", "notify.mobile_app_pixel_9"],
)
def test_legacy_mobile_services_support_click_action(service: str) -> None:
    result = click.mobile_click_action_data(
        {}, click_action=" /lovelace/door ",
        integration=None, service=service,
    )
    assert result == {
        "clickAction": "/lovelace/door",
        "url": "/lovelace/door",
    }


@pytest.mark.parametrize(
    "integration,service",
    [
        ("nfandroidtv", "notify.living_room_tv"),
        ("nfandroidtv", "notify.mobile_app_not_a_mobile_entry"),
        ("telegram", "notify.telegram"),
        ("persistent_notification", None),
        ("smtp", "notify.mail"),
        (None, "notify.some_unknown_service"),
        (None, None),
    ],
)
def test_click_action_not_sent_to_unsupported_providers(
    integration: str | None, service: str | None
) -> None:
    data = {"duration": 5, "position": "bottom-left"}
    result = click.mobile_click_action_data(
        data,
        click_action="/lovelace/cameras",
        integration=integration,
        service=service,
    )
    assert result == data
    assert "url" not in result
    assert "clickAction" not in result


def test_explicit_click_action_overrides_mobile_notify_data_only() -> None:
    profile = {
        "tag": "alarm", "clickAction": "/old/android", "url": "/old/ios",
        "actions": [{"action": "ACK", "title": "Acknowledge"}],
    }
    android = click.mobile_click_action_data(
        profile, click_action=" /new/door ", integration="mobile_app"
    )
    tv = click.mobile_click_action_data(
        profile, click_action=" /new/door ", integration="nfandroidtv"
    )
    assert android["clickAction"] == android["url"] == "/new/door"
    assert android["tag"] == "alarm"
    assert android["actions"] == profile["actions"]
    assert tv == profile
    assert profile["clickAction"] == "/old/android"
    assert profile["url"] == "/old/ios"


@pytest.mark.parametrize("value", [None, "", "  "])
def test_no_click_action_keeps_original_provider_data(value: str | None) -> None:
    data = {"tag": "keep", "clickAction": "/already"}
    assert click.mobile_click_action_data(
        data, click_action=value, integration="mobile_app"
    ) == data


def _select_requested_outputs():
    """Exercise the actual manager selector in a pure-python test fixture."""
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    block = manager[
        manager.index("    def _select_requested_outputs("):
        manager.index("    def _tts_player_scope(")
    ]
    function = dedent(block)
    code = compile(
        "from __future__ import annotations\n" + function,
        "announcement-manager-selector",
        "exec",
    )
    # The AST is compiled from the real method; the only fakes are the
    # Home Assistant registry expansion functions and the manager's hass.
    mapping = {
        "integration:mobile_app": ("entity:notify.phone",),
        "integration:nfandroidtv": ("entity:notify.tv",),
        "entry:phone-id": ("entity:notify.phone",),
    }
    def expand_notify(_hass, tokens):
        return mapping.get(tokens[0], ())
    namespace = {
        "LEVEL_CRITICAL": "critical",
        "PROVIDER_ALL_ALIAS": "all",
        "PROVIDER_TTS_ALIAS": "tts",
        "PROVIDER_NOTIFY_ALIAS": "notify",
        "PROVIDER_SNAPCAST_ALIAS": "snapcast",
        "PROVIDER_COMPANION_TTS_ALIAS": "companion_tts",
        "TARGET_ENTITY_PREFIX": "entity:",
        "TARGET_ENTRY_PREFIX": "entry:",
        "TARGET_INTEGRATION_PREFIX": "integration:",
        "TARGET_SERVICE_PREFIX": "service:",
        "ServiceValidationError": ValueError,
        "expand_notify_output_tokens": expand_notify,
        "expand_tts_engine_tokens": lambda *_: (),
        "expand_media_player_tokens": lambda *_: (),
        "expand_snapcast_output_tokens": lambda *_: (),
        "expand_companion_tts_tokens": lambda *_: (),
    }
    exec(code, namespace)
    from types import SimpleNamespace
    return namespace["_select_requested_outputs"], SimpleNamespace(hass=object())


@pytest.mark.parametrize(
    "service,expected",
    [
        (["mobile_app"], ("entity:notify.phone",)),
        (["nfandroidtv"], ("entity:notify.tv",)),
        (["integration:mobile_app"], ("entity:notify.phone",)),
        (["entry:phone-id"], ("entity:notify.phone",)),
        (["notify"], ("entity:notify.phone", "entity:notify.tv")),
    ],
)
def test_explicit_service_filters_configured_integrations(
    service: list[str], expected: tuple[str, ...]
) -> None:
    selector, instance = _select_requested_outputs()
    tts, notify, players, snapcast, companion = selector(
        instance, service, level="info",
        tts_engines=["tts.piper"],
        notify_outputs=["entity:notify.phone", "entity:notify.tv"],
        room_tts_players=["media_player.room"],
        snapcast_clients=["media_player.snapcast"],
        companion_entries=["phone-id"], companion_tts=False,
    )
    assert notify == expected
    assert not tts
    assert not players
    assert not snapcast
    assert not companion


def test_companion_tts_alias_only_selects_spoken_companion_app() -> None:
    selector, instance = _select_requested_outputs()
    parts = selector(
        instance, ["companion_tts"], level="info",
        tts_engines=["tts.piper"],
        notify_outputs=["entity:notify.phone", "entity:notify.tv"],
        room_tts_players=[], snapcast_clients=[],
        companion_entries=["phone-id"], companion_tts=False,
    )
    assert parts == ((), (), (), (), ("phone-id",))


def test_critical_preserves_existing_broadcast_safety_policy() -> None:
    selector, instance = _select_requested_outputs()
    parts = selector(
        instance, ["mobile_app"], level="critical",
        tts_engines=["tts.piper"],
        notify_outputs=["entity:notify.phone", "entity:notify.tv"],
        room_tts_players=["media_player.room"], snapcast_clients=["snapcast"],
        companion_entries=["phone-id"], companion_tts=False,
    )
    assert parts == (
        ("tts.piper",),
        ("entity:notify.phone", "entity:notify.tv"),
        ("media_player.room",), ("snapcast",), ("phone-id",),
    )


def test_action_schema_and_provider_wiring_and_translations() -> None:
    service = yaml.safe_load((COMPONENT / "services.yaml").read_text())
    assert "text" in service["send"]["fields"]["content"]["fields"]["click_action"]["selector"]
    init = (COMPONENT / "__init__.py").read_text()
    manager = (COMPONENT / "manager.py").read_text()
    assert "probatio.Optional(ATTR_CLICK_ACTION): cv.string" in init
    assert "click_action=call.data.get(ATTR_CLICK_ACTION)" in init
    assert "click_action=click_action" in manager
    assert "click_action=job.click_action" in manager
    assert "mobile_click_action_data(" in manager
    # Mobile app's grouped target and legacy advanced services receive
    # the prepared provider_data; generic notify.send_message gets no data.
    assert '"notify", "mobile_app", data, blocking=True' in manager
    assert '"notify", "send_message", data, blocking=True' in manager
    for file in ("strings.json", "translations/en.json",
                 "translations/de.json", "translations/el.json"):
        payload = json.loads((COMPONENT / file).read_text(encoding="utf-8"))
        item = payload["services"]["send"]["fields"]["click_action"]
        assert item["name"] and item["description"]


def test_tts_push_never_reads_job_click_action() -> None:
    manager = (COMPONENT / "manager.py").read_text()
    # The only use of queued click_action is within the visual part sender.
    assert manager.count("job.click_action") == 1
    visual = manager[
        manager.index("    async def _async_deliver_notification_part("):
        manager.index("    async def _async_reading_hold("),
    ]
    assert "job.click_action" in visual
