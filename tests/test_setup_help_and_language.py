"""UI contracts for setup labels, help text, and TTS language selection."""

from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_tts_language_and_voice_are_engine_capability_dropdowns() -> None:
    flow=(C/"config_flow.py").read_text(encoding="utf-8")
    outputs=(C/"outputs.py").read_text(encoding="utf-8")
    assert "tts_engine_languages(self.hass" in flow
    assert "tts_default_language(" in flow
    assert "tts_engine_voice_options(" in flow
    tts_block=flow[
        flow.index("async def async_step_tts"):
        flow.index("async def async_step_snapcast")
    ]
    language_pos=tts_block.index("CONF_TTS_LANGUAGE")
    voice_pos=tts_block.index("CONF_TTS_VOICE")
    options_pos=tts_block.rindex("CONF_TTS_OPTIONS")
    direct_pos=tts_block.rindex("CONF_TTS_AREA_PLAYERS")
    assert language_pos < voice_pos < options_pos < direct_pos
    assert "selector.SelectSelector(" in tts_block
    assert "async_get_supported_voices(candidate)" in outputs
    assert "supported_languages" in outputs
    assert "_tts_language_family" in outputs
    assert "tts_engine_supports_voice" in outputs
    assert "selector.TextSelector()" in tts_block


def test_every_visible_four_step_field_has_specific_help_in_all_locales() -> None:
    for relative in ("strings.json","translations/en.json","translations/de.json","translations/el.json"):
        data=json.loads((C/relative).read_text(encoding="utf-8"))
        for section in ("config","options"):
            for step_name in ("outputs","tts","notification_profile","queue"):
                step=data[section]["step"][step_name]
                descriptions=step.get("data_description",{})
                for key,label in step.get("data",{}).items():
                    assert label and label != key, (relative,section,step_name,key)
                    assert key in descriptions, (relative,section,step_name,key)
                    assert len(str(descriptions[key]).strip()) >= 20, (
                        relative,section,step_name,key
                    )


def test_snapcast_profile_is_not_called_visual_behavior() -> None:
    for relative in ("strings.json","translations/en.json","translations/de.json","translations/el.json"):
        data=json.loads((C/relative).read_text(encoding="utf-8"))
        for section in ("config","options"):
            title=data[section]["step"]["notification_profile"]["title"].casefold()
            assert "visual behavior" not in title
            assert "οπτική συμπεριφορά" not in title
            assert "optische" not in title
