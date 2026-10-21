"""Safely register the bundled Announcement Hub dashboard card in Lovelace.

Resource registration is idempotent and never modifies YAML-managed resources.
Always load the storage resource collection before inspecting or writing it:
older Home Assistant versions can otherwise overwrite existing resources.
"""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

CARD_RESOURCE_PATH = "/announcement_hub/announcement-hub-card.js"


async def async_ensure_card_resource(hass: Any, version: str) -> bool:
    """Ensure the card's module URL is available to the Lovelace card picker.

    Return False when Lovelace is absent or its resources are YAML-managed.
    Existing manually registered modules are respected, not duplicated.
    """
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        _LOGGER.debug("Lovelace unavailable; dashboard card can be added manually")
        return False

    if isinstance(lovelace, dict):
        mode = lovelace.get("resource_mode", lovelace.get("mode"))
        resources = lovelace.get("resources")
    else:
        mode = getattr(lovelace, "resource_mode", getattr(lovelace, "mode", None))
        resources = getattr(lovelace, "resources", None)

    if mode != "storage" or resources is None:
        _LOGGER.debug("Lovelace resources not storage-managed; add the card manually")
        return False

    try:
        # Loading BEFORE async_items/async_create_item is mandatory for
        # compatibility with Home Assistant's previously lazy-loaded store.
        if getattr(resources, "loaded", True) is False:
            await resources.async_load()
            resources.loaded = True

        expected_url = f"{CARD_RESOURCE_PATH}?v={version}"
        for existing in resources.async_items():
            url = str(existing.get("url", ""))
            if url.split("?", 1)[0] != CARD_RESOURCE_PATH:
                continue
            if existing.get("res_type") != "module":
                _LOGGER.warning(
                    "Announcement Hub card resource exists but is not a JavaScript module; "
                    "change it to module under Settings > Dashboards > Resources"
                )
                return False
            if url == expected_url or "?" not in url:
                # Do not overwrite an existing manual resource.
                return True
            if url.startswith(CARD_RESOURCE_PATH + "?v="):
                # Update only versioned resources that this integration manages.
                await resources.async_update_item(
                    existing["id"],
                    {"res_type": "module", "url": expected_url},
                )
                _LOGGER.info("Updated Announcement Hub dashboard resource to %s", version)
            return True

        await resources.async_create_item(
            {"res_type": "module", "url": expected_url}
        )
        _LOGGER.info("Registered Announcement Hub dashboard card in Lovelace")
        return True
    except Exception:  # noqa: BLE001
        _LOGGER.exception(
            "Could not automatically register Announcement Hub dashboard card; "
            "add the resource %s manually",
            CARD_RESOURCE_PATH,
        )
        return False
