"""All localized card person-destination labels must be human-readable.

The output keys in PERSON_DESTINATIONS are stable API values and must not
be translated. Their selected labels, icon tooltips and aria-labels are
translated by _t(name), while recipient identifiers remain unchanged.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
LOCALE_FILE = COMPONENT / "frontend" / "announcement-hub-locales.json"
CARD_JS = COMPONENT / "frontend" / "announcement-hub-card.js"
LABELS = ("People", "Room", "Integrations", "Devices")
MUST_LOCALIZE = ("People", "Room", "Integrations", "Devices")
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
    assert all(len(messages) == 208 for messages in locales.values())
    for language, messages in locales.items():
        for english in LABELS:
            assert english in messages, (language, english)
            assert isinstance(messages[english], str), (language, english)
            assert messages[english].strip(), (language, english)
        for english in MUST_LOCALIZE:
            assert messages[english] != english, (language, english)
        assert messages["Room"] != messages["Integrations"], language
        assert messages["Integrations"] != messages["Devices"], language


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
    assert 'const PERSON_DESTINATIONS = [["room", "Room"]]' in source
    assert 'this._personOwned = { integration: new Set(), device: new Set() }' in source
    assert 'button.title = this._t(name)' in source
    assert 'button.setAttribute("aria-label", this._t(name))' in source
    assert 'this.$("person-destinations-selected").textContent' in source
    assert 'button.appendChild(symbol)' in source
    assert 'this._drawPersonOwnedTargets()' in source
    assert "payload.person_destination = exactPersonTargets ? [] : [...this._personDestinations]" in source
