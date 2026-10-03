"""Contracts for Snapcast area/source routing."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_snapcast_friendly_source_is_resolved_to_stream_identifier() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("def _snapcast_source_matches")
    end=manager.index("def _snapcast_output_available", start)
    block=manager[start:end]
    assert 'current_source = str(state.attributes.get("source") or "")' in block
    assert "streams = group.streams_by_name()" in block
    assert "stream = streams.get(source)" in block
    assert 'getattr(stream, "identifier"' in block
    assert "current_source == stream_id" in block


def test_snapcast_availability_trusts_explicit_selected_source_membership() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("def _snapcast_output_available")
    end=manager.index("def _routable_snapcast_snapshot", start)
    block=manager[start:end]
    assert "_snapcast_source_matches" not in block
    assert "is_volume_muted" in block


def test_snapcast_snapshot_filters_source_only_for_unselected_clients() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("def _routable_snapcast_snapshot")
    end=manager.index("async def _async_apply_snapcast_route", start)
    block=manager[start:end]
    assert "entity_id not in selected_set" in block
    assert "_snapcast_source_matches(entity_id)" in block


def test_area_filter_still_runs_before_source_filter() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    area_filter=manager.index("routed_snapcast = tuple(")
    source_check=manager.index("def _snapcast_source_matches")
    assert area_filter < source_check
    routed=manager[area_filter:area_filter+700]
    assert "entity_area_id(self.hass, entity_id)" in routed
    assert "area_id in effective_areas" in routed
