"""UI contracts for notification discovery setup."""

from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_all_recognised_notify_outputs_are_preselected() -> None:
    flow=(C/"config_flow.py").read_text(encoding="utf-8")
    block=flow[
        flow.index("async def async_step_outputs"):
        flow.index("def _prepare_notify_profile_steps")
    ]
    assert "selected_default = list(known)" in block
    assert "default=selected_default" in block


def test_notification_group_labels_are_translated_in_all_locales() -> None:
    required={
        "notify_outputs",
        "notify_room_outputs",
        "notify_info_outputs",
        "notify_warning_outputs",
        "notify_error_outputs",
        "notify_critical_outputs",
    }
    for relative in (
        "strings.json",
        "translations/en.json",
        "translations/de.json",
        "translations/el.json",
    ):
        data=json.loads((C/relative).read_text(encoding="utf-8"))
        for section in ("config","options"):
            labels=data[section]["step"]["outputs"]["data"]
            assert required <= set(labels)
            for key in required:
                assert labels[key]
                assert labels[key] != key


def test_obsolete_per_output_substep_is_removed() -> None:
    flow=(C/"config_flow.py").read_text(encoding="utf-8")
    assert "async_step_notification_routing" not in flow
    assert "_prepare_notify_routing_steps" not in flow
