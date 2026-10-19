"""Regression contracts for delivery-breaking routing edge cases."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "custom_components" / "announcement_hub"



def test_area_preference_alone_owns_room_escalation():
    manager = (C / "manager.py").read_text(encoding="utf-8")
    assert "requested_output_area_ids = self._resolve_area_ids(area_tokens)" in manager
    assert "room_fallback_routing = bool(" in manager
    assert "area_filter_active = explicit_area_routing or occupancy_filter_active" in manager
    assert "self._staged_areas(job, stage)" in manager
    assert "filter_by_area=area_filter_active" in manager

def test_empty_or_unavailable_occupancy_keeps_general_outputs_eligible() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    routed = manager[
        manager.index("def routed_plan("):
        manager.index("# Build all physical channel candidates first")
    ]
    assert "not explicit_area_routing" in routed
    assert "== NOTIFY_SCOPE_GENERAL" in routed
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



def test_explicit_recipients_ignore_occupancy_restrictions():
    manager = (C / "manager.py").read_text(encoding="utf-8")
    assert "if occupied_only and not explicit_area_routing and not requested" in manager
    assert "explicit_targeting = bool(requested) or bool(channel_tokens)" in manager
    assert "room_fallback_routing = bool(" in manager
    assert "requested = tuple(dict.fromkeys((" in manager
    assert "self._explicit_recipient_tokens(" in manager


def test_room_recipient_union_has_two_jobs_and_separate_physical_targets():
    manager = (C / "manager.py").read_text(encoding="utf-8")
    assert "if explicit_area_routing and requested and not _fanout:" in manager
    assert "related_job_ids = (explicit_job.job_id,)" in manager
    assert "_group_token=group_token" in manager
    assert "job.group_id = _group_token" in manager
    assert "_group_token=group_token" in manager
    assert "_excluded_physical=physical_keys(static)" not in manager

def test_tts_targets_are_frozen_even_when_currently_unavailable() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    start = manager.index("# TTS follows the same room-level selection")
    end = manager.index("room_delivery_selected = any(", start)
    block = manager[start:end]
    assert "tts_must_output = bool(" in block
    assert "tts_candidates" in block
    assert "tts_normally_allowed or force_tts" in block
    assert "chosen.extend(" in block


def test_fallback_requires_zero_fixed_room_candidates_not_unavailability() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    assert "room_candidate_exists = bool(room_candidates)" in manager
    assert "and not target_room_candidate_exists" in manager
    start = manager.index("target_room_candidate_exists")
    fallback = manager[
        start:
        manager.index("notify_output_areas = {", start)
    ]
    assert "target_room_routing_active" in fallback
    assert "_target_room_candidate_available" in fallback
    assert "not _target_room_candidate_available" not in fallback


def test_fallback_door_rule_uses_current_target_rooms() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    start = manager.index("def _fallback_door_allows")
    end = manager.index("def _occupied_area_ids", start)
    block = manager[start:end]
    assert "target_area_ids" in block
    assert "target_areas" in block
    assert "occupied_area_ids" not in block
    assert "target-area door" in block
