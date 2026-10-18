"""Load the bundled dashboard card in every frontend build."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILE = Path(__file__).parent / "frontend" / "mykolaiv-outages-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILE.name}"
DATA_CARD_URL = f"{DOMAIN}_card_url"


def card_digest() -> str:
    """Short hash of the card file, so an unreleased card change reaches browsers."""
    return hashlib.sha256(CARD_FILE.read_bytes()).hexdigest()[:8]


def _resources(hass: HomeAssistant) -> ResourceStorageCollection | None:
    """Return the dashboard resources when they are managed in the UI."""
    data = hass.data.get("lovelace")
    # A dict up to HA 2025.1, the LovelaceData dataclass afterwards.
    resources = (
        data.get("resources")
        if isinstance(data, dict)
        else getattr(data, "resources", None)
    )
    if isinstance(resources, ResourceStorageCollection):
        return resources
    return None


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card and load it on every dashboard."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), True)]
    )
    # The query makes browsers fetch the card again after an update; the hash
    # covers builds that share a version, e.g. installs from the develop branch.
    version = (await async_get_integration(hass, DOMAIN)).version
    digest = await hass.async_add_executor_job(card_digest)
    url = f"{CARD_URL}?v={version}-{digest}"
    hass.data[DATA_CARD_URL] = url
    if await async_ensure_resource(hass):
        return
    # Dashboards in YAML mode: scripts added to the page. They load
    # independently of the dashboard, so the Android app may render the
    # dashboard first; resources don't have that problem.
    add_extra_js_url(hass, url)
    # Browsers older than the frontend's "modern" cut-off (e.g. an Android
    # WebView below Chrome 131) get the legacy build, which loads only these.
    add_extra_js_url(hass, url, es5=True)


async def async_ensure_resource(hass: HomeAssistant) -> bool:
    """Add or update the card's dashboard resource; False in YAML mode."""
    if (url := hass.data.get(DATA_CARD_URL)) is None or (
        resources := _resources(hass)
    ) is None:
        return False
    await resources.async_get_info()  # loads the stored resources
    for item in resources.async_items():
        if item["url"].split("?")[0] != CARD_URL:
            continue
        if item["url"] != url:
            await resources.async_update_item(
                item["id"], {"res_type": "module", "url": url}
            )
        return True
    await resources.async_create_item({"res_type": "module", "url": url})
    _LOGGER.debug("Added dashboard resource %s", url)
    return True


async def async_remove_resource(hass: HomeAssistant) -> None:
    """Remove the card's dashboard resource."""
    if (resources := _resources(hass)) is None:
        return
    await resources.async_get_info()
    for item in list(resources.async_items()):
        if item["url"].split("?")[0] == CARD_URL:
            await resources.async_delete_item(item["id"])
