"""Parsing, DST-aware timeline and forecast."""

from datetime import UTC, date, datetime, timedelta

import pytest

from custom_components.mykolaiv_outages.schedule import (
    SlotKind,
    day_intervals,
    forecast,
    format_periods,
    outage_periods,
    parse_source,
)

from .conftest import NOW

TODAY = date(2026, 10, 17)


def parse(queues, time_series, active, now=NOW):
    return parse_source(queues, time_series, active, now)


def text(source, queue, day=TODAY):
    slots = source.slots(queue, day)
    return format_periods(outage_periods(day_intervals(slots, day)), "none")


def schedule(day, series, offset=3):
    start = datetime(day.year, day.month, day.day, tzinfo=UTC) - timedelta(hours=offset)
    return {"from": start.isoformat().replace("+00:00", "Z"), "series": series}


def slot(queue_id, index, kind="OFF"):
    return {"outage_queue_id": queue_id, "time_series_id": index + 1, "type": kind}


def test_live_schedule(queues, time_series, active):
    source = parse(queues, time_series, active)
    assert set(source.queues) == {f"{a}.{b}" for a in range(1, 7) for b in (1, 2)}
    assert source.queues["1.1"].live_off is True
    assert source.queues["1.2"].live_off is False
    assert text(source, "1.1") == "10:30–12:00"
    assert text(source, "1.2") == "13:00–15:30"
    assert text(source, "2.1") == "16:30–19:00"
    assert text(source, "2.2") == "20:00–22:00"
    # Published day, queue without slots: power on all day.
    assert text(source, "4.2") == "none"
    assert source.slots("1.1", TODAY + timedelta(days=1)) is None
    possible = [
        (f"{item.start:%H:%M}", f"{item.end:%H:%M}")
        for item in day_intervals(source.slots("1.1", TODAY), TODAY)
        if item.kind is SlotKind.POSSIBLE
    ]
    assert possible == [("07:00", "07:30"), ("09:00", "09:30")]  # UTC
    assert source.updated is not None


def test_priority_and_unknown_queues(queues, time_series):
    series = [
        slot(14, 0, "PROBABLY_OFF"),
        slot(14, 0, "SURE_OFF"),
        slot(14, 0, "OFF"),
        slot(14, 1, "ENABLE"),
        slot(999, 2),
    ]
    source = parse(queues, time_series, [schedule(TODAY, series)])
    assert source.slots("1.1", TODAY)[:3] == [
        SlotKind.CONFIRMED,
        SlotKind.ON,
        SlotKind.ON,
    ]


def test_schedules_for_one_day_are_merged(queues, time_series):
    source = parse(
        queues,
        time_series,
        [schedule(TODAY, [slot(14, 0)]), schedule(TODAY, [slot(14, 47)])],
    )
    assert text(source, "1.1") == "00:00–00:30; 23:30–24:00"


def test_deleted_queues_are_hidden(queues, time_series):
    queues[0]["deleted"] = 1
    assert "1.1" not in parse(queues, time_series, []).queues


@pytest.mark.parametrize(
    "change",
    [
        {"from": "2026-10-16T22:00:00Z"},
        {"from": "2026-10-17"},
        {"from": None},
        {"series": None},
        {"series": [slot(14, 0, "MAYBE")]},
        {"series": [slot(14, 60)]},
        {"series": ["x"]},
    ],
)
def test_invalid_schedule(queues, time_series, change):
    row = {**schedule(TODAY, []), **change}
    with pytest.raises(ValueError):
        parse(queues, time_series, [row])


def test_invalid_reference_data(queues, time_series):
    with pytest.raises(ValueError, match="Time series"):
        parse(queues, time_series[:-1], [])
    with pytest.raises(ValueError, match="time series format"):
        parse(queues, [{**time_series[0], "start": "1:00"}, *time_series[1:]], [])
    with pytest.raises(ValueError, match="Duplicate"):
        parse([*queues, {**queues[0], "id": 500}], time_series, [])
    with pytest.raises(ValueError, match="queue format"):
        parse([{**queues[0], "type_id": 1}], time_series, [])


def test_dst_fall_back_day_has_25_hours(queues, time_series):
    day = date(2026, 10, 25)
    # 03:00–04:00 local occurs twice when clocks go back at 04:00 EEST.
    rows = [schedule(day, [slot(14, 6), slot(14, 7)])]
    source = parse(queues, time_series, rows, datetime(2026, 10, 25, 0, tzinfo=UTC))
    intervals = day_intervals(source.slots("1.1", day), day)
    assert intervals[-1].end - intervals[0].start == timedelta(hours=25)
    (start, end), *_ = outage_periods(intervals)
    assert end - start == timedelta(hours=2)


def test_dst_spring_forward_day_has_23_hours(queues, time_series):
    day = date(2026, 3, 29)
    rows = [schedule(day, [slot(14, 6), slot(14, 8)], offset=2)]
    source = parse(queues, time_series, rows, datetime(2026, 3, 29, 0, tzinfo=UTC))
    intervals = day_intervals(source.slots("1.1", day), day)
    assert intervals[-1].end - intervals[0].start == timedelta(hours=23)
    # 03:00 does not exist that night, only 04:00–04:30 remains.
    assert format_periods(outage_periods(intervals), "none") == "04:00–04:30"


def test_long_state_is_truncated():
    start = datetime(2026, 10, 16, 21, tzinfo=UTC)
    periods = [
        (start + timedelta(hours=i), start + timedelta(hours=i, minutes=30))
        for i in range(24)
    ]
    result = format_periods(periods, "none")
    assert len(result) <= 255
    assert result.endswith(")")


def test_forecast_current_outage(queues, time_series, active):
    source = parse(queues, time_series, active)
    result = forecast(source, "1.1", NOW)
    assert result.current == (
        datetime(2026, 10, 17, 7, 30, tzinfo=UTC),
        datetime(2026, 10, 17, 9, tzinfo=UTC),
    )
    assert result.next is None
    assert result.restoration == datetime(2026, 10, 17, 9, tzinfo=UTC)


def test_forecast_next_outage(queues, time_series, active):
    result = forecast(parse(queues, time_series, active), "2.2", NOW)
    assert result.current is None
    assert result.next == (
        datetime(2026, 10, 17, 17, tzinfo=UTC),
        datetime(2026, 10, 17, 19, tzinfo=UTC),
    )


def test_forecast_unknown_end_at_horizon(queues, time_series):
    source = parse(queues, time_series, [schedule(TODAY, [slot(14, 47)])])
    result = forecast(source, "1.1", NOW)
    assert result.next == (datetime(2026, 10, 17, 20, 30, tzinfo=UTC), None)
    assert result.restoration is None


def test_forecast_merges_across_midnight(queues, time_series):
    tomorrow = TODAY + timedelta(days=1)
    rows = [
        schedule(TODAY, [slot(14, 47)]),
        schedule(tomorrow, [slot(14, 0), slot(14, 1)]),
    ]
    result = forecast(parse(queues, time_series, rows), "1.1", NOW)
    assert result.next == (
        datetime(2026, 10, 17, 20, 30, tzinfo=UTC),
        datetime(2026, 10, 17, 22, tzinfo=UTC),
    )


def test_forecast_requires_today(queues, time_series):
    tomorrow = TODAY + timedelta(days=1)
    source = parse(queues, time_series, [schedule(tomorrow, [slot(14, 0)])])
    assert forecast(source, "1.1", NOW) is None
    assert forecast(parse(queues, time_series, []), "1.1", NOW) is None
