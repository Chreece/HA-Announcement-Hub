"""Occupied room selection must be independent of general outputs."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_occupied_area_requires_room_delivery() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    call=manager[
        manager.index("occupied_room_candidate_exists"):
        manager.index("if occupancy_filter_active and not occupied_room_candidate_exists")
    ]
    assert "require_room_delivery=occupancy_filter_active" in call


def test_general_outputs_cannot_suppress_nearest_room_level() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("if require_room_delivery:")
    block=manager[start:manager.index("room_delivery_selected = any(", start)]
    assert "room_candidates" in block
    assert "room_available" in block
    assert "room_normal_available" in block
    assert "elif room_available:" in block
    assert "room_distance = min(" in block
    assert "chosen.extend(" in block


def test_same_room_behavior_is_used_for_fallback_room() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert manager.count("require_room_delivery=") >= 2
    assert "require_room_delivery=True" in manager


def test_snapcast_source_filter_remains_strict() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("def _snapcast_output_available")
    end=manager.index("def _routable_snapcast_snapshot", start)
    block=manager[start:end]
    assert "_snapcast_source_matches(entity_id)" in block
