"""Reviewable card locale coverage, routing semantics and interpolation safety."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
CARD = COMPONENT / "frontend" / "announcement-hub-locales.json"
INTERPOLATION = re.compile(r"\{[a-z]+\}")
REQUIRED = {
    "The message", "Who receives it?", "How to deliver", "Announcement",
    "Delivery service", "AI provider", "Send announcement",
    "Choose a room or explicit recipient, or switch to Automatic routing.",
    "Selecting a delivery service requires a room or exact recipient. Use Automatic channel for automatic routing.",
    "Areas use room fallback. Integrations, devices and entities are exact additional recipients.",
    "A queued request is not a device-side delivery receipt.",
    "Queued #{id}{related}. Delivery will follow Hub routing.",
    "Could not submit: {error}. Check the queue before retrying.",
}
TECHNICAL_EXAMPLES = {
    "mobile_app, nfandroidtv", "notify.phone, media_player.speaker",
    "conversation.my_agent or ai_task.my_model", "/lovelace/cameras",
}


def test_all_supported_locales_cover_all_card_keys():
    locales = json.loads(CARD.read_text(encoding="utf-8"))
    keys = set(locales["el"])
    assert REQUIRED <= keys
    assert len(locales) == 19
    assert len(keys) >= 125
    for language, entries in locales.items():
        missing = keys - set(entries)
        assert not missing, (language, sorted(missing))
        for english, localized in entries.items():
            assert isinstance(localized, str) and localized.strip(), (language, english)
            assert sorted(INTERPOLATION.findall(english)) == sorted(
                INTERPOLATION.findall(localized)
            ), (language, english)
            if english in REQUIRED:
                assert localized != english, (language, english)


def test_exact_recipient_keys_and_lovelace_entity_examples_unchanged():
    locales = json.loads(CARD.read_text(encoding="utf-8"))
    for language, entries in locales.items():
        for literal in TECHNICAL_EXAMPLES:
            assert literal not in entries or entries[literal] == literal, (language, literal)
    js = (COMPONENT / "frontend" / "announcement-hub-card.js").read_text(encoding="utf-8")
    assert "payload.service = [this._channel]" in js
    assert "payload.ai_agent = agent" in js
    assert "translation(this._translations, key, args)" in js
    assert r"/\{([a-z]+)\}/g" in js
