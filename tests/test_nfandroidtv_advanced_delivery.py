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
