"""Executable regressions for shared Snapcast playback isolation.

All methods under test are extracted from the production AnnouncementManager.
No music player or actual notification is invoked on a real Home Assistant.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "custom_components" / "announcement_hub" / "manager.py").read_text(
    encoding="utf-8"
)
TREE = ast.parse(SRC)
CLASS = next(
    node for node in TREE.body
    if isinstance(node, ast.ClassDef) and node.name == "AnnouncementManager"
)


class HomeAssistantError(Exception):
    pass


NAMESPACE = {
    "asyncio": asyncio,
    "HomeAssistantError": HomeAssistantError,
    "STATE_UNAVAILABLE": "unavailable",
    "STATE_UNKNOWN": "unknown",
    "MEDIA_PLAYER_DOMAIN": "media_player",
    "CONF_START_TIMEOUT": "start_timeout",
    "DEFAULT_START_TIMEOUT": 10.0,
    "CONF_PLAYBACK_TIMEOUT": "playback_timeout",
    "DEFAULT_PLAYBACK_TIMEOUT": 30.0,
    "ATTR_ENTITY_ID": "entity_id",
    "ATTR_MEDIA_CONTENT_ID": "media_content_id",
    "ATTR_MEDIA_CONTENT_TYPE": "media_content_type",
    "ATTR_MEDIA_ANNOUNCE": "announce",
    "MediaType": SimpleNamespace(MUSIC="music"),
    "_SNAPCAST_TAIL_DRAIN_SECONDS": 0.0,
}


def install_method(name):
    method = next(
        n for n in CLASS.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == name
    )
    code = "from __future__ import annotations\n" + ast.unparse(method)
    exec(compile(code, f"AnnouncementManager.{name}", "exec"), NAMESPACE)
    return NAMESPACE[name]


METHODS = {
    name: install_method(name)
    for name in (
        "_server_tts_available_now",
        "_job_has_ready_server_tts",
        "_async_send_server_tts",
        "_async_play_server_round",
        "_async_play_media_source",
        "_assert_snapcast_route_isolated",
        "_async_guard_snapcast_tail",
        "_async_quarantine_snapcast_route",
    )
}


class Services:
    def __init__(self):
        self.calls = []

    async def async_call(self, domain, service, data, **kwargs):
        self.calls.append((domain, service, data, kwargs))


class FakeManager:
    def __init__(self):
        self.settings = {}
        self.hass = SimpleNamespace(services=Services(), states=SimpleNamespace(get=lambda _: None))
        self.route = {
            "media_player.kitchen_snapcast": False,
            "media_player.living_snapcast": True,
            "media_player.bedroom_snapcast": True,
        }
        self.failures = []
        self.stops = []
        self.guard_checks = 0

    def _routable_snapcast_snapshot(self, _selected):
        self.guard_checks += 1
        return dict(self.route)

    def _raise_if_cancelled(self, _job):
        pass

    def _record_channel_failure(self, _job, channel, error):
        self.failures.append((channel, str(error)))

    async def _async_stop_player(self, player):
        self.stops.append(player)

    async def _async_set_mute_states(self, desired):
        self.route.update(desired)

    @staticmethod
    async def _wait_for(predicate, *, timeout, job):
        return predicate()


for name, method in METHODS.items():
    setattr(FakeManager, name, method)


def job(*, recipients=(), server=True):
    return SimpleNamespace(
        job_id="test", tts_text="Someone is at the door.",
        server_tts_enabled=server,
        tts_engines=("tts.piper",),
        tts_media_player="media_player.mpd",
        snapcast_clients=tuple(recipients),
        room_tts_players=(),
        outputs=(), snapcast_client_areas={},
    )


def test_missing_physical_recipients_disable_server_tts_even_when_mpd_is_ready():
    m = FakeManager()
    j = job(recipients=())
    assert not m._server_tts_available_now(
        engines=("tts.piper",), player="media_player.mpd",
        snapcast_clients=()
    )
    assert not m._job_has_ready_server_tts(j)


def test_persisted_no_clients_cannot_play_shared_mpd_and_never_triggers_services():
    m = FakeManager()
    j = job(recipients=())
    asyncio.run(m._async_send_server_tts(j))
    assert m.failures and m.failures[0][0] == "server_tts"
    assert "no authorized Snapcast clients" in m.failures[0][1]
    assert m.hass.services.calls == []
    assert m.stops == []


def test_shared_round_rejects_missing_or_unselected_targets_before_any_media_call():
    m = FakeManager()
    for selected, targets in (
        ((), ()),
        (("media_player.kitchen_snapcast",), ()),
        ((), ("media_player.kitchen_snapcast",)),
        (("media_player.kitchen_snapcast",), ("media_player.living_snapcast",)),
    ):
        with pytest.raises(HomeAssistantError):
            asyncio.run(m._async_play_server_round(
                job(), "media_player.mpd",
                selected_clients=selected,
                target_clients=targets,
            ))
    assert m.hass.services.calls == []


def test_isolated_route_allows_exactly_one_unmuted_recipient():
    m = FakeManager()
    m._assert_snapcast_route_isolated(("media_player.kitchen_snapcast",))
    assert m.guard_checks == 1


@pytest.mark.parametrize("unexpected", [
    "media_player.living_snapcast",
    "media_player.bedroom_snapcast",
])
def test_any_other_snapcast_client_unmuted_fails_closed(unexpected):
    m = FakeManager()
    m.route[unexpected] = False
    with pytest.raises(HomeAssistantError, match="other Snapcast clients"):
        m._assert_snapcast_route_isolated(("media_player.kitchen_snapcast",))


def test_selected_recipient_muted_or_missing_causes_guard_failure():
    m = FakeManager()
    m.route["media_player.kitchen_snapcast"] = True
    with pytest.raises(HomeAssistantError, match="lost audible"):
        m._assert_snapcast_route_isolated(("media_player.kitchen_snapcast",))
    m.route.pop("media_player.kitchen_snapcast")
    with pytest.raises(HomeAssistantError, match="lost selected"):
        m._assert_snapcast_route_isolated(("media_player.kitchen_snapcast",))


def test_no_route_guard_may_be_bypassed_by_empty_shared_player_targets():
    m = FakeManager()
    with pytest.raises(HomeAssistantError, match="no physical Snapcast"):
        m._assert_snapcast_route_isolated(())


def test_shared_media_tts_plays_without_provider_side_announce_chime():
    m = FakeManager()
    j = job(recipients=("media_player.kitchen_snapcast",))
    async def harmless_wait(predicate, *, timeout, job):
        predicate()  # Verifies the full route before each phase.
        return True
    m._wait_for = harmless_wait
    asyncio.run(m._async_play_media_source(
        j, "media_player.mpd", "media-source://tts/test",
        ("media_player.kitchen_snapcast",),
    ))
    assert len(m.hass.services.calls) == 1
    domain, action, data, kwargs = m.hass.services.calls[0]
    assert (domain, action) == ("media_player", "play_media")
    assert data["entity_id"] == "media_player.mpd"
    assert "announce" not in data
    assert m.guard_checks >= 3


def test_direct_room_tts_still_uses_announce_semantics_and_no_snapcast_route():
    m = FakeManager()
    j = job(recipients=(), server=False)
    async def harmless_wait(predicate, *, timeout, job):
        return True
    m._wait_for = harmless_wait
    asyncio.run(m._async_play_media_source(
        j, "media_player.kitchen_speaker", "media-source://tts/test", (),
    ))
    assert m.hass.services.calls[0][2]["announce"] is True
    assert m.guard_checks == 0


def test_no_recipient_shared_play_media_fails_before_service_dispatch():
    m = FakeManager()
    with pytest.raises(HomeAssistantError, match="no physical Snapcast"):
        asyncio.run(m._async_play_media_source(
            job(), "media_player.mpd", "media-source://tts/test", (),
        ))
    assert not m.hass.services.calls


def test_muting_route_drift_during_playback_halts_the_source_round():
    m = FakeManager()
    j = job(recipients=("media_player.kitchen_snapcast",))
    counter = 0
    async def concurrent_controller(predicate, *, timeout, job):
        nonlocal counter
        counter += 1
        if counter == 2:
            # Simulates the user's separate Volumes automation unmuting
            # the bedroom while shared MPD is playing for Kitchen.
            m.route["media_player.bedroom_snapcast"] = False
        return predicate()
    m._wait_for = concurrent_controller
    with pytest.raises(HomeAssistantError, match="other Snapcast clients"):
        asyncio.run(m._async_play_media_source(
            j, "media_player.mpd", "media-source://tts/test",
            ("media_player.kitchen_snapcast",),
        ))
    assert len(m.hass.services.calls) == 1
    assert counter == 2


def test_tail_drift_quarantines_unexpected_clients_before_restore():
    m = FakeManager()
    m.route["media_player.living_snapcast"] = False
    j = job(recipients=("media_player.kitchen_snapcast",))
    with pytest.raises(HomeAssistantError):
        asyncio.run(m._async_guard_snapcast_tail(
            j, "media_player.mpd",
            ("media_player.kitchen_snapcast",), 0.2,
        ))
    assert m.stops == ["media_player.mpd"]
    assert m.route["media_player.living_snapcast"] is True
    assert m.route["media_player.bedroom_snapcast"] is True
    assert m.route["media_player.kitchen_snapcast"] is False


def test_stored_legacy_job_cannot_expand_missing_route_into_all_configured_snapcast_clients():
    assert 'job.server_tts_enabled = False' in SRC
    assert 'disabled unsafe shared TTS playback' in SRC
    assert 'job.snapcast_clients = current_snapcast' not in SRC


def test_planner_requires_physical_snapcast_recipients_for_shared_player():
    assert "player and routed_selected[0] and routed_selected[3]" in SRC
    server = SRC[SRC.index("    async def _async_send_server_tts("):
                 SRC.index("    async def _async_play_server_round(")]
    assert "selected_clients=(), target_clients=()" not in server
    assert "if not job.snapcast_clients:" in server
