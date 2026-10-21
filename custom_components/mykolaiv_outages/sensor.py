"""Schedule, forecast and update sensors."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MykolaivConfigEntry
from .const import TIME_ZONE
from .entity import MykolaivEntity
from .schedule import day_intervals, forecast, format_periods, outage_periods

DAY_DESCRIPTIONS = (
    SensorEntityDescription(key="today", translation_key="today"),
    SensorEntityDescription(key="tomorrow", translation_key="tomorrow"),
)
FORECAST_DESCRIPTIONS = (
    SensorEntityDescription(
        key="next_outage",
        translation_key="next_outage",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="restoration",
        translation_key="restoration",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)
UPDATED_DESCRIPTION = SensorEntityDescription(
    key="last_update",
    translation_key="last_update",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MykolaivConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(MykolaivDaySensor(coordinator, entry, item) for item in DAY_DESCRIPTIONS),
            *(
                MykolaivForecastSensor(coordinator, entry, item)
                for item in FORECAST_DESCRIPTIONS
            ),
            MykolaivUpdateSensor(coordinator, entry, UPDATED_DESCRIPTION),
        ]
    )


def _clock(value: datetime, end: bool = False) -> str:
    local = value.astimezone(TIME_ZONE)
    return "24:00" if end and local.time() == time() else f"{local:%H:%M}"


class MykolaivDaySensor(MykolaivEntity, SensorEntity):
    """All outage periods of one day; unknown until the operator publishes it."""

    @property
    def _day(self) -> date:
        today = dt_util.utcnow().astimezone(TIME_ZONE).date()
        return today + timedelta(days=self.entity_description.key == "tomorrow")

    @property
    def native_value(self) -> str | None:
        day = self._day
        slots = self.coordinator.data.slots(self.queue, day)
        if slots is None:
            return None
        empty = "Без відключень" if self.hass.config.language == "uk" else "No outages"
        return format_periods(outage_periods(day_intervals(slots, day)), empty)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        day = self._day
        slots = self.coordinator.data.slots(self.queue, day)
        intervals = day_intervals(slots, day) if slots else []
        return {
            "queue": self.queue,
            "cached": self.cached,
            "date": day.isoformat(),
            "published": slots is not None,
            "outages": [
                {"start": _clock(start), "end": _clock(end, True)}
                for start, end in outage_periods(intervals)
            ],
            "periods": [
                {
                    "start": _clock(item.start),
                    "end": _clock(item.end, True),
                    "kind": item.kind.value,
                }
                for item in intervals
                if item.kind.value != "on"
            ],
        }


class MykolaivForecastSensor(MykolaivEntity, SensorEntity):
    """Next outage start and expected restoration within the published horizon."""

    @property
    def native_value(self) -> datetime | None:
        result = forecast(self.coordinator.data, self.queue, dt_util.utcnow())
        if result is None:
            return None
        if self.entity_description.key == "next_outage":
            return result.next[0] if result.next else None
        return result.restoration

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = forecast(self.coordinator.data, self.queue, dt_util.utcnow())
        context = "unknown"
        if result is not None:
            context = "current" if result.current else "next" if result.next else "none"
        return {"queue": self.queue, "outage": context, "cached": self.cached}


class MykolaivUpdateSensor(MykolaivEntity, SensorEntity):
    """When the operator last changed the published schedule."""

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.data.updated

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "fetched": self.coordinator.data.fetched.isoformat(),
            "cached": self.cached,
        }
