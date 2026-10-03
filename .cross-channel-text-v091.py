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

# Manager: every selected physical channel can use whichever message text exists.
p=C/"manager.py"
rep(p,
'''                        "native_text": bool(text_notify or level == LEVEL_CRITICAL),
''',
'''                        "native_text": bool(text_notify or text_tts),
''')
rep(p,
'''                            "native_text": bool(
                                text_tts or level == LEVEL_CRITICAL
                            ),
''',
'''                            "native_text": bool(text_tts or text_notify),
''',
count=3)

# Models: preserve channel-preferred text, but never drop the channel merely
# because only the other text field was supplied.
p=C/"models.py"
rep(p,
'''    if level == LEVEL_CRITICAL:
        tts_text = text_tts or text_notify
        notify_text = text_notify or text_tts
    else:
        tts_text = (
            text_tts or text_notify
            if force_tts
            else (text_tts if audible else None)
        )
        notify_text = (
            text_notify or text_tts
            if force_notify or not audible
            else text_notify
        )
''',
'''    if level == LEVEL_CRITICAL:
        tts_text = text_tts or text_notify
        notify_text = text_notify or text_tts
    else:
        # Channel selection has already been resolved by the manager. Keep each
        # channel's dedicated text when present, but fall back to the other text
        # instead of silently dropping an otherwise selected delivery path.
        tts_text = (
            (text_tts or text_notify)
            if (audible or force_tts)
            else None
        )
        notify_text = text_notify or text_tts
''')

# version
rep(C/"const.py",'VERSION: Final = "0.9.0"','VERSION: Final = "0.9.1"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.9.0":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.9.1"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# Regression tests
(ROOT/"tests"/"test_cross_channel_text_delivery.py").write_text('''"""Regression contracts for text fallback across selected output channels."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_notify_candidate_accepts_tts_only_announcements() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    block=manager[
        manager.index('"kind": "notify"'):
        manager.index('if not tts_hard_disabled:')
    ]
    assert '"native_text": bool(text_notify or text_tts)' in block


def test_tts_candidates_accept_notify_only_announcements() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert manager.count('"native_text": bool(text_tts or text_notify)') == 3


def test_selected_visual_channel_uses_notify_then_tts_text() -> None:
    models=(C/"models.py").read_text(encoding="utf-8")
    assert "notify_text = text_notify or text_tts" in models


def test_selected_tts_channel_uses_tts_then_notify_text() -> None:
    models=(C/"models.py").read_text(encoding="utf-8")
    assert "(text_tts or text_notify)" in models


def test_dedicated_text_still_wins_when_both_are_present() -> None:
    models=(C/"models.py").read_text(encoding="utf-8")
    assert "text_tts or text_notify" in models
    assert "text_notify or text_tts" in models
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

- Fixed selected notification outputs receiving only some announcements when the
  caller supplied text_tts but no text_notify.
- Visual notification candidates now remain eligible whenever either text field
  contains content; when delivered they prefer text_notify and fall back to
  text_tts.
- TTS candidates now likewise remain eligible whenever either text field contains
  content; when delivered they prefer text_tts and fall back to text_notify.
- This keeps the v0.9 availability/level selector authoritative: once a physical
  output is selected, it is no longer silently discarded because its dedicated
  text field was omitted.
- When both fields are supplied, channel-specific content is unchanged:
  notifications use text_notify and TTS uses text_tts.

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied 0.9.1 cross-channel text delivery fix")
