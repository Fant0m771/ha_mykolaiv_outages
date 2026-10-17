"""Mykolaivoblenergo outage schedules for Home Assistant."""

from __future__ import annotations

from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .card import async_ensure_resource, async_register_card, async_remove_resource
from .const import CONF_HOUSE, DOMAIN, HOUSE_CHECK_INTERVAL
from .coordinator import (
    MykolaivCoordinator,
    async_acquire,
    async_release,
    schedule_store,
)
from .repairs import (
    async_check_house,
    async_check_queue,
    changed_issue,
    missing_issue,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.EVENT,
    Platform.SENSOR,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MykolaivConfigEntry = ConfigEntry[MykolaivCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card so it appears in the card picker."""
    if getattr(hass, "http", None) is None or "frontend" not in hass.config.components:
        return True
    await async_register_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MykolaivConfigEntry) -> bool:
    """Set up one queue on the shared coordinator."""
    # Again after the integration was removed and added back without a restart.
    await async_ensure_resource(hass)
    coordinator = await async_acquire(hass)
    entry.runtime_data = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await async_release(hass, coordinator)
        raise
    entry.async_on_unload(
        coordinator.async_add_listener(lambda: async_check_queue(hass, entry))
    )
    async_check_queue(hass, entry)
    if entry.data.get(CONF_HOUSE):

        @callback
        def check_house(_now: datetime | None = None) -> None:
            entry.async_create_background_task(
                hass, async_check_house(hass, entry), f"{DOMAIN} house check"
            )

        entry.async_on_unload(
            async_track_time_interval(hass, check_house, HOUSE_CHECK_INTERVAL)
        )
        check_house()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MykolaivConfigEntry) -> bool:
    """Unload a queue and stop polling after the last one."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await async_release(hass, entry.runtime_data)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: MykolaivConfigEntry) -> None:
    """Forget the stored schedule, repair issues and, last, the card resource."""
    await schedule_store(hass, entry.entry_id).async_remove()
    for issue in (missing_issue(entry.entry_id), changed_issue(entry.entry_id)):
        ir.async_delete_issue(hass, DOMAIN, issue)
    others = hass.config_entries.async_entries(DOMAIN)
    if not any(other.entry_id != entry.entry_id for other in others):
        await async_remove_resource(hass)
