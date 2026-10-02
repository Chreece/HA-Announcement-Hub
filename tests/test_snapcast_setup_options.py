"""Regression contracts for Snapcast discovery options."""

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
