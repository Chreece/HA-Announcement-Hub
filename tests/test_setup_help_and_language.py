"""UI contracts for setup labels, help text, and TTS language selection."""

from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_tts_language_is_dropdown_from_engine_capabilities() -> None:
    flow=(C/"config_flow.py").read_text(encoding="utf-8")
    outputs=(C/"outputs.py").read_text(encoding="utf-8")
    assert "tts_engine_languages(self.hass" in flow
    assert "tts_default_language(self.hass" in flow
    tts_block=flow[
        flow.index("async def async_step_tts"):
        flow.index("async def async_step_snapcast")
    ]
    marker="_optional_marker(\n                    CONF_TTS_LANGUAGE"
    language_pos=tts_block.index(marker)
    block=tts_block[language_pos:language_pos+900]
    assert "selector.SelectSelector(" in block
    assert "selector.TextSelector()" not in block
    assert "supported_languages" in outputs


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
