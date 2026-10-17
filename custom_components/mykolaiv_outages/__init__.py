"""Mykolaivoblenergo outage schedules for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import MykolaivCoordinator, async_acquire, async_release

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type MykolaivConfigEntry = ConfigEntry[MykolaivCoordinator]


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
