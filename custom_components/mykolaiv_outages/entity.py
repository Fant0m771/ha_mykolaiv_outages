"""Base entity for one configured queue."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_QUEUE, DOMAIN, MANUFACTURER, SITE_URL
from .coordinator import MykolaivCoordinator


class MykolaivEntity(CoordinatorEntity[MykolaivCoordinator]):
    """Entities keep their identity when the queue is reconfigured."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MykolaivCoordinator,
        entry: ConfigEntry,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.queue: str = entry.data[CONF_QUEUE]
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=f"Черга {self.queue}",
            configuration_url=SITE_URL,
        )

    @property
    def available(self) -> bool:
        """The queue must still exist at the operator."""
        return super().available and self.queue in self.coordinator.data.queues
