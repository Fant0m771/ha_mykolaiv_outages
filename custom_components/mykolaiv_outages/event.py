"""Events when the operator publishes or changes a day's schedule."""

from __future__ import annotations

from datetime import date, timedelta

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MykolaivConfigEntry
from .const import TIME_ZONE
from .entity import MykolaivEntity
from .schedule import SlotKind, day_intervals, format_periods, outage_periods

DESCRIPTION = EventEntityDescription(
    key="schedule",
    translation_key="schedule",
    event_types=["schedule_published", "schedule_changed"],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MykolaivConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([MykolaivScheduleEvent(entry.runtime_data, entry, DESCRIPTION)])


class MykolaivScheduleEvent(MykolaivEntity, EventEntity):
    """Compare each refresh with the last one; the first refresh is the baseline."""

    _seen: dict[date, list[SlotKind]] | None = None

    def _snapshot(self) -> dict[date, list[SlotKind]] | None:
        if not self.available:
            return None
        data = self.coordinator.data
        return {
            day: list(slots)
            for day in data.days
            if (slots := data.slots(self.queue, day)) is not None
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._seen = self._snapshot()

    @callback
    def _handle_coordinator_update(self) -> None:
        current = self._snapshot()
        if current is not None and self._seen is not None:
            today = dt_util.utcnow().astimezone(TIME_ZONE).date()
            labels = {today: "today", today + timedelta(days=1): "tomorrow"}
            empty = (
                "Без відключень" if self.hass.config.language == "uk" else "No outages"
            )
            for day, slots in sorted(current.items()):
                previous = self._seen.get(day)
                if day not in labels or previous == slots:
                    continue
                self._trigger_event(
                    "schedule_published" if previous is None else "schedule_changed",
                    {
                        "day": labels[day],
                        "date": day.isoformat(),
                        "schedule": format_periods(
                            outage_periods(day_intervals(slots, day)), empty
                        ),
                    },
                )
                # Write each event so that none is lost when two arrive together.
                self.async_write_ha_state()
        if current is not None:
            self._seen = current
        super()._handle_coordinator_update()
