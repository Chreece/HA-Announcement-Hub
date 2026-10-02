from __future__ import annotations

from pathlib import Path
import json

ROOT = Path('.')
COMPONENT = ROOT / 'custom_components' / 'announcement_hub'


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected exactly one match, found {count}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


outputs = COMPONENT / 'outputs.py'
replace_once(
    outputs,
    'from homeassistant.helpers import entity_registry as er\n\nfrom .const import (',
    'from homeassistant.helpers import entity_registry as er\nfrom homeassistant.util import slugify\n\nfrom .const import (',
)

old_service_branch = '''        elif ref.startswith(TARGET_SERVICE_PREFIX):
            service = ref.removeprefix(TARGET_SERVICE_PREFIX)
            if service.startswith("notify."):
                object_id = service.partition(".")[2]
                matching_entity = f"notify.{object_id}"
                result.append(
                    NotifyOutput(
                        ref=ref,
                        service=service,
                        integration=entity_integration(hass, matching_entity),
                        config_entry_id=entity_config_entry_id(
                            hass, matching_entity
                        ),
                    )
                )
'''
new_service_branch = '''        elif ref.startswith(TARGET_SERVICE_PREFIX):
            service = ref.removeprefix(TARGET_SERVICE_PREFIX)
            if service.startswith("notify."):
                object_id = service.partition(".")[2]
                matching_entity = f"notify.{object_id}"
                integration = entity_integration(hass, matching_entity)
                config_entry_id = entity_config_entry_id(hass, matching_entity)
                resolved_area = entity_area_id(hass, matching_entity)

                # A legacy notify action and its modern NotifyEntity are not
                # guaranteed to have the same object ID. NFAndroidTV names its
                # legacy action from the config-entry title, so recover the
                # owning entry when a user selected the service directly.
                if config_entry_id is None:
                    for entry in _entries(hass):
                        if slugify(str(entry.title)) != object_id:
                            continue
                        if not (
                            entry.domain == "nfandroidtv"
                            or f"{entry.domain}.notify" in hass.config.components
                        ):
                            continue
                        integration = str(entry.domain)
                        config_entry_id = str(entry.entry_id)
                        resolved_area = entry_area_id(hass, entry.entry_id)
                        break

                result.append(
                    NotifyOutput(
                        ref=ref,
                        service=service,
                        integration=integration,
                        config_entry_id=config_entry_id,
                        area_id=resolved_area,
                    )
                )
'''
replace_once(outputs, old_service_branch, new_service_branch)

old_legacy_resolver = '''def notify_output_legacy_service(
    hass: HomeAssistant, output: NotifyOutput
) -> str | None:
    """Return an advanced legacy notify action when one matches the output.

    Home Assistant's modern notify.send_message action intentionally accepts only
    message and title. Integrations such as nfandroidtv expose placement, duration,
    and styling through their legacy notify.<name> action.
    """
    if output.service:
        return output.service
    if not output.entity_id:
        return None
    object_id = output.entity_id.partition(".")[2]
    if object_id and hass.services.has_service("notify", object_id):
        return f"notify.{object_id}"
    return None
'''
new_legacy_resolver = '''def notify_output_legacy_service(
    hass: HomeAssistant, output: NotifyOutput
) -> str | None:
    """Return the provider's advanced legacy notify action, when available.

    Modern ``notify.send_message`` accepts only message and title. Providers such
    as NFAndroidTV expose placement, duration, and styling through their legacy
    ``notify.<name>`` action. The entity object ID is not guaranteed to equal that
    service name, so also resolve it from the owning config-entry title—the exact
    name Home Assistant uses when registering NFAndroidTV's legacy action.
    """
    if output.service:
        return output.service

    if output.entity_id:
        object_id = output.entity_id.partition(".")[2]
        if object_id and hass.services.has_service("notify", object_id):
            return f"notify.{object_id}"

    if output.config_entry_id:
        entry = _entry(hass, output.config_entry_id)
        if entry is not None:
            service_name = slugify(str(entry.title))
            if service_name and hass.services.has_service("notify", service_name):
                return f"notify.{service_name}"

    return None
'''
replace_once(outputs, old_legacy_resolver, new_legacy_resolver)

manager = COMPONENT / 'manager.py'
old_manager = '''        legacy_service = notify_output_legacy_service(self.hass, output)
        if output.integration == INTEGRATION_NFANDROIDTV and legacy_service:
            await self._async_call_legacy_notify(
                legacy_service,
                message=message,
                title=title,
                data=provider_data,
            )
            return
'''
new_manager = '''        legacy_service = notify_output_legacy_service(self.hass, output)
        if output.integration == INTEGRATION_NFANDROIDTV:
            # Never silently fall back to notify.send_message here. That modern
            # action discards NFAndroidTV's position, duration, font, colour,
            # transparency, and interrupt options. Raising lets the normal
            # availability retry window wait for the legacy action to appear.
            if not legacy_service:
                raise HomeAssistantError(
                    "Notifications for Android TV advanced notify action is not "
                    "available; position/style data cannot be applied"
                )
            await self._async_call_legacy_notify(
                legacy_service,
                message=message,
                title=title,
                data=provider_data,
            )
            return
'''
replace_once(manager, old_manager, new_manager)

manifest_path = COMPONENT / 'manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
if manifest.get('version') != '0.3.1':
    raise SystemExit(f"Unexpected manifest version: {manifest.get('version')}")
manifest['version'] = '0.3.2'
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

replace_once(
    COMPONENT / 'const.py',
    'VERSION: Final = "0.3.1"',
    'VERSION: Final = "0.3.2"',
)
replace_once(
    ROOT / 'tests' / 'test_resources.py',
    'assert manifest["version"] == "0.3.1"',
    'assert manifest["version"] == "0.3.2"',
)

changelog = ROOT / 'CHANGELOG.md'
changelog_text = changelog.read_text(encoding='utf-8')
heading = '# Changelog\n\n'
if not changelog_text.startswith(heading):
    raise SystemExit('Unexpected changelog header')
entry = '''## 0.3.2 - 2026-10-02

- Fixed Notifications for Android TV / Fire TV placement and styling being
  silently dropped when the modern notify entity ID differed from the legacy
  notify action name.
- Resolve the advanced Android TV notify action from the owning config-entry
  title, matching Home Assistant's own legacy-service registration.
- Retry while the advanced action is unavailable instead of falling back to
  `notify.send_message`, which cannot carry position or style options.
- Preserve integration and area discovery when a legacy notify service is
  selected directly.

'''
changelog.write_text(heading + entry + changelog_text[len(heading):], encoding='utf-8')

readme = ROOT / 'README.md'
readme_text = readme.read_text(encoding='utf-8')
anchor = '### Notifications for Android TV / Fire TV\n'
if anchor in readme_text and 'advanced legacy notify action' not in readme_text:
    readme_text = readme_text.replace(
        anchor,
        anchor
        + '\nPlacement and styling are delivered through the provider\'s advanced legacy notify action. Announcement Hub resolves that action from the selected output\'s config entry and will retry rather than silently use the generic `notify.send_message` action, which cannot carry these options.\n\n',
        1,
    )
    readme.write_text(readme_text, encoding='utf-8')

test_path = ROOT / 'tests' / 'test_nfandroidtv_advanced_delivery.py'
test_path.write_text('''"""Regression contracts for NFAndroidTV advanced notification delivery."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def test_legacy_service_resolution_uses_config_entry_title() -> None:
    outputs = (COMPONENT / "outputs.py").read_text(encoding="utf-8")
    assert "from homeassistant.util import slugify" in outputs
    assert "service_name = slugify(str(entry.title))" in outputs
    assert "hass.services.has_service(\"notify\", service_name)" in outputs


def test_nfandroidtv_never_drops_advanced_options_into_generic_notify() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "if output.integration == INTEGRATION_NFANDROIDTV:" in manager
    assert "if not legacy_service:" in manager
    assert "position/style data cannot be applied" in manager
    assert "Never silently fall back to notify.send_message" in manager


def test_direct_legacy_service_keeps_integration_and_area_binding() -> None:
    outputs = (COMPONENT / "outputs.py").read_text(encoding="utf-8")
    assert "slugify(str(entry.title)) != object_id" in outputs
    assert "integration = str(entry.domain)" in outputs
    assert "resolved_area = entry_area_id(hass, entry.entry_id)" in outputs
''', encoding='utf-8')

print('Applied Announcement Hub 0.3.2 NFAndroidTV position fix')
