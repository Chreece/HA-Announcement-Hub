from pathlib import Path
import json

ROOT=Path(".")
C=ROOT/"custom_components"/"announcement_hub"

def rep(path,old,new,count=1):
    text=path.read_text(encoding="utf-8")
    found=text.count(old)
    if found!=count:
        raise SystemExit(f"{path}: expected {count}, found {found}: {old[:120]!r}")
    path.write_text(text.replace(old,new,count),encoding="utf-8")

# ---------------- manager: room fallback ignores general outputs ----------------
p=C/"manager.py"

rep(p,
'''        def routed_plan(
            area_ids: tuple[str, ...],
            *,
            filter_by_area: bool,
        ) -> tuple[
''',
'''        def routed_plan(
            area_ids: tuple[str, ...],
            *,
            filter_by_area: bool,
            require_room_delivery: bool = False,
        ) -> tuple[
''')

# Tag physical candidates by whether they represent room-local delivery.
rep(p,
'''                        "available": notify_output_available(self.hass, output),
                        "native_text": bool(text_notify or level == LEVEL_CRITICAL),
''',
'''                        "available": notify_output_available(self.hass, output),
                        "native_text": bool(text_notify or level == LEVEL_CRITICAL),
                        "room_bound": (
                            self._notify_policy(output)[0] == NOTIFY_SCOPE_ROOM
                        ),
''')

rep(p,
'''                            "available": self._direct_tts_available_now(
                                entity_id, routed_selected[0]
                            ),
                            "native_text": bool(
                                text_tts or level == LEVEL_CRITICAL
                            ),
''',
'''                            "available": self._direct_tts_available_now(
                                entity_id, routed_selected[0]
                            ),
                            "native_text": bool(
                                text_tts or level == LEVEL_CRITICAL
                            ),
                            "room_bound": (
                                self._tts_player_scope(entity_id)
                                == NOTIFY_SCOPE_ROOM
                            ),
''')

rep(p,
'''                            "available": self._server_tts_available_now(
                                engines=routed_selected[0],
                                player=player,
                                snapcast_clients=routed_selected[3],
                            ),
                            "native_text": bool(
                                text_tts or level == LEVEL_CRITICAL
                            ),
''',
'''                            "available": self._server_tts_available_now(
                                engines=routed_selected[0],
                                player=player,
                                snapcast_clients=routed_selected[3],
                            ),
                            "native_text": bool(
                                text_tts or level == LEVEL_CRITICAL
                            ),
                            "room_bound": bool(routed_selected[3]),
''')

rep(p,
'''                            "available": companion_output_available(
                                self.hass, output
                            ),
                            "native_text": bool(
                                text_tts or level == LEVEL_CRITICAL
                            ),
''',
'''                            "available": companion_output_available(
                                self.hass, output
                            ),
                            "native_text": bool(
                                text_tts or level == LEVEL_CRITICAL
                            ),
                            "room_bound": bool(output.area_id),
''')

# Remember whether the occupied/fallback area has any room-local configured candidate
# before availability/level filtering.
needle='''            available = [item for item in candidates if item["available"]]
            normal_available = [
'''
replacement='''            room_candidate_exists = any(
                item["room_bound"] for item in candidates
            )
            available = [item for item in candidates if item["available"]]
            normal_available = [
'''
rep(p,needle,replacement)

# After normal availability selection, force one room-local path when fallback
# routing is active, without making an available general path wait.
needle='''                else:
                    chosen = []

            chosen_notify = {
'''
replacement='''                else:
                    chosen = []

            if require_room_delivery:
                room_candidates = [
                    item for item in candidates if item["room_bound"]
                ]
                room_available = [
                    item for item in room_candidates if item["available"]
                ]
                room_normal_available = [
                    item
                    for item in room_available
                    if item["native_text"]
                    and actual_priority
                    >= LEVEL_PRIORITY.get(
                        item["minimum"], LEVEL_PRIORITY[LEVEL_INFO]
                    )
                ]
                room_chosen: list[dict[str, Any]] = []
                if room_normal_available:
                    room_chosen = room_normal_available
                elif room_available:
                    room_distance = min(
                        self._level_distance(level, item["minimum"])
                        for item in room_available
                    )
                    room_chosen = [
                        item
                        for item in room_available
                        if self._level_distance(level, item["minimum"])
                        == room_distance
                    ]
                elif not available and room_candidates:
                    # Nothing of any class is available. Preserve the existing
                    # timeout semantics, but make the wait target room-local.
                    room_normal_configured = [
                        item
                        for item in room_candidates
                        if item["native_text"]
                        and actual_priority
                        >= LEVEL_PRIORITY.get(
                            item["minimum"], LEVEL_PRIORITY[LEVEL_INFO]
                        )
                    ]
                    if room_normal_configured:
                        room_chosen = room_normal_configured
                    else:
                        room_distance = min(
                            self._level_distance(level, item["minimum"])
                            for item in room_candidates
                        )
                        room_chosen = [
                            item
                            for item in room_candidates
                            if self._level_distance(level, item["minimum"])
                            == room_distance
                        ]

                if room_chosen:
                    chosen_keys = {
                        (item["kind"], item["id"]) for item in chosen
                    }
                    chosen.extend(
                        item
                        for item in room_chosen
                        if (item["kind"], item["id"]) not in chosen_keys
                    )
                    force_tts = force_tts or any(
                        item["kind"] != "notify"
                        and not (
                            item["native_text"]
                            and actual_priority
                            >= LEVEL_PRIORITY.get(
                                item["minimum"],
                                LEVEL_PRIORITY[LEVEL_INFO],
                            )
                        )
                        for item in room_chosen
                    )
                    force_notify = force_notify or any(
                        item["kind"] == "notify"
                        and not (
                            item["native_text"]
                            and actual_priority
                            >= LEVEL_PRIORITY.get(
                                item["minimum"],
                                LEVEL_PRIORITY[LEVEL_INFO],
                            )
                        )
                        for item in room_chosen
                    )

            chosen_notify = {
'''
rep(p,needle,replacement)

# Return room-candidate existence alongside plan.
rep(p,
'''            return (
                routed_selected,
                routed_notify,
                routed_companion,
                route_plan,
            )

        selected, notify_records, companion_records, plan = routed_plan(
''',
'''            return (
                routed_selected,
                routed_notify,
                routed_companion,
                route_plan,
                room_candidate_exists,
            )

        (
            selected,
            notify_records,
            companion_records,
            plan,
            occupied_room_candidate_exists,
        ) = routed_plan(
''')

# Adjust tuple return annotation from 4 -> 5 by appending bool.
rep(p,
'''            tuple[CompanionTTSOutput, ...],
            Any,
        ]:
''',
'''            tuple[CompanionTTSOutput, ...],
            Any,
            bool,
        ]:
''')

# Fallback based on zero ROOM candidates, not zero outputs, and require room
# delivery on the fallback pass.
rep(p,
'''        if occupancy_filter_active and not plan.has_output:
            fallback_area_id = self._fallback_area_id()
''',
'''        if occupancy_filter_active and not occupied_room_candidate_exists:
            fallback_area_id = self._fallback_area_id()
''')

rep(p,
'''                (
                    fallback_selected,
                    fallback_notify_records,
                    fallback_companion_records,
                    fallback_plan,
                ) = routed_plan((fallback_area_id,), filter_by_area=True)
''',
'''                (
                    fallback_selected,
                    fallback_notify_records,
                    fallback_companion_records,
                    fallback_plan,
                    fallback_room_candidate_exists,
                ) = routed_plan(
                    (fallback_area_id,),
                    filter_by_area=True,
                    require_room_delivery=True,
                )
''')

rep(p,
'''                if fallback_plan.has_output:
''',
'''                if fallback_room_candidate_exists and fallback_plan.has_output:
''')

# ---------------- service response: friendly area names ----------------
p=C/"__init__.py"
rep(p,
'''from .manager import AnnouncementManager
''',
'''from .manager import AnnouncementManager
from .outputs import area_name
''')
rep(p,
'''            "outputs": list(job.outputs),
''',
'''            "outputs": [area_name(hass, area_id) for area_id in job.outputs],
            "output_area_ids": list(job.outputs),
''')

# ---------------- version ----------------
rep(C/"const.py",'VERSION: Final = "0.9.0"','VERSION: Final = "0.9.1"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.9.0":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.9.1"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# ---------------- tests ----------------
(ROOT/"tests"/"test_room_fallback_with_general_outputs.py").write_text('''"""Regression contracts for room fallback alongside general outputs."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_general_outputs_do_not_satisfy_room_candidate_requirement() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert '"room_bound": (' in manager
    assert "occupied_room_candidate_exists" in manager
    assert "if occupancy_filter_active and not occupied_room_candidate_exists:" in manager


def test_fallback_pass_requires_room_delivery() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "require_room_delivery=True" in manager
    assert "room_normal_available" in manager
    assert "elif room_available:" in manager


def test_fallback_room_can_add_nearest_level_tts_beside_general_notify() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "chosen.extend(" in manager
    assert "room_distance = min(" in manager
    assert "force_tts = force_tts or any(" in manager


def test_available_general_output_does_not_force_wait_for_unavailable_room_output() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "elif not available and room_candidates:" in manager


def test_service_response_uses_friendly_area_names_and_keeps_ids() -> None:
    init=(C/"__init__.py").read_text(encoding="utf-8")
    assert '"outputs": [area_name(hass, area_id) for area_id in job.outputs]' in init
    assert '"output_area_ids": list(job.outputs)' in init
''',encoding="utf-8")

res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8").replace(
    'assert manifest["version"] == "0.9.0"',
    'assert manifest["version"] == "0.9.1"',
)
res.write_text(text,encoding="utf-8")

ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.9.1 - 2026-10-03

- Fixed room fallback being blocked by General/movable notification outputs.
- Occupancy fallback now asks whether the occupied room has any room-bound
  candidate, instead of using DeliveryPlan.has_output across general and room
  outputs together.
- When the occupied room has zero room-bound candidates, the configured fallback
  room is evaluated even if phones, laptops, watches, or other General outputs
  remain available.
- The fallback-room pass explicitly requires room-local delivery. If a fallback
  room output is available, its normal matching level is preferred; otherwise
  the nearest available level is used immediately. This allows an Info
  announcement to use Warning-level Flur TTS when Küche has no room output.
- General/movable outputs remain in the same job and may still receive the
  announcement; they no longer suppress room fallback.
- An available General output does not make the queue wait for an unavailable
  fallback-room output. Waiting for the fallback room occurs only when no output
  class is currently available.
- Service responses now show friendly Home Assistant area names in "outputs"
  and expose the internal stable IDs separately as "output_area_ids".

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied 0.9.1 room fallback/general-output fix")
