"""Parse Mykolaivoblenergo schedules and build a UTC outage timeline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from typing import Any

from .const import EMERGENCY_QUEUE_TYPES, GPV_QUEUE_TYPE, TIME_ZONE


class SlotKind(StrEnum):
    """Half-hour state as published by the operator, in priority order."""

    ON = "on"
    POSSIBLE = "possible"
    OFF = "off"
    CONFIRMED = "confirmed"

    @property
    def is_outage(self) -> bool:
        return self in (SlotKind.OFF, SlotKind.CONFIRMED)


SOURCE_KINDS = {
    "ENABLE": SlotKind.ON,
    "PROBABLY_OFF": SlotKind.POSSIBLE,
    "OFF": SlotKind.OFF,
    "SURE_OFF": SlotKind.CONFIRMED,
}
PRIORITY = list(SlotKind)


@dataclass(frozen=True, kw_only=True)
class Queue:
    """A queue and the operator's live switch-off flag."""

    id: int
    name: str
    live_off: bool
    type_id: int = GPV_QUEUE_TYPE

    @property
    def label(self) -> str:
        """How the operator names the queue, e.g. "ГАВ 9"."""
        prefix = EMERGENCY_QUEUE_TYPES.get(self.type_id)
        return f"{prefix} {self.name}" if prefix else self.name


@dataclass(frozen=True, kw_only=True)
class SourceData:
    """Everything published by the operator at one point in time."""

    queues: dict[str, Queue]
    # Emergency (ГАВ/СГАВ) queues by id; they only have a live status.
    emergency: dict[int, Queue] = field(default_factory=dict)
    # Local date -> queue id -> 48 wall-clock half-hour slots.
    days: dict[date, dict[int, list[SlotKind]]] = field(default_factory=dict)
    updated: datetime | None = None
    fetched: datetime

    def slots(self, queue: str, day: date) -> list[SlotKind] | None:
        """Return a queue's slots, or None when no schedule is published."""
        if day not in self.days or queue not in self.queues:
            return None
        return self.days[day].get(self.queues[queue].id, [SlotKind.ON] * 48)


@dataclass(frozen=True, kw_only=True)
class Interval:
    """A continuous period of one kind in UTC."""

    start: datetime
    end: datetime
    kind: SlotKind


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Unexpected timestamp")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Timestamp without time zone")
    return result.astimezone(UTC)


def parse_queues(rows: list[dict[str, Any]]) -> dict[str, Queue]:
    """Return active schedule queues by name."""
    queues: dict[str, Queue] = {}
    for row in rows:
        if (
            type(row.get("id")) is not int
            or not isinstance(row.get("name"), str)
            or not row["name"]
            or row.get("type_id") != GPV_QUEUE_TYPE
        ):
            raise ValueError("Unexpected queue format")
        if row.get("deleted"):
            continue
        if row["name"] in queues:
            raise ValueError("Duplicate queue names")
        queues[row["name"]] = Queue(
            id=row["id"], name=row["name"], live_off=bool(row.get("enabled"))
        )
    return queues


def parse_emergency(rows: list[dict[str, Any]]) -> dict[int, Queue]:
    """Return active emergency queues (ГАВ, СГАВ) by id."""
    queues: dict[int, Queue] = {}
    for row in rows:
        if (
            type(row.get("id")) is not int
            or not isinstance(row.get("name"), str)
            or not row["name"]
            or row.get("type_id") not in EMERGENCY_QUEUE_TYPES
        ):
            raise ValueError("Unexpected emergency queue format")
        if not row.get("deleted"):
            queues[row["id"]] = Queue(
                id=row["id"],
                name=row["name"],
                live_off=bool(row.get("enabled")),
                type_id=row["type_id"],
            )
    return queues


def parse_time_series(rows: list[dict[str, Any]]) -> dict[int, int]:
    """Map source slot ids to wall-clock half-hour indexes 0..47."""
    slots = {}
    for row in rows:
        start = row.get("start")
        if (
            type(row.get("id")) is not int
            or not isinstance(start, str)
            or not re.fullmatch(r"([01]\d|2[0-3]):[03]0:00", start)
        ):
            raise ValueError("Unexpected time series format")
        slots[row["id"]] = int(start[:2]) * 2 + (start[3:5] == "30")
    if sorted(slots.values()) != list(range(48)):
        raise ValueError("Time series does not cover one day")
    return slots


def parse_source(
    queue_rows: list[dict[str, Any]],
    time_series_rows: list[dict[str, Any]],
    schedule_rows: list[dict[str, Any]],
    fetched: datetime,
    emergency_rows: list[dict[str, Any]] | None = None,
) -> SourceData:
    """Validate all responses; any unknown shape is rejected."""
    queues = parse_queues(queue_rows)
    emergency = parse_emergency(emergency_rows or [])
    slots = parse_time_series(time_series_rows)
    queue_ids = {queue.id for queue in queues.values()}
    days: dict[date, dict[int, list[SlotKind]]] = {}
    updated: datetime | None = None
    for schedule in schedule_rows:
        local = _timestamp(schedule.get("from")).astimezone(TIME_ZONE)
        if local.time() != time():
            raise ValueError("Schedule does not start at midnight")
        series = schedule.get("series")
        if not isinstance(series, list):
            raise ValueError("Unexpected schedule format")
        day = days.setdefault(local.date(), {})
        for item in series:
            if (
                not isinstance(item, dict)
                or item.get("time_series_id") not in slots
                or type(item.get("outage_queue_id")) is not int
                or item.get("type") not in SOURCE_KINDS
            ):
                raise ValueError("Unexpected schedule slot")
            if item["outage_queue_id"] not in queue_ids:
                continue
            kinds = day.setdefault(item["outage_queue_id"], [SlotKind.ON] * 48)
            index = slots[item["time_series_id"]]
            kind = SOURCE_KINDS[item["type"]]
            if PRIORITY.index(kind) > PRIORITY.index(kinds[index]):
                kinds[index] = kind
            # A missing timestamp must not discard an otherwise valid schedule.
            if isinstance(item.get("updated_at"), str):
                stamp = _timestamp(item["updated_at"])
                updated = stamp if updated is None else max(updated, stamp)
    return SourceData(
        queues=queues,
        emergency=emergency,
        days=days,
        updated=updated,
        fetched=fetched,
    )


def local_midnight(day: date) -> datetime:
    """Return the UTC instant of a local midnight."""
    return datetime.combine(day, time(), TIME_ZONE).astimezone(UTC)


def day_intervals(slots: list[SlotKind], day: date) -> list[Interval]:
    """Lay wall-clock slots on real UTC half hours, including 23/25-hour days."""
    cursor = local_midnight(day)
    end = local_midnight(day + timedelta(days=1))
    result: list[Interval] = []
    while cursor < end:
        local = cursor.astimezone(TIME_ZONE)
        kind = slots[local.hour * 2 + (local.minute >= 30)]
        following = cursor + timedelta(minutes=30)
        if result and result[-1].kind == kind and result[-1].end == cursor:
            result[-1] = Interval(start=result[-1].start, end=following, kind=kind)
        else:
            result.append(Interval(start=cursor, end=following, kind=kind))
        cursor = following
    return result


def outage_periods(intervals: list[Interval]) -> list[tuple[datetime, datetime]]:
    """Merge adjacent planned and confirmed outage intervals."""
    periods: list[tuple[datetime, datetime]] = []
    for interval in intervals:
        if not interval.kind.is_outage:
            continue
        if periods and periods[-1][1] == interval.start:
            periods[-1] = (periods[-1][0], interval.end)
        else:
            periods.append((interval.start, interval.end))
    return periods


def format_periods(periods: list[tuple[datetime, datetime]], empty: str) -> str:
    """Format periods in local time and keep the state within 255 characters."""
    if not periods:
        return empty
    parts = []
    for start, end in periods:
        end_local = end.astimezone(TIME_ZONE)
        end_text = "24:00" if end_local.time() == time() else f"{end_local:%H:%M}"
        parts.append(f"{start.astimezone(TIME_ZONE):%H:%M}–{end_text}")
    for count in range(len(parts), 0, -1):
        hidden = len(parts) - count
        text = "; ".join(parts[:count]) + (f"; … (+{hidden})" if hidden else "")
        if len(text) <= 255:
            return text
    return "…"


@dataclass(frozen=True, kw_only=True)
class Forecast:
    """Current and upcoming outage within the published horizon."""

    current: tuple[datetime, datetime | None] | None = None
    next: tuple[datetime, datetime | None] | None = None

    @property
    def restoration(self) -> datetime | None:
        window = self.current or self.next
        return window[1] if window else None


def forecast(source: SourceData, queue: str, now: datetime) -> Forecast | None:
    """Return None when today's schedule is unknown; never guess past the horizon."""
    today = now.astimezone(TIME_ZONE).date()
    intervals: list[Interval] = []
    day = today
    while (slots := source.slots(queue, day)) is not None:
        intervals += day_intervals(slots, day)
        day += timedelta(days=1)
    if not intervals:
        return None
    horizon = intervals[-1].end
    current = upcoming = None
    for start, end in outage_periods(intervals):
        window = (start, None if end == horizon else end)
        if start <= now < end:
            current = window
        elif start > now and upcoming is None:
            upcoming = window
    return Forecast(current=current, next=upcoming)
