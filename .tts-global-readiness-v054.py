from pathlib import Path
import json

ROOT=Path(".")
C=ROOT/"custom_components"/"announcement_hub"

def rep(path, old, new):
    text=path.read_text(encoding="utf-8")
    count=text.count(old)
    if count!=1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    path.write_text(text.replace(old,new,1),encoding="utf-8")

# outputs.py: TTS availability must not require a generated TTS state.
p=C/"outputs.py"
rep(p,
'''def tts_engine_available(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    return state is not None and state.state != STATE_UNAVAILABLE
''',
'''def tts_engine_available(hass: HomeAssistant, entity_id: str) -> bool:
    """Return whether a configured TTS engine can be attempted.

    Home Assistant TextToSpeechEntity deliberately has no meaningful state
    before its first generated utterance. Requiring a live state here creates a
    first-use deadlock: the scheduler refuses to run the job that would create
    that first state. Treat registration + loaded owning config entry as
    availability, while still respecting an explicitly unavailable state.
    """
    reg_entry = er.async_get(hass).async_get(entity_id)
    if reg_entry is None or getattr(reg_entry, "disabled_by", None) is not None:
        return False

    if entry_id := _entity_config_entry_id(reg_entry):
        entry = _entry(hass, entry_id)
        if entry is None:
            return False
        entry_state = getattr(getattr(entry, "state", None), "value", None)
        if entry_state is not None and entry_state != "loaded":
            return False

    state = hass.states.get(entity_id)
    return state is None or state.state != STATE_UNAVAILABLE
''')

# manager.py: document/lock the global-vs-room contract.
m=C/"manager.py"
rep(m,
'''    def _job_has_ready_server_tts(self, job: AnnouncementJob) -> bool:
        if (
''',
'''    def _job_has_ready_server_tts(self, job: AnnouncementJob) -> bool:
        """Check global TTS infrastructure plus area-bound physical outputs.

        TTS engines and the shared TTS media player are global infrastructure;
        only Snapcast clients are room outputs and participate in area routing.
        """
        if (
''')

# Version.
rep(C/"const.py",'VERSION: Final = "0.5.3"','VERSION: Final = "0.5.4"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.5.3":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.5.4"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# Regression tests.
(ROOT/"tests"/"test_tts_global_readiness.py").write_text('''"""Regression contracts for global server-TTS infrastructure."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def test_tts_engine_first_use_does_not_require_live_state() -> None:
    outputs = (COMPONENT / "outputs.py").read_text(encoding="utf-8")
    start = outputs.index("def tts_engine_available")
    end = outputs.index("def companion_output_available", start)
    block = outputs[start:end]
    assert "er.async_get(hass).async_get(entity_id)" in block
    assert "entry_state" in block
    assert "state is None or state.state != STATE_UNAVAILABLE" in block


def test_server_tts_area_filter_applies_only_to_snapcast_outputs() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    start = manager.index("def _job_has_ready_server_tts")
    end = manager.index("def _job_runnable_now", start)
    block = manager[start:end]
    assert "job.tts_media_player" in block
    assert "tts_engine_available(self.hass, engine)" in block
    assert "job.snapcast_client_areas.get(" in block
    assert "entity_area_id(self.hass, job.tts_media_player)" not in block
    assert "entity_area_id(self.hass, engine)" not in block


def test_global_tts_fix_keeps_background_task_lifecycle() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(") == 2
''',encoding="utf-8")

res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8").replace(
    'assert manifest["version"] == "0.5.3"',
    'assert manifest["version"] == "0.5.4"',
)
res.write_text(text,encoding="utf-8")

ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.5.4 - 2026-10-02

- Fixed first-use server-TTS readiness deadlock.
- TTS engines are now treated as global infrastructure and no longer require a
  pre-existing TTS entity state before the first utterance.
- A TTS engine is considered attemptable from its enabled entity registration
  and loaded owning config entry; an explicit unavailable state is still
  respected.
- The shared server-TTS media player remains global infrastructure and is never
  area-filtered.
- Only Snapcast clients are physical server-TTS room outputs and participate in
  occupied-area routing.
- No queue worker or Home Assistant startup-task lifecycle behavior changed.

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied Announcement Hub 0.5.4 global TTS readiness fix")
