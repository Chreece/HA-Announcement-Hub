"""Run the actual routed_plan closure for explicit output-routing cases.

These tests isolate the nested planner from Home Assistant's runtime using fake
entity availability and registry data, while executing its real production body.
"""

from __future__ import annotations

import ast
import importlib.util
from enum import StrEnum
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
SOURCE = (COMPONENT / "manager.py").read_text(encoding="utf-8")

if "homeassistant.const" not in sys.modules:
    homeassistant = ModuleType("homeassistant")
    homeassistant_const = ModuleType("homeassistant.const")

    class Platform(StrEnum):
        SENSOR = "sensor"

    homeassistant_const.Platform = Platform
    homeassistant.const = homeassistant_const
    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.const"] = homeassistant_const

package = ModuleType("announcement_hub")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("announcement_hub", package)
for name in ("const", "models"):
    full_name = f"announcement_hub.{name}"
    if full_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            full_name, COMPONENT / f"{name}.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        spec.loader.exec_module(module)

from announcement_hub.models import build_delivery_plan, tts_allowed_for_level  # noqa: E402


def _planner(
    *,
    notify_refs: tuple[str, ...],
    notification_areas: dict[str, str | None],
    notification_available: dict[str, bool],
    tts_engines: tuple[str, ...] = ("tts.piper",),
    snapcast_clients: tuple[str, ...] = ("media_player.wohnzimmer_snapcast",),
    player: str | None = "media_player.tts_source",
    level: str = "critical",
    text_tts: str | None = None,
    text_notify: str | None = "Κίνηση στο σπίτι",
    explicit_area_routing: bool = False,
    explicit_targeting: bool = True,
):
    tree = ast.parse(SOURCE)
    klass = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AnnouncementManager"
    )
    outer = next(
        node for node in klass.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_enqueue"
    )
    nested = next(
        node for node in outer.body
        if isinstance(node, ast.FunctionDef) and node.name == "routed_plan"
    )

    class Manager:
        hass = SimpleNamespace()

        @staticmethod
        def _notify_policy(output):
            return ("room" if output.area_id else "general", "debug")

        @staticmethod
        def _tts_player_scope(entity_id):
            return "room"

        @staticmethod
        def _direct_tts_available_now(entity_id, engines):
            return False

        @staticmethod
        def _server_tts_available_now(**kwargs):
            return False

        @staticmethod
        def _level_distance(level, minimum):
            return 0

    namespace = {
        "self": Manager(),
        "base_selected": (
            tts_engines, notify_refs, (), snapcast_clients, (),
        ),
        "all_notify_records": tuple(
            SimpleNamespace(
                ref=ref,
                area_id=notification_areas.get(ref),
                integration=(
                    "mobile_app" if "mobile" in ref
                    else "nfandroidtv" if "tv" in ref else "unknown"
                ),
            )
            for ref in notify_refs
        ),
        "all_companion_records": (),
        "all_room_tts_players": (),
        "player": player,
        "level": level,
        "text_tts": text_tts,
        "text_notify": text_notify,
        "explicit_area_routing": explicit_area_routing,
        "explicit_targeting": explicit_targeting,
        "minimum_tts_level": "debug",
        "LEVEL_CRITICAL": "critical",
        "LEVEL_INFO": "info",
        "LEVEL_PRIORITY": {
            "debug": 0, "info": 1, "success": 1,
            "warning": 2, "error": 3, "critical": 4,
        },
        "DEFAULT_NOTIFY_MIN_LEVEL": "debug",
        "TTS_LEVEL_NEVER": "never",
        "NOTIFY_SCOPE_GENERAL": "general",
        "NOTIFY_SCOPE_ROOM": "room",
        "INTEGRATION_MOBILE_APP": "mobile_app",
        "entity_area_id": lambda hass, entity_id: "wohnzimmer",
        "notify_output_available": (
            lambda hass, output: notification_available.get(output.ref, False)
        ),
        "companion_output_available": lambda hass, output: False,
        "tts_allowed_for_level": tts_allowed_for_level,
        "build_delivery_plan": build_delivery_plan,
    }
    exec(
        compile(
            "from __future__ import annotations\n" + ast.unparse(nested),
            "announcement-hub-real-routed-plan",
            "exec",
        ),
        namespace,
    )
    return namespace["routed_plan"]


def test_explicit_critical_mobile_app_never_selects_tts_even_if_configured():
    planner = _planner(
        notify_refs=("entity:notify.mobile_app_phone",),
        notification_areas={"entity:notify.mobile_app_phone": None},
        notification_available={"entity:notify.mobile_app_phone": True},
        # Simulate the physical set after service=[mobile_app].
        tts_engines=(), snapcast_clients=(),
    )
    selected, _, _, plan, has_fixed, _, _ = planner(
        (), filter_by_area=False, require_room_delivery=False,
    )
    assert selected == (
        (), ("entity:notify.mobile_app_phone",), (), (), (),
    )
    assert plan.notify_outputs == ("entity:notify.mobile_app_phone",)
    assert plan.tts_text is None
    assert plan.snapcast_clients == ()
    assert plan.tts_engines == ()
    assert plan.server_tts_enabled is False
    assert not plan.has_audible_output
    assert plan.has_visual_output
    assert not has_fixed


def test_selected_unavailable_visual_waits_without_tts_substitution():
    planner = _planner(
        notify_refs=("entity:notify.tv",),
        notification_areas={"entity:notify.tv": "wohnzimmer"},
        notification_available={"entity:notify.tv": False},
        tts_engines=(), snapcast_clients=(), player=None,
    )
    selected, _, _, plan, has_fixed, available, selected_room = planner(
        ("wohnzimmer",), filter_by_area=True, require_room_delivery=True,
    )
    assert selected[1] == ("entity:notify.tv",)
    assert not selected[2]
    assert not selected[3]
    assert not plan.has_audible_output
    assert plan.notify_outputs == ("entity:notify.tv",)
    assert plan.has_visual_output
    assert has_fixed and not available and selected_room


def test_explicit_room_excludes_global_unselected_notifications():
    planner = _planner(
        notify_refs=("entity:notify.mobile_app_phone", "entity:notify.tv"),
        notification_areas={
            "entity:notify.mobile_app_phone": None,
            "entity:notify.tv": "wohnzimmer",
        },
        notification_available={
            "entity:notify.mobile_app_phone": True,
            "entity:notify.tv": False,
        },
        tts_engines=(), snapcast_clients=(), player=None,
        explicit_area_routing=True,
    )
    selected, _, _, plan, *_ = planner(
        ("wohnzimmer",), filter_by_area=True, require_room_delivery=True,
    )
    assert selected[1] == ("entity:notify.tv",)
    assert plan.notify_outputs == ("entity:notify.tv",)
    assert plan.has_visual_output
    assert not plan.has_audible_output


def test_noncritical_explicit_visual_uses_spoken_source_in_same_channel():
    planner = _planner(
        notify_refs=("entity:notify.mobile_app_phone",),
        notification_areas={"entity:notify.mobile_app_phone": None},
        notification_available={"entity:notify.mobile_app_phone": False},
        tts_engines=(), snapcast_clients=(), player=None,
        level="info", text_tts="Door open", text_notify=None,
    )
    selected, _, _, plan, *_ = planner((), filter_by_area=False)
    assert selected[1] == ("entity:notify.mobile_app_phone",)
    assert plan.notify_text == "Door open"
    assert plan.tts_text is None
    assert not plan.has_audible_output


def test_explicit_service_and_output_disable_cross_room_fallback():
    assert "explicit_targeting = bool(requested) or explicit_area_routing" in SOURCE
    start = SOURCE.index("        if (\n            not explicit_targeting")
    end = SOURCE.index("        notify_output_areas = {", start)
    fallback = SOURCE[start:end]
    assert "fallback_area_id = self._fallback_area_id()" in fallback
    assert "and not target_room_candidate_exists" in fallback
    strict_start = SOURCE.index("            if explicit_targeting:")
    strict_end = SOURCE.index(
        "            room_candidates = [", strict_start + 35
    )
    strict = SOURCE[strict_start:strict_end]
    assert "route_plan = build_delivery_plan(" in strict
    assert "force_tts=strict_tts" in strict
    assert "force_notify=strict_visual" in strict

def test_action_response_reports_authoritative_strict_target_mode() -> None:
    action = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    assert '"strict_targets": job.strict_targets' in action
    assert "strict_targets=explicit_targeting" in SOURCE

def test_empty_explicit_selector_must_not_become_critical_broadcast() -> None:
    assert "if outputs is not None and not any(" in SOURCE
    assert "if requested_services is not None and not any(" in SOURCE
    assert "Explicit output selector is empty" in SOURCE
    assert "Explicit service selector is empty" in SOURCE
    # These guards must run before the implicit Critical broadcast selector.
    entry = SOURCE.index("    async def async_enqueue(")
    checks = SOURCE.index("if requested_services is not None and not any(", entry)
    selector = SOURCE.index("selected = self._select_requested_outputs(", entry)
    assert checks < selector
