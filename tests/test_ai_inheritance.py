"""Test omitted per-action AI fields inherit persisted integration settings."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
spec = importlib.util.spec_from_file_location(
    "announcement_hub_ai_settings_test", COMPONENT / "ai_settings.py"
)
assert spec is not None and spec.loader is not None
ai_settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_settings)


@pytest.mark.parametrize("configured,expected", [
    (True, True), (False, False), (None, False),
    ("true", True), ("on", True), ("false", False), ("off", False),
])
def test_omitted_use_ai_inherits_integration(configured, expected):
    assert ai_settings.resolve_ai_enabled(configured, None) == (
        expected, "integration"
    )


@pytest.mark.parametrize("configured", [True, False, "true", "false"])
def test_explicit_false_disables_even_if_default_is_true(configured):
    assert ai_settings.resolve_ai_enabled(configured, False) == (
        False, "action"
    )


@pytest.mark.parametrize("configured", [True, False, "true", "false"])
def test_explicit_true_enables_even_if_default_is_false(configured):
    assert ai_settings.resolve_ai_enabled(configured, True) == (
        True, "action"
    )


def test_real_user_template_has_no_implicit_false_override() -> None:
    data = yaml.safe_load(
        """
        action: notify.announcement_hub
        data:
          level: '{{ level | default("info", true) }}'
          occupied_only: true
          text_tts: '{{ message }}'
          text_notify: '{{ message_print | default(message, true) }}'
          title: '{{ title | default("Ειδοποίηση", true) }}'
          output: '{{ new_client }}'
        response_variable: announcement_hub_result
        """
    )
    assert "use_ai" not in data["data"]
    assert data["response_variable"] == "announcement_hub_result"
    assert ai_settings.resolve_ai_enabled(True, data["data"].get("use_ai")) == (
        True, "integration"
    )


def test_service_passes_tristate_and_job_exposes_ai_result() -> None:
    init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    model = (COMPONENT / "models.py").read_text(encoding="utf-8")
    assert "probatio.Optional(ATTR_USE_AI): bool" in init
    assert "probatio.Optional(ATTR_USE_AI, default=False)" not in init
    assert "use_ai=call.data.get(ATTR_USE_AI)" in init
    assert "resolve_ai_enabled(" in manager
    assert "self.settings.get(CONF_DEFAULT_USE_AI, DEFAULT_USE_AI)" in manager
    assert "diagnostics=ai" in manager
    assert "ai=ai_info" in manager
    assert '"ai": dict(job.ai)' in init
    assert "payload.setdefault(\"ai\", {})" in model

