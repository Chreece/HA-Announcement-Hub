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

# Explicitly configured/expanded Snapcast clients are the authoritative TTS
# source selection. Availability must depend on connectivity + mute capability,
# not on the client's current group stream.
rep(p,
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
''',
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
''')

# Snapshot rules:
# - selected clients are authoritative TTS clients and are always in scope when
#   connected, regardless of current stream/source label;
# - unrelated clients discovered from the integration still respect the optional
#   source restriction so Announcement Hub does not mute unrelated audio.
old='''        route_scope = tuple(
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
'''
new='''        selected_set = set(selected_clients)
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
'''
rep(p,old,new)

# Version.
rep(C/"const.py",'VERSION: Final = "0.9.3"','VERSION: Final = "0.9.4"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.9.3":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.9.4"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# Regression tests.
(ROOT/"tests"/"test_snapcast_selected_source_authority.py").write_text('''"""Selected Snapcast outputs are the authoritative TTS-source membership."""

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
''',encoding="utf-8")

# Update older source-resolution test to match the corrected architecture.
p=ROOT/"tests"/"test_snapcast_source_resolution.py"
text=p.read_text(encoding="utf-8")
text=text.replace(
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
''',
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
''')
p.write_text(text,encoding="utf-8")

res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8").replace(
    'assert manifest["version"] == "0.9.3"',
    'assert manifest["version"] == "0.9.4"',
)
res.write_text(text,encoding="utf-8")

ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.9.4 - 2026-10-03

- Corrected Snapcast TTS-source semantics.
- The Snapcast entry/entities selected in Announcement Hub configuration are now
  authoritative membership of the TTS Snapcast path.
- Room routing first filters those selected clients by Home Assistant area, then
  checks whether the resulting room client is connected and mute-controllable.
- Explicitly selected TTS clients are no longer rejected merely because their
  current Snapcast group stream/source label differs from the configured source
  text.
- The optional source restriction is still applied to unselected Snapcast
  clients included in the mute snapshot, preventing unrelated Music clients from
  being muted by announcement routing.
- This fixes occupied rooms such as Wohnzimmer and fallback rooms such as Flur
  returning zero snapcast_clients even though the selected TTS Snapcast entry
  contains a client assigned to that area.

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied 0.9.4 selected Snapcast TTS-source authority fix")
