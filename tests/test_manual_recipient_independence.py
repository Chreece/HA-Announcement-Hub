"""Regression protection: manual dashboard recipients bypass output defaults.

A manual room must never inherit an unselected general phone/other room
even if the integration's configured output set is empty.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "custom_components" / "announcement_hub"
SOURCE = (C / "manager.py").read_text(encoding="utf-8")


def test_manual_output_pool_selects_live_endpoints_not_configured_allow_list():
    manager = next(
        node for node in ast.parse(SOURCE).body
        if isinstance(node, ast.ClassDef) and node.name == "AnnouncementManager"
    )
    fn = next(
        node for node in manager.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_manual_output_catalog"
    )
    isolated = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            fn,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(isolated)

    areas = {
        "notify.kitchen": "kitchen",
        "notify.phone": None,
        "media_player.kitchen": "kitchen",
        "media_player.bedroom": "bedroom",
        "media_player.snap_kitchen": "kitchen",
        "media_player.snap_bedroom": "bedroom",
    }
    env = {
        "TARGET_ENTITY_PREFIX": "entity:",
        "TARGET_ENTRY_PREFIX": "entry:",
        "CONF_TTS_MEDIA_PLAYER": "tts_media_player",
        "entity_area_id": lambda hass, entity_id: areas.get(entity_id),
        "notify_output_options": lambda hass: [
            {"value": "entity:notify.kitchen"},
            {"value": "entity:notify.phone"},
        ],
        "tts_media_player_options": lambda hass: [
            {"value": "media_player.kitchen"},
            {"value": "media_player.bedroom"},
        ],
        "snapcast_output_options": lambda hass: [
            {"value": "entity:media_player.snap_kitchen"},
            {"value": "entity:media_player.snap_bedroom"},
        ],
        "expand_snapcast_output_tokens": lambda hass, tokens: tuple(
            t.removeprefix("entity:") for t in tokens
        ),
        "companion_tts_output_options": lambda hass: [
            {"value": "entry:phone-1"},
        ],
        "expand_companion_tts_tokens": lambda hass, tokens: tuple(
            t.removeprefix("entry:") for t in tokens
        ),
        "resolve_companion_tts_outputs": lambda hass, entries: [
            SimpleNamespace(entry_id="phone-1", area_id=None)
        ],
        "tts_default_engine": lambda hass: "tts.default",
    }
    exec(compile(isolated, "<manual catalogue>", "exec"), env)
    fake = SimpleNamespace(
        hass=object(),
        settings={"tts_media_player": None},
        _configured_outputs=lambda: ((), (), (), (), ()),
        _ensure_list=lambda value: [] if value is None else [value],
    )
    build = env["_manual_output_catalog"]
    all_outputs = build(fake)
    assert "entity:notify.phone" in all_outputs[1]
    assert "media_player.bedroom" in all_outputs[2]
    assert "phone-1" in all_outputs[4]
    assert all_outputs[0] == ("tts.default",)
    exact_room = build(fake, ("kitchen",))
    assert exact_room[1] == ("entity:notify.kitchen",)
    assert exact_room[2] == ("media_player.kitchen",)
    assert exact_room[3] == ("media_player.snap_kitchen",)
    assert exact_room[4] == ()


def test_manual_and_person_routing_cannot_become_global_without_targets():
    source = SOURCE
    service = (C / "__init__.py").read_text(encoding="utf-8")
    card = (C / "frontend" / "announcement-hub-card.js").read_text(encoding="utf-8")
    assert "Manual targets require an explicit area, integration, device or entity" in source
    assert "self._manual_output_catalog(job.preferred_areas)" in source
    assert "manual_targets=manual_targets" in source
    assert "if job_manual else self._notify_policy(output)" in source
    assert "ATTR_MANUAL_TARGETS" in service
    assert 'payload.manual_targets = true' in card
    assert 'if (this._targetMode === "targeted") payload.manual_targets = true;' in card
    assert 'if (call.data.get(ATTR_MANUAL_TARGETS) or any(' in service
    assert "and not _person_targeted" in source
    assert "job.manual_targets" in source
