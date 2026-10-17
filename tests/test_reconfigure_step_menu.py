"""Regression contracts for direct Reconfigure and Configure navigation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
FLOW_SOURCE = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")

spec = importlib.util.spec_from_file_location(
    "announcement_hub_flow_settings_test",
    COMPONENT / "flow_settings.py",
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
merge_reconfiguration = module.merge_reconfiguration


def test_direct_menu_exists_on_both_config_entry_buttons() -> None:
    assert "async def async_step_reconfigure(" in FLOW_SOURCE
    assert 'step_id="reconfigure", menu_options=list(EDIT_MENU_OPTIONS)' in FLOW_SOURCE
    assert 'step_id="init", menu_options=list(EDIT_MENU_OPTIONS)' in FLOW_SOURCE
    for choice in ("edit_outputs", "edit_tts", "edit_profiles", "edit_general", "edit_all"):
        assert f'    "{choice}",' in FLOW_SOURCE
        assert f"async def async_step_{choice}(" in FLOW_SOURCE


def test_first_time_setup_remains_guided() -> None:
    source = FLOW_SOURCE[
        FLOW_SOURCE.index("class AnnouncementHubConfigFlow("):
        FLOW_SOURCE.index("class AnnouncementHubOptionsFlow(")
    ]
    assert "async def async_step_user(" in source
    assert 'return await self.async_step_outputs()' in source
    assert "async def async_step_reconfigure(" in source
    assert "self._get_reconfigure_entry()" in source
    assert "self.async_update_and_abort(" in source
    assert "self.async_create_entry(title=NAME, data=self._working)" in source
    assert "async_update_reload_and_abort(" not in source


def test_each_selected_section_finishes_without_opening_following_pages() -> None:
    outputs = FLOW_SOURCE[
        FLOW_SOURCE.index("async def async_step_outputs("):
        FLOW_SOURCE.index("def _prepare_notify_profile_steps")
    ]
    tts = FLOW_SOURCE[
        FLOW_SOURCE.index("async def async_step_tts("):
        FLOW_SOURCE.index("async def async_step_snapcast(")
    ]
    profiles = FLOW_SOURCE[
        FLOW_SOURCE.index("async def async_step_notification_profile("):
        FLOW_SOURCE.index("async def async_step_tts(")
    ]
    assert 'if self._edit_section == "outputs":' in outputs
    assert 'if self._edit_section == "tts":' in tts
    assert 'if self._edit_section == "profiles":' in profiles
    assert "return await self._async_finish()" in outputs
    assert "return await self._async_finish()" in tts
    assert "return await self._async_finish()" in profiles
    assert 'self._edit_section = "queue"' in FLOW_SOURCE
    assert 'self._edit_section = None' in FLOW_SOURCE


def test_existing_output_selection_is_preserved_not_auto_selected() -> None:
    assert "selected_default = list(known)" in FLOW_SOURCE
    assert "self._editing_existing or domain in domains" in FLOW_SOURCE
    assert "if self._editing_existing:" in FLOW_SOURCE
    assert "ref for ref in self._working.get(CONF_NOTIFY_OUTPUTS, [])" in FLOW_SOURCE
    assert "if ref not in known:" in FLOW_SOURCE
    assert "options.append(" in FLOW_SOURCE
    assert "policies[ref].get(NOTIFY_POLICY_SCOPE)" in FLOW_SOURCE


def test_menu_translations_match_all_languages() -> None:
    expected = {"edit_outputs", "edit_tts", "edit_profiles", "edit_general", "edit_all"}
    for filename in (
        "strings.json",
        "translations/en.json",
        "translations/de.json",
        "translations/el.json",
    ):
        contents = json.loads((COMPONENT / filename).read_text(encoding="utf-8"))
        for section, step in (("config", "reconfigure"), ("options", "init")):
            menu = contents[section]["step"][step]
            assert menu["title"]
            assert menu["description"]
            assert set(menu["menu_options"]) == expected
            assert set(menu["menu_option_descriptions"]) == expected
            assert all(menu["menu_options"].values())
            assert all(menu["menu_option_descriptions"].values())


def test_reconfigure_preserves_original_data_and_other_option_overrides() -> None:
    data = {
        "notify_outputs": ["entity:notify.tv"],
        "tts_engines": ["tts.piper"],
        "queue_max": 100,
        "default_use_ai": False,
    }
    opts = {
        "notify_outputs": ["entity:notify.phone"],
        "default_use_ai": True,
        "default_ai_agent": "conversation.home",
    }
    working = {**data, **opts, "default_ai_agent": "conversation.custom"}
    next_data, next_options = merge_reconfiguration(data, opts, working)
    assert next_data == data
    assert next_options == {
        **opts, "default_ai_agent": "conversation.custom"
    }
    assert {**next_data, **next_options} == working
    assert data["notify_outputs"] == ["entity:notify.tv"]
    assert opts["default_ai_agent"] == "conversation.home"


def test_reconfigure_updates_values_at_their_existing_storage_location() -> None:
    data = {"tts_engines": ["tts.old"], "queue_max": 100}
    opts = {"queue_max": 90, "fallback_ai_agent": "conversation.backup"}
    working = {**data, **opts, "tts_engines": ["tts.piper"], "queue_max": 80}
    new_data, new_options = merge_reconfiguration(data, opts, working)
    assert new_data["tts_engines"] == ["tts.piper"]
    assert new_data["queue_max"] == 100
    assert new_options["queue_max"] == 80
    assert new_options["fallback_ai_agent"] == "conversation.backup"


@pytest.mark.parametrize("where", ["data", "options", "both"])
def test_cleared_values_do_not_resurrect(where: str) -> None:
    data = {"tts_language": "el_GR", "tts_engines": ["tts.piper"]}
    opts = {"notify_outputs": ["notify.mobile"]}
    if where in {"options", "both"}:
        opts["tts_language"] = "de_DE"
    if where == "options":
        data.pop("tts_language")
    working = {**data, **opts}
    working.pop("tts_language")
    new_data, new_options = merge_reconfiguration(data, opts, working)
    assert "tts_language" not in new_data
    assert "tts_language" not in new_options
    assert new_options["notify_outputs"] == ["notify.mobile"]


def test_unedited_legacy_unknown_settings_survive() -> None:
    data = {"future_unknown_setting": {"nested": ["keep"]}}
    options = {"other_setting": ["kept"]}
    working = {**data, **options}
    assert merge_reconfiguration(data, options, working) == (data, options)
