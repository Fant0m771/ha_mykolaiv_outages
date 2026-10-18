"""Base entity for one configured queue."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.loader import async_get_loaded_integration
from homeassistant.util import dt as dt_util

from .const import CONF_QUEUE, DOMAIN, MANUFACTURER, SITE_URL, STALE_AFTER
from .coordinator import MykolaivCoordinator


class MykolaivEntity(CoordinatorEntity[MykolaivCoordinator]):
    """Entities keep their identity when the queue is reconfigured."""

    _attr_has_entity_name = True
    # Entities showing the operator's live status need fresh data; schedule
    # entities keep the last published schedule for STALE_AFTER.
    _live = False

    def __init__(
        self,
        coordinator: MykolaivCoordinator,
        entry: ConfigEntry,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.entry = entry
        self.queue: str = entry.data[CONF_QUEUE]
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=f"Черга {self.queue}",
            configuration_url=SITE_URL,
            # Shows which build runs, e.g. a develop install (X.Y.Z.devN).
            sw_version=str(
                async_get_loaded_integration(coordinator.hass, DOMAIN).version
            ),
        )

    @property
    def available(self) -> bool:
        """The queue must still exist; old data only while it is still recent."""
        data = self.coordinator.data
        if data is None or self.queue not in data.queues:
            return False
        if self.coordinator.last_update_success:
            return True
        return not self._live and dt_util.utcnow() - data.fetched < STALE_AFTER
