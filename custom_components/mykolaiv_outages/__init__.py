"""Mykolaivoblenergo outage schedules for Home Assistant."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import MykolaivCoordinator, async_acquire, async_release

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.EVENT,
    Platform.SENSOR,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
CARD_FILE = Path(__file__).parent / "frontend" / "mykolaiv-outages-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILE.name}"

type MykolaivConfigEntry = ConfigEntry[MykolaivCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card so it appears in the card picker."""
    if getattr(hass, "http", None) is None or "frontend" not in hass.config.components:
        return True
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), True)]
    )
    # The version query makes browsers fetch the card again after an update.
    version = (await async_get_integration(hass, DOMAIN)).version
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MykolaivConfigEntry) -> bool:
    """Set up one queue on the shared coordinator."""
    coordinator = await async_acquire(hass)
    entry.runtime_data = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await async_release(hass, coordinator)
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MykolaivConfigEntry) -> bool:
    """Unload a queue and stop polling after the last one."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await async_release(hass, entry.runtime_data)
    return unloaded
