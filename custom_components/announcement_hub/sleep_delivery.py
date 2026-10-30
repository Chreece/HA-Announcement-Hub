"""Pure sleep-time written-recipient selection, bounded to configured outputs.

An "integration:<domain>" token selects ONLY the concrete notification outputs
already enabled in Announcement Hub. Individual device tokens select only their
exact configured endpoints. No ambient Home Assistant devices are discovered
by the routing policy, and unknown/stale tokens do not broaden recipients.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

INTEGRATION_TOKEN_PREFIX = "integration:"
DEFAULT_SLEEP_NOTIFICATION_INTEGRATION = "mobile_app"


def sleep_notify_output_options(
    outputs: Sequence[Any],
    labels: Mapping[str, str] | None = None,
    *,
    integration_label: Callable[[str, int], str] | None = None,
    device_label: Callable[[str], str] | None = None,
) -> list[dict[str, str]]:
    """Integration/all-devices first, then individual supported devices."""
    labels = labels or {}
    groups: dict[str, list[str]] = {}
    known: dict[str, Any] = {}
    for output in outputs:
        known.setdefault(output.ref, output)
        if output.integration:
            groups.setdefault(str(output.integration), []).append(output.ref)

    options: list[dict[str, str]] = []
    for integration in sorted(groups):
        options.append({
            "value": f"{INTEGRATION_TOKEN_PREFIX}{integration}",
            "label": (
                integration_label(integration, len(set(groups[integration])))
                if integration_label else
                f"Integration · {integration.replace('_', ' ').title()}"
                f" — all devices ({len(set(groups[integration]))})"
            ),
        })
    for ref, output in sorted(
        known.items(), key=lambda item: (
            str(item[1].integration or "").casefold(),
            str(labels.get(item[0], item[0])).casefold(),
        )
    ):
        options.append({
            "value": ref,
            "label": (
                device_label(labels.get(ref, ref))
                if device_label else f"Device · {labels.get(ref, ref)}"
            ),
        })
    return options


def sleep_notify_selected_refs(
    outputs: Sequence[Any],
    selection: Sequence[str] | None,
) -> tuple[str, ...]:
    """Expand selected groups to eligible, explicitly configured outputs.

    None (setting absent on older installations) retains historical mobile
    written fallback. [] (explicit empty choice) means nobody may receive it.
    """
    if selection is None:
        selection = (f"{INTEGRATION_TOKEN_PREFIX}{DEFAULT_SLEEP_NOTIFICATION_INTEGRATION}",)
    elif isinstance(selection, str):
        selection = (selection,)

    selected = set(str(value) for value in selection)
    result = [
        output.ref
        for output in outputs
        if output.ref in selected
        or (
            output.integration
            and f"{INTEGRATION_TOKEN_PREFIX}{output.integration}" in selected
        )
    ]
    return tuple(dict.fromkeys(result))
