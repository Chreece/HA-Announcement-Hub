"""Regression contracts for fixed-room fallback alongside moveable/general outputs."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_moveable_outputs_do_not_satisfy_fixed_tts_candidate_requirement() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert '"fixed_room": (' in manager
    assert "output.integration != INTEGRATION_MOBILE_APP" in manager
    assert '"fixed_room": False' in manager
    assert "fixed_tts_candidates" in manager
    assert 'item["kind"] in {"room_tts", "server_tts"}' in manager
    assert "and not target_fixed_tts_candidate_exists" in manager


def test_fixed_room_selection_waits_for_unavailable_room_candidate() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "require_room_delivery=True" in manager
    assert "room_normal_available" in manager
    assert "elif room_available:" in manager
    assert "elif room_candidates:" in manager
    assert "moveable/general output is immediately usable" in manager


def test_fallback_is_tts_only_and_preserves_original_visual_outputs() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "tts_only=True" in manager
    assert "routed_notify = ()" in manager
    assert "routed_companion = ()" in manager
    assert "selected[1]," in manager
    assert "fallback_selected[2]," in manager
    assert "fallback_selected[3]," in manager
    assert "fallback_plan.has_audible_output" in manager


def test_fallback_room_can_relax_level_for_tts() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "room_distance = min(" in manager
    assert "force_tts = force_tts or any(" in manager
    assert "force_tts=fallback_plan.tts_text is not None" in manager


def test_service_response_uses_friendly_area_names_only() -> None:
    init=(C/"__init__.py").read_text(encoding="utf-8")
    assert '"outputs": [area_name(hass, area_id) for area_id in job.outputs]' in init
    assert '"output_area_ids": list(job.outputs)' not in init


def test_fallback_is_not_committed_without_actual_tts_room_delivery() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "room_delivery_selected = any(" in manager
    assert "fallback_room_delivery_selected" in manager
    assert "and fallback_room_delivery_selected" in manager
    assert "and fallback_plan.has_audible_output" in manager
