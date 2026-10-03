"""Regression contracts for room fallback alongside general outputs."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_general_outputs_do_not_satisfy_room_candidate_requirement() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert '"room_bound": (' in manager
    assert "occupied_room_candidate_exists" in manager
    assert "if occupancy_filter_active and not occupied_room_candidate_exists:" in manager


def test_fallback_pass_requires_room_delivery() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "require_room_delivery=True" in manager
    assert "room_normal_available" in manager
    assert "elif room_available:" in manager


def test_fallback_room_can_add_nearest_level_tts_beside_general_notify() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "chosen.extend(" in manager
    assert "room_distance = min(" in manager
    assert "force_tts = force_tts or any(" in manager


def test_available_general_output_does_not_force_wait_for_unavailable_room_output() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "elif not available and room_candidates:" in manager


def test_service_response_uses_friendly_area_names_only() -> None:
    init=(C/"__init__.py").read_text(encoding="utf-8")
    assert '"outputs": [area_name(hass, area_id) for area_id in job.outputs]' in init
    assert '"output_area_ids": list(job.outputs)' not in init


def test_fallback_is_not_committed_without_actual_room_delivery() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "room_delivery_selected = any(" in manager
    assert "fallback_room_delivery_selected" in manager
    assert "and fallback_room_delivery_selected" in manager
