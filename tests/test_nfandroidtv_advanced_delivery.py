# Regression contracts for NFAndroidTV advanced notification delivery.

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def test_legacy_service_resolution_uses_config_entry_title() -> None:
    outputs = (COMPONENT / "outputs.py").read_text(encoding="utf-8")
    assert "from homeassistant.util import slugify" in outputs
    assert "service_name = slugify(str(entry.title))" in outputs
    assert 'hass.services.has_service("notify", service_name)' in outputs


def test_nfandroidtv_uses_runtime_client_when_legacy_action_is_missing() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "async def _async_send_nfandroidtv_runtime(" in manager
    assert "entry.domain != INTEGRATION_NFANDROIDTV" in manager
    assert 'client = getattr(entry, "runtime_data", None)' in manager
    assert "self.hass.async_add_executor_job(" in manager
    assert 'bkgcolor=data.get("bkgcolor", data.get("color"))' in manager


def test_nfandroidtv_never_drops_position_into_generic_notify() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "if output.integration == INTEGRATION_NFANDROIDTV:" in manager
    assert "no active advanced delivery" in manager
    assert "if await self._async_send_nfandroidtv_runtime(" in manager


def test_direct_legacy_service_keeps_integration_and_area_binding() -> None:
    outputs = (COMPONENT / "outputs.py").read_text(encoding="utf-8")
    assert "slugify(str(entry.title)) != object_id" in outputs
    assert "integration = str(entry.domain)" in outputs
    assert "resolved_area = entry_area_id(hass, entry.entry_id)" in outputs


def test_nfandroidtv_power_observers_use_strong_identity_links_only() -> None:
    outputs = (COMPONENT / "outputs.py").read_text(encoding="utf-8")
    start = outputs.index("def notify_output_power_entities(")
    end = outputs.index("def notify_output_power_entity(", start)
    block = outputs[start:end]
    assert "output.integration != INTEGRATION_NFANDROIDTV" in block
    assert "notify_device_id" in block
    assert "_config_entry_host(notify_entry)" in block
    assert "== notify_host" in block
    assert "if same_device:" in block
    assert "if same_area:" in block
    assert "return tuple(dict.fromkeys(host_matches))" in block
    assert "len(host_matches) == 1" not in block
    assert "len(same_area) == 1" not in block
    assert "entity_name(" not in block
    assert "friendly_name" not in block


def test_nfandroidtv_multiple_power_observers_are_aggregated() -> None:
    outputs = (COMPONENT / "outputs.py").read_text(encoding="utf-8")
    start = outputs.index("def notify_output_power_available(")
    end = outputs.index("def area_name(", start)
    block = outputs[start:end]
    assert "notify_output_power_entities(hass, output)" in block
    assert "for entity_id in candidates:" in block
    assert "state.state not in _POWER_OFF_STATES" in block
    assert "return True" in block
    assert "return False" in block


def test_nfandroidtv_power_state_blocks_visual_candidate_when_all_observers_are_off() -> None:
    outputs = (COMPONENT / "outputs.py").read_text(encoding="utf-8")
    assert "STATE_STANDBY" in outputs
    assert "_POWER_OFF_STATES" in outputs
    start = outputs.index("def notify_output_available(")
    end = outputs.index("def snapcast_output_available(", start)
    block = outputs[start:end]
    assert "notify_output_power_available(hass, output) is False" in block
    assert "return False" in block


def test_nfandroidtv_host_matching_is_conservative_and_name_free() -> None:
    outputs = (COMPONENT / "outputs.py").read_text(encoding="utf-8")
    assert "from homeassistant.const import (" in outputs
    assert "CONF_HOST" in outputs
    assert "def _normalise_host(" in outputs
    assert "def _config_entry_host(" in outputs
    start = outputs.index("def notify_output_power_entities(")
    end = outputs.index("def notify_output_power_entity(", start)
    block = outputs[start:end]
    assert "configured host/IP match" in block
    assert "Entity IDs, names, models, and fuzzy text matching are never used" in block
