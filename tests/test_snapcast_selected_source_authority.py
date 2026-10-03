"""Selected Snapcast outputs are the authoritative TTS-source membership."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_selected_snapcast_availability_does_not_require_current_stream_name() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("def _snapcast_output_available")
    end=manager.index("def _routable_snapcast_snapshot", start)
    block=manager[start:end]
    assert "is_volume_muted" in block
    assert "_snapcast_source_matches" not in block


def test_selected_clients_bypass_source_filter_in_route_snapshot() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("def _routable_snapcast_snapshot")
    end=manager.index("async def _async_apply_snapcast_route", start)
    block=manager[start:end]
    assert "selected_set = set(selected_clients)" in block
    assert "entity_id not in selected_set" in block
    assert "and not self._snapcast_source_matches(entity_id)" in block


def test_unselected_clients_still_respect_source_restriction() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("def _routable_snapcast_snapshot")
    end=manager.index("async def _async_apply_snapcast_route", start)
    block=manager[start:end]
    assert "_snapcast_source_matches(entity_id)" in block


def test_area_filter_still_selects_room_clients_before_availability() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("routed_snapcast = tuple(")
    block=manager[start:start+800]
    assert "entity_area_id(self.hass, entity_id)" in block
    assert "area_id in effective_areas" in block
