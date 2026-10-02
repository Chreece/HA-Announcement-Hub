from pathlib import Path
import json

ROOT=Path(".")
C=ROOT/"custom_components"/"announcement_hub"

def rep(path, old, new):
    text=path.read_text(encoding="utf-8")
    count=text.count(old)
    if count!=1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old,new,1),encoding="utf-8")

# Always show every currently recognised notification output selected when the
# page opens. User can explicitly deselect outputs before submitting.
p=C/"config_flow.py"
rep(p,
'''        initial = CONF_NOTIFY_OUTPUTS not in self._working
        selected_default = (
            known
            if initial
            else [value for value in self._value(CONF_NOTIFY_OUTPUTS, []) if value in known]
        )
''',
'''        # Discovery is authoritative for the setup UI: every currently
        # supported notify entity is preselected whenever this page opens.
        # The user can deselect unwanted outputs before submitting.
        selected_default = list(known)
''')

# Remove dead intermediate notification-routing flow code. Keeping obsolete
# step methods around can confuse translation/resource maintenance even though
# they are no longer reachable from the four-step flow.
text=p.read_text(encoding="utf-8")
start=text.index("    def _prepare_notify_routing_steps(self) -> None:\n")
end=text.index("    def _prepare_notify_profile_steps(self) -> None:\n", start)
p.write_text(text[:start]+text[end:],encoding="utf-8")

# Bump version so HA/HACS presents this as a new integration revision.
rep(C/"const.py",'VERSION: Final = "0.8.0"','VERSION: Final = "0.8.1"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.8.0":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.8.1"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# Static resources: assert every visible field in step 1 has translated labels
# in EN/DE/EL and never relies on raw config keys.
for relative in ("strings.json","translations/en.json","translations/de.json","translations/el.json"):
    q=C/relative
    data=json.loads(q.read_text(encoding="utf-8"))
    for section in ("config","options"):
        step=data[section]["step"]["outputs"]
        required={
            "notify_outputs",
            "notify_room_outputs",
            "notify_info_outputs",
            "notify_warning_outputs",
            "notify_error_outputs",
            "notify_critical_outputs",
        }
        missing=required-set(step.get("data",{}))
        if missing:
            raise SystemExit(f"{relative}/{section}: missing labels {sorted(missing)}")
        for key in required:
            if not str(step["data"][key]).strip() or step["data"][key]==key:
                raise SystemExit(f"{relative}/{section}: raw/empty label for {key}")

# Update existing test and add a resource contract.
tests=ROOT/"tests"/"test_four_step_setup.py"
text=tests.read_text(encoding="utf-8")
text=text.replace(
'''    assert "selected_default = (" in flow
    assert "if initial" in flow
''',
'''    assert "selected_default = list(known)" in flow
''')
tests.write_text(text,encoding="utf-8")

(ROOT/"tests"/"test_notification_setup_ui.py").write_text('''"""UI contracts for notification discovery setup."""

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
''',encoding="utf-8")

res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8").replace(
    'assert manifest["version"] == "0.8.0"',
    'assert manifest["version"] == "0.8.1"',
)
res.write_text(text,encoding="utf-8")

ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.8.1 - 2026-10-02

- Notification setup now preselects every currently recognised supported notify
  entity whenever the page opens; users deselect outputs they do not want.
- Added resource contracts requiring translated labels for every notification
  grouping field in English, German, and Greek.
- Removed the obsolete per-output notification-routing config-flow methods left
  behind by the four-step setup redesign.
- No notification delivery or queue semantics changed.

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied 0.8.1 notification setup UI fixes")
