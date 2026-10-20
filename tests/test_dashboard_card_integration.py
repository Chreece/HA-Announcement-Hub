"""Bundled dashboard card installation and Home Assistant contract tests."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
FRONTEND = COMPONENT / "frontend"


def test_dashboard_assets_are_shipped_by_the_integration_and_manual_installer():
    package = {
        "frontend/announcement-hub-card.js",
        "frontend/announcement-hub-card.css",
        "frontend/announcement-hub-card.html",
    }
    for name in package:
        target = COMPONENT / name
        assert target.is_file()
        assert target.stat().st_size >= 1000
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")
    for name in package:
        assert name in installer
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    assert "http" in manifest["dependencies"]
    assert manifest["domain"] == "announcement_hub"


def test_http_resources_use_nonblocking_home_assistant_static_path_api():
    source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    assert "from homeassistant.components.http import StaticPathConfig" in source
    assert "await hass.http.async_register_static_paths(" in source
    assert '"/announcement_hub"' in source
    assert 'str(Path(__file__).parent / "frontend")' in source
    assert "StaticPathConfig(" in source
    assert '"frontend"' in source
    assert "hass.http.register_static_path(" not in source


def test_card_action_payloads_are_still_governed_by_core_schema():
    init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    card = (FRONTEND / "announcement-hub-card.js").read_text(encoding="utf-8")
    for field in (
        "text", "text_tts", "text_notify", "title", "area",
        "integration", "device", "entity", "service", "level",
        "use_ai", "ai_mode", "ai_agent", "click_action", "occupied_only",
    ):
        assert field in init or field == "text"
        assert field in card
    assert '"notify", "announcement_hub", payload, undefined, false, true' in card
    assert "if (reply?.job_id)" in card
    assert "Queued #" in card
    assert "check the queue before retrying" in card.lower()
    assert 'this.$("critical-confirm").hidden = false' in card


def test_card_is_english_and_readme_shows_exact_module_resource_url():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Dashboard card" in readme
    assert "/announcement_hub/announcement-hub-card.js" in readme
    assert "type: custom:announcement-hub-card" in readme
    assert "JavaScript module" in readme
    assert "Home Assistant" in readme
    assert "No external" not in readme or "no extra custom-card repository" in readme.lower()
    card = (FRONTEND / "announcement-hub-card.js").read_text(encoding="utf-8")
    assert "announcement-hub-card-editor" in card
    assert "window.customCards.push" in card
    assert "preview: true" in card


def test_styling_and_markups_have_no_external_runtime_resources():
    js = (FRONTEND / "announcement-hub-card.js").read_text(encoding="utf-8")
    html = (FRONTEND / "announcement-hub-card.html").read_text(encoding="utf-8")
    css = (FRONTEND / "announcement-hub-card.css").read_text(encoding="utf-8")
    assert "https://" not in css
    assert "https://" not in html
    assert "<script" not in html.lower()
    assert "eval(" not in js
    assert "new Function" not in js
    assert "textContent" in js
    assert "prefers-reduced-motion" in css
    assert "max-width:550px" in css
    for field_id in ("message", "text-tts", "text-notify", "message-title",
                     "targets", "send", "critical-confirm", "notice"):
        assert ('id="' + field_id + '"') in html
