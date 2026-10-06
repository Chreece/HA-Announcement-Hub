"""Occupied room selection must be independent of moveable/general outputs."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_occupancy_routing_still_requires_fixed_room_delivery() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    call=manager[
        manager.index("target_fixed_tts_candidate_exists"):
        manager.index("fallback_area_id = self._fallback_area_id()")
    ]
    assert "require_room_delivery=occupancy_filter_active" in call


def test_general_outputs_cannot_suppress_nearest_fixed_room_level() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("if require_room_delivery:")
    block=manager[start:manager.index("room_delivery_selected = any(", start)]
    assert 'item["fixed_room"]' in block
    assert "room_candidates" in block
    assert "room_available" in block
    assert "room_normal_available" in block
    assert "elif room_available:" in block
    assert "room_distance = min(" in block
    assert "chosen.extend(" in block


def test_same_room_level_behavior_is_used_for_tts_fallback_room() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert manager.count("require_room_delivery=") >= 2
    assert "require_room_delivery=True" in manager
    assert "tts_only=True" in manager


def test_snapcast_source_filter_remains_strict() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("def _snapcast_output_available")
    end=manager.index("def _routable_snapcast_snapshot", start)
    block=manager[start:end]
    assert "_snapcast_source_matches(entity_id)" in block
