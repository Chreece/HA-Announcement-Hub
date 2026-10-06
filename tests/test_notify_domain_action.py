"""Contracts for the canonical notify.announcement_hub action."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "custom_components" / "announcement_hub"


def test_primary_send_action_lives_under_notify_domain() -> None:
    init = (C / "__init__.py").read_text(encoding="utf-8")
    const = (C / "const.py").read_text(encoding="utf-8")
    assert 'DOMAIN as NOTIFY_DOMAIN' in init
    assert 'NOTIFY_SERVICE_ANNOUNCEMENT_HUB: Final = "announcement_hub"' in const
    assert "hass.services.async_register(\n        NOTIFY_DOMAIN," in init
    assert "NOTIFY_SERVICE_ANNOUNCEMENT_HUB" in init
    assert "schema=SEND_SCHEMA" in init
    assert "supports_response=SupportsResponse.OPTIONAL" in init


def test_notify_action_has_rich_service_description() -> None:
    init = (C / "__init__.py").read_text(encoding="utf-8")
    assert "def _notify_action_description()" in init
    assert 'root / "services.yaml"' in init
    assert 'root / "strings.json"' in init
    assert "async_set_service_schema(" in init
    assert "flat_fields" in init


def test_notify_is_a_setup_dependency() -> None:
    manifest = json.loads((C / "manifest.json").read_text(encoding="utf-8"))
    assert "notify" in manifest["dependencies"]
    assert "notify" not in manifest.get("after_dependencies", [])


def test_legacy_send_action_remains_compatible_but_docs_use_notify_action() -> None:
    init = (C / "__init__.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    strings = json.loads((C / "strings.json").read_text(encoding="utf-8"))
    assert "Backward-compatible alias" in init
    assert "hass.services.has_service(DOMAIN, SERVICE_SEND)" in init
    assert "notify.announcement_hub" in readme
    assert "action: announcement_hub.send" not in readme
    assert "legacy alias" in strings["services"]["send"]["name"].lower()
