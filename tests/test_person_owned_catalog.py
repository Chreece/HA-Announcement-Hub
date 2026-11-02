"""Profile-owned integration/device groups must never select unrelated HA devices."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"
spec = importlib.util.spec_from_file_location("ah_person_catalog_test", COMPONENT / "person_catalog.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


PROFILES = {
    "person.alex": {
        "enabled": True, "destinations": {
            "mobile": ["notify.alex_phone", "notify.alex_phone"],
            "watch": ["notify.alex_watch"],
        },
    },
    "person.bob": {
        "enabled": True, "destinations": {
            "mobile": ["notify.bob_phone"],
            "other": ["media_player.bob_tv"],
        },
    },
    "person.disabled": {
        "enabled": False,
        "destinations": {"mobile": ["notify.other_device"]},
    },
}
METADATA = {
    "person.alex": {
        "notify.alex_phone": {"integration": "mobile_app", "device": "alex_phone_id", "device_label": "Pixel 9"},
        "notify.alex_watch": {"integration": "mobile_app", "device": "alex_watch_id", "device_label": "Watch 3"},
        # Other devices from the same integration cannot be inherited.
        "notify.bob_phone": {"integration": "mobile_app", "device": "bob_phone_id", "device_label": "Bob Phone"},
    },
    "person.bob": {
        "notify.bob_phone": {"integration": "mobile_app", "device": "bob_phone_id", "device_label": "Bob Phone"},
        "media_player.bob_tv": {"integration": "nfandroidtv", "device": "bob_tv_id", "device_label": "Bob TV"},
    },
    "person.disabled": {
        "notify.other_device": {"integration": "mobile_app", "device": "disabled_id", "device_label": "Disabled"},
    },
}


def test_owned_inventory_shows_only_profile_assigned_and_enabled_devices():
    data = module.owned_person_catalog(PROFILES, METADATA)
    assert set(data) == {"person.alex", "person.bob"}
    assert data["person.alex"]["integrations"] == [{"value": "mobile_app", "label": "Mobile App"}]
    assert {item["value"] for item in data["person.alex"]["devices"]} == {
        "alex_phone_id", "alex_watch_id",
    }
    assert "bob_phone_id" not in str(data["person.alex"])
    assert "disabled_id" not in str(data)


def test_integration_group_resolves_only_assigned_person_endpoints():
    owned = module.resolve_owned_person_outputs(
        PROFILES["person.alex"], METADATA["person.alex"],
        integrations=["mobile_app"],
    )
    assert owned == {
        "integration:mobile_app": ("notify.alex_phone", "notify.alex_watch"),
    }
    assert "notify.bob_phone" not in str(owned)


def test_device_filter_never_expands_into_other_person_or_other_device():
    selected = module.resolve_owned_person_outputs(
        PROFILES["person.alex"], METADATA["person.alex"],
        integrations=["mobile_app"], devices=["alex_phone_id", "bob_phone_id"],
    )
    assert selected["device:alex_phone_id"] == ("notify.alex_phone",)
    assert selected["device:bob_phone_id"] == ()
    assert selected["integration:mobile_app"] == ("notify.alex_phone", "notify.alex_watch")


def test_multi_person_target_option_may_match_only_one_profile_without_leaking():
    alex = module.resolve_owned_person_outputs(PROFILES["person.alex"], METADATA["person.alex"],
                                               devices=["bob_tv_id"])
    bob = module.resolve_owned_person_outputs(PROFILES["person.bob"], METADATA["person.bob"],
                                              devices=["bob_tv_id"])
    assert alex["device:bob_tv_id"] == ()
    assert bob["device:bob_tv_id"] == ("media_player.bob_tv",)


def test_empty_or_disabled_entity_registry_works_fail_closed():
    assert module.owned_person_catalog(PROFILES, {})["person.alex"] == {
        "integrations": [], "devices": [],
    }
    assert module.resolve_owned_person_outputs(
        PROFILES["person.alex"], {},
        integrations=["mobile_app"], devices=["alex_phone_id"],
    ) == {"integration:mobile_app": (), "device:alex_phone_id": ()}


def test_backend_requires_scoped_fields_and_rejects_globally_unowned_groups():
    source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    assert "ATTR_PERSON_INTEGRATION" in source
    assert "ATTR_PERSON_DEVICE" in source
    assert "owned_metadata = _person_owned_metadata(hass, profiles)" in source
    assert "requested_owned - matched_owned" in source
    assert "slots.update(owned_slots)" in source
    assert 'local["entities"] = refs' in source
    assert "SERVICE_LIST_PERSON_TARGETS" in source
    assert "async def async_list_person_targets(call: ServiceCall)" in source
    assert "supports_response=SupportsResponse.OPTIONAL" in source
    assert "target_person cannot be combined with area" in source


def test_person_target_list_exposes_no_global_output_fallback():
    source = (COMPONENT / "person_catalog.py").read_text(encoding="utf-8")
    assert "for entity_id in _assigned_entities(profile)" in source
    assert "for entity_id in assigned" in source
    assert "credentials" in source
    assert not hasattr(module, "expand_integration")
