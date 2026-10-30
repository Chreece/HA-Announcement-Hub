"""Sleep-mode written-recipient policy and configuration contract."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
MODULE = COMPONENT / "sleep_delivery.py"

spec = importlib.util.spec_from_file_location("test_sleep_delivery_policy", MODULE)
assert spec and spec.loader
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def output(ref, integration, area=None):
    return SimpleNamespace(ref=ref, integration=integration, area_id=area)


OUTPUTS = (
    output("entity:notify.pixel", "mobile_app"),
    output("entity:notify.tablet", "mobile_app", "schlafzimmer"),
    output("entity:notify.tv", "nfandroidtv", "wohnzimmer"),
    output("entity:notify.fire", "nfandroidtv", "kueche"),
    output("service:notify.legacy", None),
)


def test_integration_options_precede_devices_and_all_labels_are_grounded():
    names = {item.ref: item.ref.split(".")[-1].title() for item in OUTPUTS}
    options = policy.sleep_notify_output_options(OUTPUTS, names)
    values = [item["value"] for item in options]
    assert values[:2] == ["integration:mobile_app", "integration:nfandroidtv"]
    assert set(values[2:]) == {item.ref for item in OUTPUTS}
    assert "all devices (2)" in options[0]["label"].casefold()
    assert "all devices (2)" in options[1]["label"].casefold()


def test_multi_selection_combines_integrations_and_devices_without_duplicates():
    selected = policy.sleep_notify_selected_refs(OUTPUTS, (
        "integration:mobile_app", "entity:notify.tv", "entity:notify.pixel",
    ))
    assert selected == (
        "entity:notify.pixel", "entity:notify.tablet", "entity:notify.tv",
    )


def test_absent_setting_preserves_old_mobile_only_and_empty_setting_means_none():
    assert policy.sleep_notify_selected_refs(OUTPUTS, None) == (
        "entity:notify.pixel", "entity:notify.tablet",
    )
    assert policy.sleep_notify_selected_refs(OUTPUTS, []) == ()


def test_unknown_and_unconfigured_devices_are_never_selected():
    assert policy.sleep_notify_selected_refs(OUTPUTS[:2], (
        "integration:nfandroidtv", "entity:notify.fire",
    )) == ()
    assert policy.sleep_notify_selected_refs(OUTPUTS, (
        "entity:notify.unknown", "integration:missing",
    )) == ()


def test_localized_group_and_device_labels_are_supported():
    opts = policy.sleep_notify_output_options(
        OUTPUTS,
        integration_label=lambda name, count: f"{name}: alle {count}",
        device_label=lambda name: f"Gerät: {name}",
    )
    assert opts[0]["label"] == "mobile_app: alle 2"
    assert all(item["label"].startswith("Gerät:") for item in opts[2:])


def test_general_options_have_two_independent_toggles_and_recipient_multiselect():
    source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    queue = source[source.index("    async def async_step_queue("):
                   source.index("class AnnouncementHubConfigFlow(")]
    assert "CONF_SLEEP_MUTE_TTS" in queue
    assert "CONF_SLEEP_FALLBACK_WRITTEN" in queue
    assert "CONF_SLEEP_FALLBACK_OUTPUTS" in queue
    assert "sleep_target_defaults" in queue
    assert "_known_multi_select(sleep_target_options)" in queue
    assert "invalid_sleep_fallback_target" in queue
    assert "self._sleep_written_recipient_options()" in queue


def test_group_and_device_select_preserves_offline_explicit_choice():
    source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    klass = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                 and x.name == "_AnnouncementFlowMixin")
    method = next(x for x in klass.body if isinstance(x, ast.FunctionDef)
                  and x.name == "_sleep_written_recipient_options")
    compiled = compile(ast.fix_missing_locations(
        ast.Module(body=[method], type_ignores=[])), "recipient options", "exec")

    configured = [output("entity:notify.pixel", "mobile_app")]
    current = ["entity:notify.unavailable"]
    options = [
        {"value": "entity:notify.pixel", "label": "Pixel"}
    ]
    namespace = {
        "expand_notify_output_tokens": lambda hass, refs: refs,
        "resolve_notify_outputs": lambda hass, refs: tuple(
            x for x in configured if x.ref in refs
        ),
        "notify_output_options": lambda hass: options,
        "sleep_notify_output_options": policy.sleep_notify_output_options,
        "provider_label": lambda hass, key, **v: (
            f"{key} " + " ".join(str(x) for x in v.values())
        ),
        "integration_label": lambda name: name,
        "INTEGRATION_MOBILE_APP": "mobile_app",
        "INTEGRATION_TOKEN_PREFIX": "integration:",
        "CONF_NOTIFY_OUTPUTS": "notify_outputs",
        "CONF_SLEEP_FALLBACK_OUTPUTS": "sleep_fallback_outputs",
        "selector": SimpleNamespace(
            SelectOptionDict=lambda **kwargs: kwargs,
        ),
    }
    exec(compiled, namespace)
    class Fake:
        _working = {
            "notify_outputs": ["entity:notify.pixel"],
            "sleep_fallback_outputs": current,
        }
        hass = SimpleNamespace()
        def _value(self, key, default):
            return self._working.get(key, default)

    entries, selected = namespace["_sleep_written_recipient_options"](Fake())
    assert selected == current
    assert entries[-1]["value"] == "entity:notify.unavailable"
    fake = Fake()
    fake._working = {"notify_outputs": ["entity:notify.pixel"]}
    _, defaults = namespace["_sleep_written_recipient_options"](fake)
    assert defaults == ["integration:mobile_app"]
