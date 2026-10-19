"""Regression checks for common text and optional spoken/visual overrides."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "custom_components" / "announcement_hub"

spec = importlib.util.spec_from_file_location(
    "announcement_hub_common_message_test", C / "message_text.py"
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
resolve_channel_texts = module.resolve_channel_texts


@pytest.mark.parametrize(
    "common,spoken,visual,expected",
    [
        ("Door open", None, None, ("Door open", "Door open")),
        ("Door open", "Please close the front door", None,
         ("Please close the front door", "Door open")),
        ("Door open", None, "🚪 **Door open**",
         ("Door open", "🚪 **Door open**")),
        ("Door open", "Close the entrance", "🚪 Entrance open",
         ("Close the entrance", "🚪 Entrance open")),
        ("  Έχει κίνηση  ", "  Ανιχνεύθηκε κίνηση ", " 🚨 Κίνηση! ",
         ("Ανιχνεύθηκε κίνηση", "🚨 Κίνηση!")),
        ("  Temperature 23°C  ", " ", "  ",
         ("Temperature 23°C", "Temperature 23°C")),
        # Legacy channel-only calls are still valid and do not create a
        # second channel merely because an alternate variant is absent.
        (None, "Existing TTS only", None, ("Existing TTS only", None)),
        (None, None, "Existing notification only",
         (None, "Existing notification only")),
        (None, "Legacy TTS", "Legacy visual", ("Legacy TTS", "Legacy visual")),
        # Without text, empty channel-specific strings remain missing.
        (None, "", "", (None, None)),
        ("   ", None, None, (None, None)),
        ("", " TTS legacy ", "", ("TTS legacy", None)),
    ],
)
def test_independent_channel_override_resolution(
    common: str | None,
    spoken: str | None,
    visual: str | None,
    expected: tuple[str | None, str | None],
) -> None:
    assert resolve_channel_texts(common, spoken, visual) == expected


def test_service_form_requires_primary_text_and_overrides_are_optional() -> None:
    services = yaml.safe_load((C / "services.yaml").read_text(encoding="utf-8"))
    fields = services["send"]["fields"]["content"]["fields"]
    assert list(fields).index("text") < list(fields).index("text_tts")
    assert fields["text"]["required"] is False
    assert fields["text"]["selector"] == {"text": {"multiline": True}}
    assert fields["text_tts"].get("required") is not True
    assert fields["text_notify"].get("required") is not True


def test_legacy_send_schema_keeps_existing_yaml_actions_valid() -> None:
    init = (C / "__init__.py").read_text(encoding="utf-8")
    assert "probatio.Optional(ATTR_TEXT): cv.string" in init
    assert "probatio.Required(ATTR_TEXT)" not in init
    assert "probatio.Optional(ATTR_TEXT_TTS): cv.string" in init
    assert "probatio.Optional(ATTR_TEXT_NOTIFY): cv.string" in init
    assert "resolve_channel_texts(" in init
    assert "text=call.data.get(ATTR_TEXT)" in init
    assert "text_tts=call.data.get(ATTR_TEXT_TTS)" in init
    assert "text_notify=call.data.get(ATTR_TEXT_NOTIFY)" in init
    assert "text is required unless" in init


def test_manager_resolves_common_text_before_routing_and_ai() -> None:
    manager = (C / "manager.py").read_text(encoding="utf-8")
    fn = manager[manager.index("    async def async_enqueue("):]
    resolved = fn.index("text_tts, text_notify = resolve_channel_texts(")
    routed = fn.index("selected = filter_selected_outputs(")
    ai = fn.index("ai_enabled, ai_source = resolve_ai_enabled(")
    frozen = fn.index("job = AnnouncementJob.create(")
    assert resolved < routed < ai < frozen
    assert "text: str | None = None" in manager
    assert "text_tts=text_tts," in manager
    assert "text_notify=text_notify," in manager


def test_new_primary_field_is_localized_for_both_actions() -> None:
    source = json.loads((C / "strings.json").read_text(encoding="utf-8"))
    for file in (
        "strings.json", "translations/en.json",
        "translations/de.json", "translations/el.json",
    ):
        data = json.loads((C / file).read_text(encoding="utf-8"))
        fields = data["services"]["send"]["fields"]
        for field in ("text", "text_tts", "text_notify"):
            assert fields[field]["name"]
            assert fields[field]["description"]
        assert "text" in fields["text"]["description"]
        assert "text" in fields["text_tts"]["description"]
        assert "text" in fields["text_notify"]["description"]
    assert source["services"]["send"]["fields"]["text"]["name"]


def test_user_can_supply_shared_text_to_visual_only_critical_without_tts() -> None:
    example = yaml.safe_load("""
        action: notify.announcement_hub
        data:
          text: Εντοπίστηκε κίνηση
          integration:
            - mobile_app
          service:
            - notification
          level: critical
          click_action: /dashboard-metrics/0
    """)
    assert example["data"]["text"] == "Εντοπίστηκε κίνηση"
    assert example["data"]["integration"] == ["mobile_app"]
    assert example["data"]["service"] == ["notification"]
    assert resolve_channel_texts(
        example["data"]["text"],
        example["data"].get("text_tts"),
        example["data"].get("text_notify"),
    ) == ("Εντοπίστηκε κίνηση", "Εντοπίστηκε κίνηση")
    # Even though both text inputs exist, the strict visual-only planner
    # still removes speech after resolving the selected physical outputs.
    manager = (C / "manager.py").read_text(encoding="utf-8")
    assert "if not strict_tts:" in manager
    assert "route_plan.tts_text = None" in manager
    assert "strict_targets=bool(requested)" in manager
    assert "room_fallback_routing" in manager
