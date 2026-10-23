"""All localized card person-destination labels must be human-readable.

The output keys in PERSON_DESTINATIONS are stable API values and must not
be translated. Their visible labels are translated by _t(name).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
LOCALE_FILE = COMPONENT / "frontend" / "announcement-hub-locales.json"
CARD_JS = COMPONENT / "frontend" / "announcement-hub-card.js"
LABELS = ("People", "Room", "Mobile", "Watch", "Tablet", "Other")
MUST_LOCALIZE = ("People", "Room", "Mobile", "Watch", "Other")
TECHNICAL = (
    "tts.piper", "mobile_app, nfandroidtv",
    "notify.phone, media_player.speaker",
    "conversation.my_agent or ai_task.my_model",
    "/lovelace/cameras",
)
INTERPOLATION = re.compile(r"\{[a-z]+\}")


def test_destination_chips_translated_into_every_dashboard_locale():
    locales = json.loads(LOCALE_FILE.read_text(encoding="utf-8"))
    assert len(locales) == 19
    assert all(len(messages) == 156 for messages in locales.values())
    for language, messages in locales.items():
        for english in LABELS:
            assert english in messages, (language, english)
            assert isinstance(messages[english], str), (language, english)
            assert messages[english].strip(), (language, english)
        for english in MUST_LOCALIZE:
            assert messages[english] != english, (language, english)
        assert messages["Room"] != messages["Other"], language
        assert messages["Mobile"] != messages["Watch"], language


def test_card_label_changes_cannot_change_api_targets_or_examples():
    locales = json.loads(LOCALE_FILE.read_text(encoding="utf-8"))
    for language, messages in locales.items():
        for example in TECHNICAL:
            if example in messages:
                assert messages[example] == example, (language, example)
        for key, value in messages.items():
            assert sorted(INTERPOLATION.findall(key)) == sorted(
                INTERPOLATION.findall(value)
            ), (language, key)

    source = CARD_JS.read_text(encoding="utf-8")
    assert '["room", "Room"]' in source
    assert '["mobile", "Mobile"]' in source
    assert '["watch", "Watch"]' in source
    assert '["tablet", "Tablet"]' in source
    assert '["other", "Other"]' in source
    assert 'button.textContent = this._t(name)' in source
    assert "payload.person_destination = [...this._personDestinations]" in source
