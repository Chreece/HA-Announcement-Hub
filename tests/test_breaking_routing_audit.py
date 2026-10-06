"""Regression contracts for delivery-breaking routing edge cases."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "custom_components" / "announcement_hub"


def test_explicit_action_areas_filter_candidate_planning_without_occupancy() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    block = manager[
        manager.index("requested_output_area_ids = self._resolve_area_ids"):
        manager.index(
            "requested = self._ensure_list",
            manager.index("requested_output_area_ids = self._resolve_area_ids"),
        )
    ]
    assert "explicit_area_routing = bool(requested_output_area_ids)" in block
    assert "if occupied_only and not explicit_area_routing" in block
    assert "if explicit_area_routing:" in block
    assert "output_area_ids = requested_output_area_ids" in block
    assert "area_filter_active = explicit_area_routing or occupancy_filter_active" in block
    assert "filter_by_area=area_filter_active" in manager


def test_empty_or_unavailable_occupancy_keeps_general_outputs_eligible() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    routed = manager[
        manager.index("def routed_plan("):
        manager.index("# Build all physical channel candidates first")
    ]
    assert "self._notify_policy(output)[0] == NOTIFY_SCOPE_GENERAL" in routed
    assert "self._tts_player_scope(entity_id) == NOTIFY_SCOPE_GENERAL" in routed
    assert "allow_general_outputs" not in routed


def test_same_player_cannot_run_direct_and_shared_tts_concurrently() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    flow = (C / "config_flow.py").read_text(encoding="utf-8")
    assert "if entity_id != player" in manager
    assert 'errors["base"] = "tts_player_role_overlap"' in flow

    import json

    for relative in (
        "strings.json",
        "translations/en.json",
        "translations/de.json",
        "translations/el.json",
    ):
        data = json.loads((C / relative).read_text(encoding="utf-8"))
        for section in ("config", "options"):
            assert "tts_player_role_overlap" in data[section]["error"]


def test_explicit_rooms_override_occupancy_for_room_routing() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    block = manager[
        manager.index("requested_output_area_ids = self._resolve_area_ids"):
        manager.index("requested = self._ensure_list")
    ]
    assert "explicit_area_routing = bool(requested_output_area_ids)" in block
    assert "if occupied_only and not explicit_area_routing" in block
    assert "if explicit_area_routing:" in block
    assert "output_area_ids = requested_output_area_ids" in block
    assert "occupied_set" not in block


def test_tts_targets_are_frozen_even_when_currently_unavailable() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    start = manager.index("# TTS has a stronger availability contract")
    end = manager.index("room_delivery_selected = any(", start)
    block = manager[start:end]
    assert "tts_must_output = bool(" in block
    assert "mandatory_tts = [" in block
    assert '{"room_tts", "server_tts", "companion_tts"}' in block
    assert "chosen.extend(" in block
    assert 'item["available"]' not in block


def test_fallback_requires_zero_fixed_tts_candidates_not_unavailability() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    assert "fixed_tts_candidate_exists = bool(fixed_tts_candidates)" in manager
    assert "and not target_fixed_tts_candidate_exists" in manager
    start = manager.index("target_fixed_tts_candidate_exists")
    fallback = manager[
        start:
        manager.index("notify_output_areas = {", start)
    ]
    assert "target_room_routing_active" in fallback
    assert "_target_fixed_tts_candidate_available" in fallback
    assert "not _target_fixed_tts_candidate_available" not in fallback


def test_fallback_door_rule_uses_current_target_rooms() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    start = manager.index("def _fallback_door_allows")
    end = manager.index("def _occupied_area_ids", start)
    block = manager[start:end]
    assert "target_area_ids" in block
    assert "target_areas" in block
    assert "occupied_area_ids" not in block
    assert "target-area door" in block
