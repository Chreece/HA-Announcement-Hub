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

rep(p,
'''    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaType,
)
''',
'''    DOMAIN as MEDIA_PLAYER_DOMAIN,
    DATA_COMPONENT as MEDIA_PLAYER_DATA_COMPONENT,
    MediaType,
)
''')

anchor='''    def _snapcast_output_available(self, entity_id: str) -> bool:
'''
text=p.read_text(encoding="utf-8")
i=text.index(anchor)
helper='''    def _snapcast_source_matches(self, entity_id: str) -> bool:
        """Match a Snapcast client's current stream to the configured TTS source.

        Home Assistant's Snapcast entity exposes source as the current Snapcast
        stream identifier, while select_source/source_list use friendly stream
        names. Resolve the configured friendly name through the live Snapcast
        entity before comparing.
        """
        source = str(
            self.settings.get(CONF_SNAPCAST_SOURCE, DEFAULT_SNAPCAST_SOURCE) or ""
        )
        source_only = bool(
            self.settings.get(
                CONF_SNAPCAST_ONLY_SOURCE, DEFAULT_SNAPCAST_ONLY_SOURCE
            )
        )
        if not source_only or not source:
            return True

        state = self.hass.states.get(entity_id)
        if state is None:
            return False
        current_source = str(state.attributes.get("source") or "")
        if current_source == source:
            return True

        component = self.hass.data.get(MEDIA_PLAYER_DATA_COMPONENT)
        entity = component.get_entity(entity_id) if component is not None else None
        group = getattr(entity, "_current_group", None) if entity is not None else None
        if group is None:
            return False

        try:
            streams = group.streams_by_name()
        except (AttributeError, TypeError):
            return False
        stream = streams.get(source)
        if stream is None:
            return False
        stream_id = str(getattr(stream, "identifier", "") or "")
        return bool(stream_id and current_source == stream_id)

'''
p.write_text(text[:i]+helper+text[i:],encoding="utf-8")

old='''    def _snapcast_output_available(self, entity_id: str) -> bool:
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
        source = str(
            self.settings.get(CONF_SNAPCAST_SOURCE, DEFAULT_SNAPCAST_SOURCE) or ""
        )
        source_only = bool(
            self.settings.get(
                CONF_SNAPCAST_ONLY_SOURCE, DEFAULT_SNAPCAST_ONLY_SOURCE
            )
        )
        return not (
            source_only
            and source
            and state.attributes.get("source") != source
        )
'''
new='''    def _snapcast_output_available(self, entity_id: str) -> bool:
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
'''
rep(p,old,new)

old='''        source = str(
            self.settings.get(CONF_SNAPCAST_SOURCE, DEFAULT_SNAPCAST_SOURCE) or ""
        )
        source_only = bool(
            self.settings.get(
                CONF_SNAPCAST_ONLY_SOURCE, DEFAULT_SNAPCAST_ONLY_SOURCE
            )
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
            if source_only and source and state.attributes.get("source") != source:
                continue
            snapshot[entity_id] = bool(muted)
'''
new='''        snapshot: dict[str, bool] = {}
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
rep(p,old,new)

rep(C/"const.py",'VERSION: Final = "0.9.2"','VERSION: Final = "0.9.3"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.9.2":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.9.3"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

(ROOT/"tests"/"test_snapcast_source_resolution.py").write_text('''"""Contracts for Snapcast area/source routing."""

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


def test_snapcast_availability_uses_authoritative_source_matcher() -> None:
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


def test_area_filter_still_runs_before_source_filter() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    area_filter=manager.index("routed_snapcast = tuple(")
    source_check=manager.index("def _snapcast_source_matches")
    assert area_filter < source_check
    routed=manager[area_filter:area_filter+700]
    assert "entity_area_id(self.hass, entity_id)" in routed
    assert "area_id in effective_areas" in routed
''',encoding="utf-8")

res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8").replace(
    'assert manifest["version"] == "0.9.2"',
    'assert manifest["version"] == "0.9.3"',
)
res.write_text(text,encoding="utf-8")

ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.9.3 - 2026-10-03

- Fixed Snapcast TTS-room detection when Home Assistant exposes the client's
  current source as a Snapcast stream identifier instead of the friendly stream
  name configured in Announcement Hub.
- Room routing remains area-first: only Snapcast clients in the occupied or
  fallback area are considered.
- The configured TTS source name is now resolved through the live Snapcast
  entity's stream map and compared to the current stream identifier.
- The same source-resolution logic is used both when deciding whether a room
  output is currently available and later when building the mute/routing
  snapshot, preventing inconsistent selection.
- Source filtering remains strict; a Music client in the correct room is not
  accepted as a TTS client merely because its area matches.

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied 0.9.3 Snapcast friendly-source resolution fix")
