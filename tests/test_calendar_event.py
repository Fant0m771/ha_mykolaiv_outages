"""Calendar events and schedule published/changed events."""

import copy
from datetime import UTC, datetime, timedelta

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.mykolaiv_outages.const import DOMAIN, SCAN_INTERVAL

from .conftest import ACTIVE_URL, NOW, QUEUES_URL, TIME_SERIES_URL

TOMORROW = {
    "from": "2026-10-17T21:00:00.000000Z",
    "series": [
        {"outage_queue_id": 14, "time_series_id": 13, "type": "OFF"},
        {"outage_queue_id": 14, "time_series_id": 14, "type": "OFF"},
    ],
}


async def setup(hass, queue="1.1"):
    await hass.config.async_set_time_zone("Europe/Kyiv")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Черга {queue}",
        unique_id=queue,
        data={"queue": queue, "address": None},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    return {
        item.unique_id.removeprefix(f"{entry.entry_id}_"): item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }


def remock(aioclient_mock, queues, time_series, active):
    aioclient_mock.clear_requests()
    aioclient_mock.get(QUEUES_URL, json=queues)
    aioclient_mock.get(TIME_SERIES_URL, json=time_series)
    aioclient_mock.get(ACTIVE_URL, json=active)


async def refresh(hass, freezer):
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_calendar(hass, source):
    ids = await setup(hass)
    state = hass.states.get(ids["outages"])
    # 11:00 in Kyiv is inside the 10:30–12:00 outage.
    assert state.state == "on"
    assert state.attributes["message"] == "Power outage"
    result = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": ids["outages"],
            "start_date_time": NOW - timedelta(hours=12),
            "end_date_time": NOW + timedelta(hours=24),
        },
        blocking=True,
        return_response=True,
    )
    (event,) = result[ids["outages"]]["events"]
    assert event["start"] == datetime(2026, 10, 17, 10, 30).isoformat() + "+03:00"
    assert event["end"] == datetime(2026, 10, 17, 12, 0).isoformat() + "+03:00"
    assert event["description"] == "Planned outage\nQueue 1.1"


async def test_calendar_unknown_end_and_confirmed(
    hass, aioclient_mock, queues, time_series
):
    hass.config.language = "uk"
    today = {
        "from": "2026-10-16T21:00:00.000000Z",
        "series": [
            {"outage_queue_id": 14, "time_series_id": 47, "type": "OFF"},
            {"outage_queue_id": 14, "time_series_id": 48, "type": "SURE_OFF"},
        ],
    }
    remock(aioclient_mock, queues, time_series, [today])
    ids = await setup(hass)
    state = hass.states.get(ids["outages"])
    assert state.state == "off"
    assert state.attributes["message"] == "Відключення світла"
    assert state.attributes["description"] == (
        "Актуальне відключення\nЧерга 1.1\nКінець відключення ще не опубліковано"
    )
    assert state.attributes["end_time"] == "2026-10-18 00:00:00"


async def test_schedule_events(
    hass, aioclient_mock, queues, time_series, active, freezer
):
    remock(aioclient_mock, queues, time_series, active)
    ids = await setup(hass)
    entity_id = ids["schedule"]
    # The first refresh is only the baseline.
    assert hass.states.get(entity_id).state == "unknown"

    remock(aioclient_mock, queues, time_series, [*active, TOMORROW])
    await refresh(hass, freezer)
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "schedule_published"
    assert state.attributes["day"] == "tomorrow"
    assert state.attributes["date"] == "2026-10-18"
    assert state.attributes["schedule"] == "06:00–07:00"
    published = state.state

    # Nothing new: no event.
    await refresh(hass, freezer)
    assert hass.states.get(entity_id).state == published

    changed = copy.deepcopy(active)
    changed[0]["series"].append(
        {"outage_queue_id": 14, "time_series_id": 40, "type": "SURE_OFF"}
    )
    remock(aioclient_mock, queues, time_series, [*changed, TOMORROW])
    freezer.tick(timedelta(seconds=1))
    await refresh(hass, freezer)
    state = hass.states.get(entity_id)
    assert state.state != published
    assert state.attributes["event_type"] == "schedule_changed"
    assert state.attributes["day"] == "today"
    assert state.attributes["schedule"] == "10:30–12:00; 19:30–20:00"


async def test_no_event_for_other_queues_or_clock(
    hass, aioclient_mock, queues, time_series, active, freezer
):
    remock(aioclient_mock, queues, time_series, active)
    ids = await setup(hass, "4.2")
    other = copy.deepcopy(active)
    other[0]["series"].append(
        {"outage_queue_id": 14, "time_series_id": 40, "type": "OFF"}
    )
    remock(aioclient_mock, queues, time_series, other)
    await refresh(hass, freezer)
    freezer.move_to(datetime(2026, 10, 17, 8, 30, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ids["schedule"]).state == "unknown"
