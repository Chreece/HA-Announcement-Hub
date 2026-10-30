"""Native UI completeness and safety checks for Chinese scripts."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "announcement_hub" / "translations"
)
LANGUAGES = ("zh-Hans", "zh-Hant")
UNCHANGED = {"0%", "25%", "50%", "75%", "100%"}
INTERPOLATIONS = re.compile(r"\{\{\s*name\s*\}\}|\{[a-z_]+\}")


def _flatten(value, prefix=""):
    if isinstance(value, str):
        return {prefix: value}
    result = {}
    for name, child in value.items():
        key = f"{prefix}.{name}" if prefix else name
        result.update(_flatten(child, key))
    return result


def _read(lang):
    return _flatten(
        json.loads((ROOT / f"{lang}.json").read_text(encoding="utf-8"))
    )


def test_chinese_native_catalogs_have_599_keys_no_english_help():
    en = _read("en")
    assert len(en) == 625
    for lang in LANGUAGES:
        loc = _read(lang)
        assert set(loc) == set(en), lang
        same = {key: value for key, value in en.items() if loc[key] == value}
        assert len(same) == 5, (lang, same)
        assert set(same.values()) == UNCHANGED, (lang, same)
        for key, source in en.items():
            if "description" in key or ".error." in key:
                assert loc[key] != source, (lang, key)


def test_chinese_setup_and_reconfigure_help_agree():
    for lang in LANGUAGES:
        loc = _read(lang)
        for key, value in loc.items():
            if key.startswith("config.step."):
                opt = "options.step." + key[len("config.step."):]
                if opt in loc:
                    assert loc[opt] == value, (lang, key, opt)
    assert _read("zh-Hans")["options.step.init.title"] == "配置 Announcement Hub"
    assert _read("zh-Hant")["options.step.init.title"] == "設定 Announcement Hub"


def test_chinese_preserves_templates_and_home_assistant_identifiers():
    en = _read("en")
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
    for lang in LANGUAGES:
        loc = _read(lang)
        for key, original in en.items():
            assert sorted(INTERPOLATIONS.findall(original)) == sorted(
                INTERPOLATIONS.findall(loc[key])
            ), (lang, key)
        for key, tokens in required.items():
            for token in tokens:
                assert token in loc[key], (lang, key, token)


def test_chinese_recipient_and_snapcast_isolation_help():
    markers = {
        "zh-Hans": ("未选择的输出", "所有手机", "不转向其他房间", "受门状态", "其他 Snapcast"),
        "zh-Hant": ("未選取的輸出", "所有手機", "不轉至其他房間", "受門狀態", "其他 Snapcast"),
    }
    for lang, (recipient, phone, person, door, snap) in markers.items():
        d = _read(lang)
        assert recipient in d["services.send.fields.manual_targets.description"], lang
        assert phone in d["services.send.fields.manual_targets.description"], lang
        assert person in d["services.send.fields.target_person.description"], lang
        assert door in d["services.send.fields.area.description"], lang
        assert snap in d[
            "config.step.notification_profile.data_description.snapcast_only_source"
        ], lang


def test_traditional_ui_uses_traditional_terms_not_simplified():
    hans, hant = _read("zh-Hans"), _read("zh-Hant")
    assert "设备" in hans["config.step.outputs.data_description.notify_outputs"]
    for key, value in hant.items():
        for incorrect in (
            "设备", "发送", "语音", "选定", "默认",
            "客户端", "服务器", "音频", "缓存", "标签",
        ):
            assert incorrect not in value, (key, incorrect)
    assert "預設" in hant["config.step.tts.data_description.tts_engines"]
    assert "用戶端" in hant[
        "config.step.notification_profile.data_description.snapcast_source"
    ]
    assert "音訊" in hant["config.step.tts.data_description.tts_cache"]
    assert "快取" in hant["config.step.tts.data_description.tts_cache"]
