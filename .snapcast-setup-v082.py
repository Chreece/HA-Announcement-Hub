from pathlib import Path
import json

ROOT=Path(".")
C=ROOT/"custom_components"/"announcement_hub"

def rep(path,old,new):
    text=path.read_text(encoding="utf-8")
    count=text.count(old)
    if count!=1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old,new,1),encoding="utf-8")

p=C/"outputs.py"
rep(p,
'''def snapcast_output_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return concrete Snapcast client entities only."""
    return [
        option.as_dict()
        for option in concrete_entity_options(
            hass,
            entity_domain="media_player",
            integration="snapcast",
        )
        if "group" not in option["value"].casefold()
    ]
''',
'''def snapcast_output_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return concrete Snapcast client entities only."""
    return [
        option.as_dict()
        for option in concrete_entity_options(
            hass,
            entity_domain="media_player",
            integration="snapcast",
        )
        if "group" not in option.value.casefold()
    ]
''')

# version
rep(C/"const.py",'VERSION: Final = "0.8.1"','VERSION: Final = "0.8.2"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.8.1":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.8.2"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# tests
(ROOT/"tests"/"test_snapcast_setup_options.py").write_text('''"""Regression contracts for Snapcast discovery options."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_snapcast_discovery_filters_selectoption_objects_before_serializing() -> None:
    source=(C/"outputs.py").read_text(encoding="utf-8")
    start=source.index("def snapcast_output_options")
    end=source.index("def companion_tts_output_options", start)
    block=source[start:end]
    assert 'if "group" not in option.value.casefold()' in block
    assert 'option["value"]' not in block
    assert "option.as_dict()" in block
''',encoding="utf-8")

res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8").replace(
    'assert manifest["version"] == "0.8.1"',
    'assert manifest["version"] == "0.8.2"',
)
res.write_text(text,encoding="utf-8")

ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.8.2 - 2026-10-02

- Fixed the TTS setup crash when Snapcast is installed.
- Snapcast discovery now filters SelectOption objects through their value
  attribute before serializing them to Home Assistant selector dictionaries.
- Added a regression test for the exact object/dict mismatch that produced
  "TypeError: 'SelectOption' object is not subscriptable".

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied 0.8.2 Snapcast setup crash fix")
