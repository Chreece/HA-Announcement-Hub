"""Provider-aware notification tap actions.

The Home Assistant Companion Apps use different payload keys for opening the
same target when the notification is tapped:
- Android: data.clickAction
- iOS / macOS: data.url

NFAndroidTV's interactive overlay does not implement URL click actions.
Unknown/general notify integrations must not receive provider-specific keys.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def mobile_click_action_data(
    provider_data: Mapping[str, Any],
    *,
    click_action: str | None,
    integration: str | None,
    service: str | None = None,
) -> dict[str, Any]:
    """Add mobile-app tap URL keys only for known compatible destinations.

    Call this independently for every physical notification output after
    merging the provider profile and job's notify_data. Explicit click_action
    overrides conflicting nested keys, and existing data remains untouched.
    """
    data = dict(provider_data)
    if not click_action or not click_action.strip():
        return data

    # Preserve provider identity as authoritative; a legacy notify service
    # with no registry match can still identify Companion App by its name.
    mobile = integration == "mobile_app" or (
        integration is None
        and isinstance(service, str)
        and (service == "notify.mobile_app" or service.startswith("notify.mobile_app_"))
    )
    if not mobile:
        return data

    target = click_action.strip()
    data["clickAction"] = target
    data["url"] = target
    return data
