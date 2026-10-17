"""Preserve effective config-entry values when a single section is reconfigured.

Entries may have their original setup stored in data and later changes stored in
options. Applying one form must not discard unrelated options or resurrect
values intentionally cleared from the original setup.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def merge_reconfiguration(
    data: Mapping[str, Any],
    options: Mapping[str, Any],
    working: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Produce changed data/options while preserving the untouched sections."""
    new_data = dict(data)
    new_options = dict(options)
    effective = {**new_data, **new_options}
    missing = object()
    for key in effective.keys() | working.keys():
        before = effective.get(key, missing)
        after = working.get(key, missing)
        if before == after:
            continue
        if after is missing:
            new_data.pop(key, None)
            new_options.pop(key, None)
        elif key in new_options or key not in new_data:
            new_options[key] = after
        else:
            new_data[key] = after
    return new_data, new_options
