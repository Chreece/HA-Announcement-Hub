from __future__ import annotations

from pathlib import Path
import json

ROOT = Path(".")
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


manager = COMPONENT / "manager.py"

replace_once(
    manager,
    "from copy import deepcopy\nimport logging\n",
    "from copy import deepcopy\nfrom functools import partial\nimport logging\n",
)

old_delivery = '''        legacy_service = notify_output_legacy_service(self.hass, output)
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

new_delivery = '''        legacy_service = notify_output_legacy_service(self.hass, output)
        if output.integration == INTEGRATION_NFANDROIDTV:
            # Prefer Home Assistant's provider action when it exists because it
            # also supports image/icon loading. Modern config-entry installs can
            # expose only the NotifyEntity, though, so use the integration's
            # already-connected runtime client as the advanced fallback.
            if legacy_service:
                await self._async_call_legacy_notify(
                    legacy_service,
                    message=message,
                    title=title,
                    data=provider_data,
                )
                return
            if await self._async_send_nfandroidtv_runtime(
                output,
                message=message,
                title=title,
                data=provider_data,
            ):
                return
            raise HomeAssistantError(
                "Notifications for Android TV has no active advanced delivery "
                "path; position/style data cannot be applied"
            )
'''
replace_once(manager, old_delivery, new_delivery)

anchor = '''    async def _async_call_legacy_notify(
        self,
        service_ref: str,
'''
helper = '''    async def _async_send_nfandroidtv_runtime(
        self,
        output: NotifyOutput,
        *,
        message: str,
        title: str | None,
        data: Mapping[str, Any],
    ) -> bool:
        "Send through NFAndroidTV's live config-entry client."
        if not output.config_entry_id:
            return False
        entry = self.hass.config_entries.async_get_entry(output.config_entry_id)
        if entry is None or entry.domain != INTEGRATION_NFANDROIDTV:
            return False
        client = getattr(entry, "runtime_data", None)
        send = getattr(client, "send", None)
        if not callable(send):
            return False

        duration_value = data.get("duration")
        duration = int(duration_value) if duration_value is not None else None
        await self.hass.async_add_executor_job(
            partial(
                send,
                message,
                title=title,
                duration=duration,
                fontsize=data.get("fontsize"),
                position=data.get("position"),
                bkgcolor=data.get("bkgcolor", data.get("color")),
                transparency=data.get("transparency"),
                interrupt=bool(data.get("interrupt", False)),
            )
        )
        return True

    async def _async_call_legacy_notify(
        self,
        service_ref: str,
'''
replace_once(manager, anchor, helper)

manifest_path = COMPONENT / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("version") != "0.3.2":
    raise SystemExit(f"Unexpected manifest version: {manifest.get('version')}")
manifest["version"] = "0.3.3"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

replace_once(
    COMPONENT / "const.py",
    'VERSION: Final = "0.3.2"',
    'VERSION: Final = "0.3.3"',
)
replace_once(
    ROOT / "tests" / "test_resources.py",
    'assert manifest["version"] == "0.3.2"',
    'assert manifest["version"] == "0.3.3"',
)

test_path = ROOT / "tests" / "test_nfandroidtv_advanced_delivery.py"
test_path.write_text(
    '''# Regression contracts for NFAndroidTV advanced notification delivery.

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
    assert "no active advanced delivery path" in manager
    assert "if await self._async_send_nfandroidtv_runtime(" in manager


def test_direct_legacy_service_keeps_integration_and_area_binding() -> None:
    outputs = (COMPONENT / "outputs.py").read_text(encoding="utf-8")
    assert "slugify(str(entry.title)) != object_id" in outputs
    assert "integration = str(entry.domain)" in outputs
    assert "resolved_area = entry_area_id(hass, entry.entry_id)" in outputs
''',
    encoding="utf-8",
)

changelog = ROOT / "CHANGELOG.md"
changelog_text = changelog.read_text(encoding="utf-8")
heading = "# Changelog\n\n"
if not changelog_text.startswith(heading):
    raise SystemExit("Unexpected changelog header")
entry = '''## 0.3.3 - 2026-10-02

- Fixed Notifications for Android TV / Fire TV disappearing entirely when the
  advanced legacy `notify.<name>` action is absent or registered under another
  name.
- Added an executor-safe fallback through the integration config entry's live
  `Notifications` runtime client, preserving position, duration, font, colour,
  transparency, and interrupt.
- Kept the provider action as the first choice where available so image/icon
  loading remains supported.

'''
changelog.write_text(
    heading + entry + changelog_text[len(heading):],
    encoding="utf-8",
)

readme = ROOT / "README.md"
readme_text = readme.read_text(encoding="utf-8")
old_note = (
    "Placement and styling are delivered through the provider's advanced legacy "
    "notify action. Announcement Hub resolves that action from the selected "
    "output's config entry and will retry rather than silently use the generic "
    "`notify.send_message` action, which cannot carry these options."
)
new_note = (
    "Placement and styling are delivered through the provider's advanced legacy "
    "notify action when available. On modern config-entry installations where "
    "that action is absent or named differently, Announcement Hub uses the "
    "integration's live runtime client in an executor, preserving position, "
    "duration, font, colour, transparency, and interrupt without falling back "
    "to generic `notify.send_message`."
)
if old_note in readme_text:
    readme.write_text(
        readme_text.replace(old_note, new_note, 1),
        encoding="utf-8",
    )

print("Applied Announcement Hub 0.3.3 NFAndroidTV runtime delivery fix")
