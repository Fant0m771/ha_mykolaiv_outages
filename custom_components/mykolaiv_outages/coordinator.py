"""One shared poller for all configured queues."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MykolaivApi, MykolaivApiError
from .const import DOMAIN, SCAN_INTERVAL
from .schedule import SourceData

_LOGGER = logging.getLogger(__name__)


class MykolaivCoordinator(DataUpdateCoordinator[SourceData]):
    """Poll the operator once for every queue and tick at half-hour boundaries."""

    def __init__(self, hass: HomeAssistant, api: MykolaivApi) -> None:
        # Shared by all entries, so it must not belong to the first one.
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self.users = 0
        self._ready_lock = asyncio.Lock()
        self._unsub_clock: Callable[[], None] | None = async_track_utc_time_change(
            hass, self._handle_clock, minute=[0, 30], second=0
        )

    @callback
    def _handle_clock(self, _now: datetime) -> None:
        """Refresh time-dependent states without a network request."""
        self.async_update_listeners()

    async def _async_update_data(self) -> SourceData:
        try:
            return await self.api.async_get_source()
        except MykolaivApiError as err:
            raise UpdateFailed(str(err)) from err

    async def async_ensure_ready(self) -> None:
        """Coalesce concurrent first refreshes from several entries."""
        async with self._ready_lock:
            if self.data is None or not self.last_update_success:
                await self.async_refresh()
            if self.data is None or not self.last_update_success:
                raise ConfigEntryNotReady(
                    str(self.last_exception or "No data from the operator")
                ) from self.last_exception

    async def async_shutdown(self) -> None:
        if self._unsub_clock is not None:
            self._unsub_clock()
            self._unsub_clock = None
        await super().async_shutdown()


async def async_acquire(hass: HomeAssistant) -> MykolaivCoordinator:
    """Return the shared coordinator, creating it for the first entry."""
    coordinator: MykolaivCoordinator | None = hass.data.get(DOMAIN)
    if coordinator is None:
        coordinator = MykolaivCoordinator(
            hass, MykolaivApi(async_get_clientsession(hass))
        )
        hass.data[DOMAIN] = coordinator
    coordinator.users += 1
    try:
        await coordinator.async_ensure_ready()
    except BaseException:
        await async_release(hass, coordinator)
        raise
    return coordinator


async def async_release(hass: HomeAssistant, coordinator: MykolaivCoordinator) -> None:
    """Stop polling once the last entry is gone."""
    coordinator.users -= 1
    if coordinator.users == 0:
        if hass.data.get(DOMAIN) is coordinator:
            hass.data.pop(DOMAIN)
        await coordinator.async_shutdown()
