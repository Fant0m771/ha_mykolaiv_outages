"""Power state from the operator's live flags and from the schedule."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MykolaivConfigEntry
from .const import CONF_EMERGENCY, CONF_HOUSE, TIME_ZONE
from .entity import MykolaivEntity
from .schedule import SlotKind

POWER = BinarySensorEntityDescription(
    key="power",
    translation_key="power",
    device_class=BinarySensorDeviceClass.POWER,
)
SCHEDULED_POWER = BinarySensorEntityDescription(
    key="scheduled_power",
    translation_key="scheduled_power",
    device_class=BinarySensorDeviceClass.POWER,
)
EMERGENCY_POWER = BinarySensorEntityDescription(
    key="emergency_power",
    translation_key="emergency_power",
    device_class=BinarySensorDeviceClass.POWER,
)
SITE = BinarySensorEntityDescription(
    key="site",
    translation_key="site",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MykolaivConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        MykolaivLivePower(coordinator, entry, POWER),
        MykolaivScheduledPower(coordinator, entry, SCHEDULED_POWER),
        MykolaivSite(coordinator, entry, SITE),
    ]
    # Address-bound entries can gain emergency queues later.
    if entry.data.get(CONF_HOUSE) or entry.data.get(CONF_EMERGENCY):
        entities.append(MykolaivEmergencyPower(coordinator, entry, EMERGENCY_POWER))
    async_add_entities(entities)


class MykolaivLivePower(MykolaivEntity, BinarySensorEntity):
    """On while the operator does not report the queue as switched off."""

    _live = True

    @property
    def is_on(self) -> bool:
        return not self.coordinator.data.queues[self.queue].live_off

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"source": "operator_status"}


class MykolaivScheduledPower(MykolaivEntity, BinarySensorEntity):
    """On while the published schedule has power for the current half hour."""

    @property
    def _slot(self) -> SlotKind | None:
        now = dt_util.utcnow().astimezone(TIME_ZONE)
        slots = self.coordinator.data.slots(self.queue, now.date())
        return slots[now.hour * 2 + (now.minute >= 30)] if slots else None

    @property
    def is_on(self) -> bool | None:
        slot = self._slot
        return None if slot is None else not slot.is_outage

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"source": "schedule", "slot": self._slot}


class MykolaivEmergencyPower(MykolaivEntity, BinarySensorEntity):
    """Off while one of the house's emergency (ГАВ/СГАВ) queues is switched off."""

    _live = True

    @property
    def _queues(self) -> list[Any]:
        # Read the entry each time: the house check may update the queue list.
        emergency = self.coordinator.data.emergency
        return [
            emergency[item]
            for item in self.entry.data.get(CONF_EMERGENCY, [])
            if item in emergency
        ]

    @property
    def is_on(self) -> bool | None:
        queues = self._queues
        if not queues:
            return None
        return not any(queue.live_off for queue in queues)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        queues = self._queues
        return {
            "source": "emergency",
            "queues": [queue.label for queue in queues],
            "switched_off": [queue.label for queue in queues if queue.live_off],
        }


class MykolaivSite(MykolaivEntity, BinarySensorEntity):
    """Whether the last request to the operator's site succeeded."""

    @property
    def available(self) -> bool:
        return self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"last_success": self.coordinator.data.fetched.isoformat()}
