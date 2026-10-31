"""Execute real person authorization and direct-audio cleanup methods."""

from __future__ import annotations

import ast
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub"


def runtime_methods():
    source = (COMPONENT / "manager.py").read_text()
    klass = next(node for node in ast.parse(source).body
                 if isinstance(node, ast.ClassDef)
                 and node.name == "AnnouncementManager")
    methods = ("_person_authorized_now", "_async_duck_direct_player",
               "_async_restore_volume", "_async_optional_direct_chime")
    nodes = [node for node in klass.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and node.name in methods]
    assert len(nodes) == len(methods)
    tree = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")]),
        *nodes,
    ], type_ignores=[])
    ast.fix_missing_locations(tree)
    spec = importlib.util.spec_from_file_location(
        "person_runtime_helpers", COMPONENT / "person_delivery.py"
    )
    assert spec and spec.loader
    people = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(people)
    env = {
        "person_is_enabled": people.person_is_enabled,
        "presence_confirmed": people.presence_confirmed,
        "MEDIA_PLAYER_DOMAIN": "media_player",
        "CONF_DIRECT_TTS_ANNOUNCE": "direct_tts_announce",
        "DEFAULT_DIRECT_TTS_ANNOUNCE": True,
        "ATTR_ENTITY_ID": "entity_id",
        "ATTR_MEDIA_CONTENT_ID": "media_content_id",
        "ATTR_MEDIA_CONTENT_TYPE": "media_content_type",
        "ATTR_MEDIA_ANNOUNCE": "announce",
        "MediaType": SimpleNamespace(MUSIC="music"),
        "_LOGGER": SimpleNamespace(warning=lambda *a, **k: None),
        "asyncio": asyncio,
    }
    exec(compile(tree, "manager methods", "exec"), env)
    return env


def test_person_room_enable_and_presence_fail_closed():
    methods = runtime_methods()
    states = {
        "binary_sensor.room": SimpleNamespace(state="on"),
        "binary_sensor.person": SimpleNamespace(state="on"),
    }
    settings = {
        "person_profiles": {"person.a": {"enabled": True}},
        "person_area_enabled": {"kitchen": True},
        "person_room_presence": {"kitchen": "binary_sensor.room"},
    }
    fake = SimpleNamespace(
        settings=settings, hass=SimpleNamespace(states=SimpleNamespace(get=states.get))
    )
    job = SimpleNamespace(
        person_ids=("person.a",), preferred_areas=("kitchen",),
        presence_sensors=("binary_sensor.person",),
    )
    permit = methods["_person_authorized_now"]
    assert permit(fake, job)
    states["binary_sensor.room"].state = "unavailable"
    assert not permit(fake, job)
    states["binary_sensor.room"].state = "on"
    settings["person_profiles"]["person.a"]["enabled"] = False
    assert not permit(fake, job)
    settings["person_profiles"]["person.a"]["enabled"] = True
    settings["person_area_enabled"]["kitchen"] = False
    assert not permit(fake, job)


def test_volume_ducking_is_scoped_persisted_and_restored():
    methods = runtime_methods()
    service_calls = []
    state = SimpleNamespace(state="playing", attributes={"volume_level": 0.5})
    class Services:
        async def async_call(self, domain, action, payload, **kwargs):
            service_calls.append((domain, action, dict(payload)))
            if action == "volume_set":
                state.attributes["volume_level"] = payload["volume_level"]
    class Store:
        async def async_save(self, payload):
            assert "volume_restore" in payload
    fake = SimpleNamespace(
        hass=SimpleNamespace(
            states=SimpleNamespace(get=lambda _: state),
            services=Services(),
        ),
        settings={
            "person_output_ducking": True,
            "person_duck_factor": 0.35,
            "direct_tts_announce": True,
        },
        _volume_restore={},
        _save_lock=asyncio.Lock(),
        _store=Store(),
        _serialize=lambda: {"volume_restore": fake._volume_restore.copy()},
        _schedule_save=lambda: None,
    )
    job = SimpleNamespace(tts_media_player="media_player.shared")
    assert asyncio.run(methods["_async_duck_direct_player"](
        fake, job, "media_player.kitchen"
    ))
    assert state.attributes["volume_level"] == 0.175
    assert fake._volume_restore["media_player.kitchen"]["original"] == 0.5
    asyncio.run(methods["_async_restore_volume"](fake, "media_player.kitchen"))
    assert state.attributes["volume_level"] == 0.5
    assert not fake._volume_restore
    # Other/unselected outputs were never touched.
    assert all(x[2]["entity_id"] == "media_player.kitchen" for x in service_calls)
    # A shared Snapcast source is never ducked.
    assert not asyncio.run(methods["_async_duck_direct_player"](
        fake, job, "media_player.shared"
    ))


def test_optional_chime_never_routes_to_shared_snapcast():
    methods = runtime_methods()
    service_calls = []
    class Services:
        async def async_call(self, domain, action, payload, **kwargs):
            service_calls.append((domain, action, payload))
    async def wait_for(*args, **kwargs):
        return True
    fake = SimpleNamespace(
        settings={
            "person_output_chime": True,
            "person_chime_url": "/local/announcement.wav",
            "person_chime_delay": 0.5,
        },
        hass=SimpleNamespace(services=Services()),
        _raise_if_cancelled=lambda job: None,
        _all_occupied_rooms_sleeping=lambda: False,
        _sleep_tts_muted_now=lambda: False,
        _assert_live_room_route=lambda job, areas: None,
        _is_player_busy=lambda player: False,
        _wait_for=wait_for,
        _async_reading_hold=wait_for,
        _hub_playing_players_by_job={},
    )
    job = SimpleNamespace(job_id="chime", pre_announce_sound=None,
                          tts_media_player="media_player.shared", person_ids=())
    chime = methods["_async_optional_direct_chime"]
    asyncio.run(chime(fake, job, "media_player.shared"))
    assert not service_calls
    asyncio.run(chime(fake, job, "media_player.kitchen"))
    assert len(service_calls) == 1
    assert service_calls[0][2]["entity_id"] == "media_player.kitchen"
    assert service_calls[0][2]["media_content_id"] == "/local/announcement.wav"


def test_area_mute_applies_to_non_person_explicit_and_automatic_room_jobs():
    methods = runtime_methods()
    settings = {
        "person_profiles": {},
        "person_area_enabled": {"kitchen": False},
        "person_room_presence": {},
    }
    fake = SimpleNamespace(
        settings=settings,
        hass=SimpleNamespace(states=SimpleNamespace(get=lambda _: None)),
    )
    job = SimpleNamespace(
        person_ids=(), outputs=("kitchen",), preferred_areas=(),
        presence_sensors=(),
    )
    assert not methods["_person_authorized_now"](fake, job)
    job.outputs = ("bedroom",)
    assert methods["_person_authorized_now"](fake, job)
    job.outputs = ("bedroom", "kitchen")
    assert not methods["_person_authorized_now"](fake, job)
