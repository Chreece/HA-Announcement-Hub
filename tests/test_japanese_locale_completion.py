"""Guard full native Japanese Announcement Hub localization."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "announcement_hub" / "translations"
KEEP = {"0%", "25%", "50%", "75%", "100%"}
PLACEHOLDERS = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")


def _flat(obj, prefix=""):
    if isinstance(obj, str):
        return {prefix: obj}
    result = {}
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        result.update(_flat(value, path))
    return result


def _load(lang):
    return _flat(json.loads((ROOT / f"{lang}.json").read_text(encoding="utf-8")))


def test_japanese_599_native_entries_and_no_english_help():
    en, ja = _load("en"), _load("ja")
    assert len(en) == 639
    assert set(ja) == set(en)
    identical = {key: source for key, source in en.items() if ja[key] == source}
    assert len(identical) == 5, identical
    assert set(identical.values()) == KEEP, identical
    for key, value in en.items():
        if "description" in key or ".error." in key:
            assert ja[key] != value, key


def test_japanese_reconfiguration_and_initial_setup_match():
    ja = _load("ja")
    for key, value in ja.items():
        if key.startswith("config.step."):
            options_key = "options.step." + key[len("config.step."):]
            if options_key in ja:
                assert ja[options_key] == value, (key, options_key)
    assert ja["options.step.init.title"] == "Announcement Hub を設定"
    assert "読書時間" not in ja["config.step.notification_profile.data_description.display_buffer_seconds"]


def test_japanese_templates_and_api_literals_survive():
    en, ja = _load("en"), _load("ja")
    for key, value in en.items():
        assert sorted(PLACEHOLDERS.findall(ja[key])) == sorted(
            PLACEHOLDERS.findall(value)
        ), key

    required = {
        "services.send.description": ("notify.announcement_hub",),
        "services.send.fields.click_action.description":
            ("app://", "entityId:entity_id", "clickAction", "notify_data"),
        "services.send.fields.text.description":
            ("text_tts", "text_notify", "text"),
        "services.send.fields.service.description":
            ("notification", "tts", "snapcast", "companion_tts"),
        "config.step.queue.data_description.default_use_ai":
            ("use_ai", "response_variable"),
        "config.step.queue.data_description.channel_fallback_mode":
            ("text_tts", "text_notify"),
        "config.step.tts.data_description.tts_voice": ("el_GR",),
        "config.step.edit_advanced_ai.data_description.rewrite":
            ("{message}", "{language}"),
        "config.step.edit_audio.data_description.person_chime_url":
            ("/local/chime.mp3",),
        "services.cancel.fields.job_id.description":
            ("announcement_hub.send",),
    }
    for key, values in required.items():
        for name in values:
            assert name in ja[key], (key, name)


def test_japanese_targeting_and_snapcast_help_keep_recipients_scoped():
    ja = _load("ja")
    manual = ja["services.send.fields.manual_targets.description"]
    assert "未選択の出力" in manual
    assert "すべての電話" in manual

    personal = ja["services.send.fields.target_person.description"]
    assert "別の部屋や共通出力" in personal
    area = ja["services.send.fields.area.description"]
    assert "ドアの状態" in area
    assert "独立して" in area

    snap = ja[
        "config.step.notification_profile.data_description.snapcast_only_source"
    ]
    assert "他の Snapcast グループ" in snap
    assert "触れません" in snap
