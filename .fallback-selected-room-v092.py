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

# Routed plan now reports both "a room candidate exists" and "a room output was
# actually selected into this delivery plan".
rep(p,
'''            tuple[CompanionTTSOutput, ...],
            Any,
            bool,
        ]:
''',
'''            tuple[CompanionTTSOutput, ...],
            Any,
            bool,
            bool,
        ]:
''')

needle='''            chosen_notify = {
                item["id"] for item in chosen if item["kind"] == "notify"
            }
'''
replacement='''            room_delivery_selected = any(
                item["room_bound"] for item in chosen
            )

            chosen_notify = {
                item["id"] for item in chosen if item["kind"] == "notify"
            }
'''
rep(p,needle,replacement)

rep(p,
'''                route_plan,
                room_candidate_exists,
            )
''',
'''                route_plan,
                room_candidate_exists,
                room_delivery_selected,
            )
''')

rep(p,
'''            plan,
            occupied_room_candidate_exists,
        ) = routed_plan(
''',
'''            plan,
            occupied_room_candidate_exists,
            occupied_room_delivery_selected,
        ) = routed_plan(
''')

rep(p,
'''                    fallback_plan,
                    fallback_room_candidate_exists,
                ) = routed_plan(
''',
'''                    fallback_plan,
                    fallback_room_candidate_exists,
                    fallback_room_delivery_selected,
                ) = routed_plan(
''')

rep(p,
'''                if fallback_room_candidate_exists and fallback_plan.has_output:
''',
'''                if (
                    fallback_room_candidate_exists
                    and fallback_room_delivery_selected
                    and fallback_plan.has_output
                ):
''')

# Do not leak internal HA area IDs through the ordinary service response.
p=C/"__init__.py"
rep(p,
'''            "outputs": [area_name(hass, area_id) for area_id in job.outputs],
            "output_area_ids": list(job.outputs),
''',
'''            "outputs": [area_name(hass, area_id) for area_id in job.outputs],
''')

# Version.
rep(C/"const.py",'VERSION: Final = "0.9.1"','VERSION: Final = "0.9.2"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.9.1":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.9.2"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# Update regression from v0.9.1 plus exact new contracts.
p=ROOT/"tests"/"test_room_fallback_with_general_outputs.py"
text=p.read_text(encoding="utf-8")
text=text.replace(
'''def test_service_response_uses_friendly_area_names_and_keeps_ids() -> None:
    init=(C/"__init__.py").read_text(encoding="utf-8")
    assert '"outputs": [area_name(hass, area_id) for area_id in job.outputs]' in init
    assert '"output_area_ids": list(job.outputs)' in init
''',
'''def test_service_response_uses_friendly_area_names_only() -> None:
    init=(C/"__init__.py").read_text(encoding="utf-8")
    assert '"outputs": [area_name(hass, area_id) for area_id in job.outputs]' in init
    assert '"output_area_ids": list(job.outputs)' not in init


def test_fallback_is_not_committed_without_actual_room_delivery() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "room_delivery_selected = any(" in manager
    assert "fallback_room_delivery_selected" in manager
    assert "and fallback_room_delivery_selected" in manager
''')
p.write_text(text,encoding="utf-8")

res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8").replace(
    'assert manifest["version"] == "0.9.1"',
    'assert manifest["version"] == "0.9.2"',
)
res.write_text(text,encoding="utf-8")

ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.9.2 - 2026-10-03

- Fixed a false-positive fallback route where General/movable outputs made the
  fallback plan non-empty even though no fallback-room output was actually
  selected.
- Fallback is now committed only when a room-bound output from the configured
  fallback area is really present in the selected delivery plan.
- This prevents responses from claiming Flur fallback while the job contains
  only general phone/laptop/watch notifications.
- Removed Home Assistant internal area IDs from the normal send-action response;
  "outputs" now exposes only friendly area names.

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied 0.9.2 actual-room-delivery fallback guard")
