"""Regression contracts for delivery-breaking routing edge cases."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "custom_components" / "announcement_hub"


def test_explicit_action_areas_filter_candidate_planning_without_occupancy() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    block = manager[
        manager.index("requested_output_area_ids = self._resolve_area_ids"):
        manager.index("requested = self._ensure_list", manager.index("requested_output_area_ids = self._resolve_area_ids"))
    ]
    assert "area_filter_active = (" in block
    assert "occupancy_filter_active or bool(requested_output_area_ids)" in block
    assert "filter_by_area=area_filter_active" in manager


def test_empty_occupied_target_is_silent_even_for_general_outputs() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    assert "allow_general_outputs = not (" in manager
    assert "occupancy_filter_active and not output_area_ids" in manager
    assert "allow_general_outputs" in manager[
        manager.index("def routed_plan("):
        manager.index("# Build all physical channel candidates first")
    ]


def test_same_player_cannot_run_direct_and_shared_tts_concurrently() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    flow = (C / "config_flow.py").read_text(encoding="utf-8")
    assert "if entity_id != player" in manager
    assert 'errors["base"] = "tts_player_role_overlap"' in flow
    for relative in (
        "strings.json",
        "translations/en.json",
        "translations/de.json",
        "translations/el.json",
    ):
        import json

        data = json.loads((C / relative).read_text(encoding="utf-8"))
        for section in ("config", "options"):
            assert "tts_player_role_overlap" in data[section]["error"]


def test_snapcast_route_waits_for_buffered_tail_before_restore() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    assert "_SNAPCAST_TAIL_DRAIN_SECONDS = 1.2" in manager
    start = manager.index("async def _async_play_server_round")
    end = manager.index("async def _async_available_tts_engines", start)
    block = manager[start:end]
    assert "hold_route = self._should_hold_snapcast_route(" in block
    assert "if not hold_route:" in block
    assert "drain_delay = max(" in block
    assert "_SNAPCAST_TAIL_DRAIN_SECONDS" in block
    assert "await asyncio.sleep(drain_delay)" in block
    assert "if hold_route:" in block
