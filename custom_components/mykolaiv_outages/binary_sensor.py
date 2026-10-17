"""Power state from the operator's live flag and from the schedule."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MykolaivConfigEntry
from .const import TIME_ZONE
from .entity import MykolaivEntity

DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    BinarySensorEntityDescription(
        key="scheduled_power",
        translation_key="scheduled_power",
        device_class=BinarySensorDeviceClass.POWER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MykolaivConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        MykolaivPowerSensor(entry.runtime_data, entry, description)
        for description in DESCRIPTIONS
    )


class MykolaivPowerSensor(MykolaivEntity, BinarySensorEntity):
    """On while the queue has power."""

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if self.entity_description.key == "power":
            # The operator raises this flag while the queue is switched off.
            return not data.queues[self.queue].live_off
        now = dt_util.utcnow().astimezone(TIME_ZONE)
        slots = data.slots(self.queue, now.date())
        if slots is None:
            return None
        return not slots[now.hour * 2 + (now.minute >= 30)].is_outage

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        if self.entity_description.key == "power":
            return {"source": "operator_status"}
        now = dt_util.utcnow().astimezone(TIME_ZONE)
        slots = self.coordinator.data.slots(self.queue, now.date())
        return {
            "source": "schedule",
            "slot": slots[now.hour * 2 + (now.minute >= 30)] if slots else None,
        }
