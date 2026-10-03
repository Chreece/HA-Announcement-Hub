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

p=C/"manager.py"

# Revert the speculative 0.9.4 source bypass. Explicit TTS Snapcast clients
# still must match the configured TTS source.
rep(p,
'''    def _snapcast_output_available(self, entity_id: str) -> bool:
        """Return whether an explicitly selected TTS Snapcast client is usable."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {
            STATE_OFF,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        }:
            return False
        return state.attributes.get("is_volume_muted") is not None
''',
'''    def _snapcast_output_available(self, entity_id: str) -> bool:
        """Return whether a client can be routed on the configured TTS source."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {
            STATE_OFF,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        }:
            return False
        if state.attributes.get("is_volume_muted") is None:
            return False
        return self._snapcast_source_matches(entity_id)
''')

rep(p,
'''        selected_set = set(selected_clients)
        route_scope = tuple(
            dict.fromkeys((*selected_clients, *all_snapcast_clients))
        )
        snapshot: dict[str, bool] = {}
        for entity_id in route_scope:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in {
                STATE_OFF,
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            }:
                continue
            muted = state.attributes.get("is_volume_muted")
            if muted is None:
                continue
            if (
                entity_id not in selected_set
                and not self._snapcast_source_matches(entity_id)
            ):
                continue
            snapshot[entity_id] = bool(muted)
''',
'''        route_scope = tuple(
            dict.fromkeys((*selected_clients, *all_snapcast_clients))
        )
        snapshot: dict[str, bool] = {}
        for entity_id in route_scope:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in {
                STATE_OFF,
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            }:
                continue
            muted = state.attributes.get("is_volume_muted")
            if muted is None:
                continue
            if not self._snapcast_source_matches(entity_id):
                continue
            snapshot[entity_id] = bool(muted)
''')

# THE ACTUAL FIX:
# Occupied-room routing must independently choose a room-local output.
# General/movable outputs are allowed too, but they can never satisfy the
# room-delivery requirement. This is the same nearest-level behavior already
# used for the fallback-room pass.
rep(p,
'''        ) = routed_plan(
            output_area_ids,
            filter_by_area=occupancy_filter_active,
        )
''',
'''        ) = routed_plan(
            output_area_ids,
            filter_by_area=occupancy_filter_active,
            require_room_delivery=occupancy_filter_active,
        )
''')

# Version.
rep(C/"const.py",'VERSION: Final = "0.9.4"','VERSION: Final = "0.9.5"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.9.4":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.9.5"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# Remove the wrong 0.9.4 regression and restore 0.9.3 source expectations.
wrong=ROOT/"tests"/"test_snapcast_selected_source_authority.py"
if wrong.exists():
    wrong.unlink()

p=ROOT/"tests"/"test_snapcast_source_resolution.py"
text=p.read_text(encoding="utf-8")
text=text.replace(
'''def test_snapcast_availability_trusts_explicit_selected_source_membership() -> None:
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
''',
'''def test_snapcast_availability_uses_authoritative_source_matcher() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("def _snapcast_output_available")
    end=manager.index("def _routable_snapcast_snapshot", start)
    block=manager[start:end]
    assert "return self._snapcast_source_matches(entity_id)" in block
    assert 'state.attributes.get("source") != source' not in block


def test_snapcast_snapshot_uses_same_source_matcher() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    start=manager.index("def _routable_snapcast_snapshot")
    end=manager.index("async def _async_apply_snapcast_route", start)
    block=manager[start:end]
    assert "if not self._snapcast_source_matches(entity_id):" in block
    assert 'state.attributes.get("source") != source' not in block
''')
p.write_text(text,encoding="utf-8")

(ROOT/"tests"/"test_occupied_room_delivery_required.py").write_text('''"""Occupied room selection must be independent of general outputs."""

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
''',encoding="utf-8")

res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8").replace(
    'assert manifest["version"] == "0.9.4"',
    'assert manifest["version"] == "0.9.5"',
)
res.write_text(text,encoding="utf-8")

ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.9.5 - 2026-10-03

- Fixed the actual room-output selection bug: occupied-room routing now requires
  an independent room-local delivery choice in addition to any General/movable
  notifications.
- General outputs such as laptops, phones, watches, and tablets can still receive
  the announcement, but they can no longer suppress the best available output
  in the occupied room.
- If no room output normally matches the level, the occupied room now uses its
  nearest available room-output level immediately, exactly like the fallback-room
  pass. Example: Info + Wohnzimmer TTS at Warning -> Wohnzimmer TTS is still
  selected while General Info/Debug notifications may also be sent.
- If the occupied room has zero room candidates, fallback-room behavior remains:
  the fallback room independently chooses its own best room-local output.
- Reverted the speculative v0.9.4 behavior that bypassed Snapcast source matching
  for explicitly selected clients. Snapcast source filtering remains strict.

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied 0.9.5 occupied-room independent selection fix")
