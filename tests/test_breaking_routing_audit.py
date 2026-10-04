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
    assert "area_filter_active = (" in block
    assert "occupancy_filter_active or bool(requested_output_area_ids)" in block
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
