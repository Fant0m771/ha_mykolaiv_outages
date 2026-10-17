"""Outages as calendar events, for calendar triggers with an offset."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MykolaivConfigEntry
from .entity import MykolaivEntity
from .schedule import SlotKind, day_intervals

DESCRIPTION = EntityDescription(key="outages", translation_key="outages")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MykolaivConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([MykolaivCalendar(entry.runtime_data, entry, DESCRIPTION)])


class MykolaivCalendar(MykolaivEntity, CalendarEntity):
    """One event per outage in the published schedule."""

    def _events(self) -> list[CalendarEvent]:
        data = self.coordinator.data
        uk = self.hass.config.language == "uk"
        intervals = []
        for day in sorted(data.days):
            if (slots := data.slots(self.queue, day)) is not None:
                intervals += day_intervals(slots, day)
        horizon = intervals[-1].end if intervals else None
        # Merge planned and confirmed slots; remember if any slot is confirmed.
        windows: list[list] = []
        for item in intervals:
            if not item.kind.is_outage:
                continue
            confirmed = item.kind is SlotKind.CONFIRMED
            if windows and windows[-1][1] == item.start:
                windows[-1][1] = item.end
                windows[-1][2] |= confirmed
            else:
                windows.append([item.start, item.end, confirmed])
        events = []
        for start, end, confirmed in windows:
            notes = [
                ("Актуальне відключення" if uk else "Confirmed outage")
                if confirmed
                else ("Заплановане відключення" if uk else "Planned outage"),
                f"{'Черга' if uk else 'Queue'} {self.queue}",
            ]
            if end == horizon:
                notes.append(
                    "Кінець відключення ще не опубліковано"
                    if uk
                    else "The end is not published yet"
                )
            events.append(
                CalendarEvent(
                    start=dt_util.as_local(start),
                    end=dt_util.as_local(end),
                    summary="Відключення світла" if uk else "Power outage",
                    description="\n".join(notes),
                    uid=f"{self.queue}_{start.isoformat()}",
                )
            )
        return events

    @property
    def event(self) -> CalendarEvent | None:
        """The current outage, otherwise the next one."""
        now = dt_util.utcnow()
        return next((item for item in self._events() if item.end > now), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            item
            for item in self._events()
            if item.end > start_date and item.start < end_date
        ]
