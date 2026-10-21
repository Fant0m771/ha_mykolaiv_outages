"""Real HA setup: entities, shared polling, clock updates and unload."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.mykolaiv_outages.const import (
    DOMAIN,
    SCAN_INTERVAL,
    TIME_ZONE,
)

from .conftest import NOW, QUEUES_URL, emergency_rows, mock_source


def add_entry(hass, queue):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Черга {queue}",
        unique_id=queue,
        data={"queue": queue, "address": None},
    )
    entry.add_to_hass(hass)
    return entry


def states(hass, entry):
    registry = er.async_get(hass)
    return {
        item.unique_id.removeprefix(f"{entry.entry_id}_"): hass.states.get(
            item.entity_id
        )
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }


async def test_entities(hass, source):
    entry = add_entry(hass, "1.1")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = states(hass, entry)
    assert set(result) == {
        "power",
        "scheduled_power",
        "today",
        "tomorrow",
        "next_outage",
        "restoration",
        "last_update",
        "outages",
        "schedule",
        "site",
    }
    assert result["site"].state == "on"
    # Manual entries without emergency queues have no emergency sensor.
    assert "emergency_power" not in result
    assert result["power"].state == "off"
    assert result["scheduled_power"].state == "off"
    assert result["scheduled_power"].attributes["slot"] == "off"
    assert result["today"].state == "10:30–12:00"
    assert result["today"].attributes["outages"] == [{"start": "10:30", "end": "12:00"}]
    assert result["today"].attributes["periods"][0] == {
        "start": "10:00",
        "end": "10:30",
        "kind": "possible",
    }
    assert result["tomorrow"].state == "unknown"
    assert result["tomorrow"].attributes["published"] is False
    # Today has a schedule, so schedules are in effect even for unpublished days.
    assert result["tomorrow"].attributes["schedules_active"] is True
    assert result["next_outage"].state == "unknown"
    assert result["restoration"].state == "2026-10-17T09:00:00+00:00"
    assert result["restoration"].attributes["outage"] == "current"
    assert result["last_update"].state != "unavailable"


async def test_power_on_queue(hass, source):
    entry = add_entry(hass, "2.2")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = states(hass, entry)
    assert result["power"].state == "on"
    assert result["scheduled_power"].state == "on"
    assert result["next_outage"].state == "2026-10-17T17:00:00+00:00"
    assert result["restoration"].attributes["outage"] == "next"


async def test_clock_updates_states(hass, source, freezer):
    entry = add_entry(hass, "1.1")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.move_to(NOW + timedelta(hours=1))
    async_fire_time_changed(hass, NOW + timedelta(hours=1))
    await hass.async_block_till_done()
    assert states(hass, entry)["scheduled_power"].state == "on"


async def test_shared_polling_and_unload(hass, source, freezer):
    first, second = add_entry(hass, "1.1"), add_entry(hass, "2.2")
    # Setting up the integration loads every entry of the domain.
    assert await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()
    assert second.state is ConfigEntryState.LOADED
    assert first.runtime_data is second.runtime_data
    assert source.call_count == 5
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert source.call_count == 10
    assert await hass.config_entries.async_unload(first.entry_id)
    assert DOMAIN in hass.data
    assert states(hass, second)["power"].state == "on"
    assert await hass.config_entries.async_unload(second.entry_id)
    assert DOMAIN not in hass.data


async def test_setup_retry_when_offline(hass, aioclient_mock):
    aioclient_mock.get(QUEUES_URL, status=503)
    entry = add_entry(hass, "1.1")
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert DOMAIN not in hass.data


async def test_failure_and_recovery(
    hass, aioclient_mock, queues, time_series, active, freezer
):
    mock_source(aioclient_mock, queues, time_series, active, emergency_rows())
    entry = add_entry(hass, "1.1")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    aioclient_mock.clear_requests()
    aioclient_mock.get(QUEUES_URL, status=500)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    result = states(hass, entry)
    # The live status is gone at once; the published schedule stays, marked.
    assert result["power"].state == "unavailable"
    assert result["site"].state == "off"
    assert result["today"].state == "10:30–12:00"
    assert result["today"].attributes["cached"] is True
    assert result["restoration"].state != "unavailable"
    assert result["outages"].attributes["cached"] is True
    # Hours later the site is still down: the schedule of today is still there.
    freezer.tick(timedelta(hours=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    result = states(hass, entry)
    assert result["today"].state == "10:30–12:00"
    assert result["scheduled_power"].state != "unavailable"
    aioclient_mock.clear_requests()
    mock_source(aioclient_mock, queues, time_series, active, emergency_rows())
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    result = states(hass, entry)
    assert result["site"].state == "on"
    assert result["power"].state != "unavailable"
    assert result["today"].attributes["cached"] is False


async def test_cached_schedule_ends_with_its_last_day(
    hass, aioclient_mock, queues, time_series, active, freezer
):
    mock_source(aioclient_mock, queues, time_series, active, emergency_rows())
    entry = add_entry(hass, "1.1")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    published = sorted(entry.runtime_data.data.days)
    aioclient_mock.clear_requests()
    aioclient_mock.get(QUEUES_URL, status=500)
    # Shortly before the end of the last published day the schedule is kept.
    last = datetime.combine(published[-1], datetime.min.time(), TIME_ZONE)
    freezer.move_to(last + timedelta(hours=23, minutes=50))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    result = states(hass, entry)
    assert result["today"].state != "unavailable"
    assert result["today"].attributes["date"] == published[-1].isoformat()
    # Once that day is over nothing is left to show; dates are not shifted.
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    result = states(hass, entry)
    assert result["today"].state == "unavailable"
    assert result["outages"].state == "unavailable"
    assert result["site"].state == "off"


async def test_no_active_schedules(hass, aioclient_mock, queues, time_series):
    """The operator applies no schedule to any queue: days say so explicitly."""
    mock_source(aioclient_mock, queues, time_series, [], emergency_rows())
    entry = add_entry(hass, "1.1")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = states(hass, entry)
    for key in ("today", "tomorrow"):
        assert result[key].state == "unknown"
        assert result[key].attributes["published"] is False
        assert result[key].attributes["schedules_active"] is False
    assert result["scheduled_power"].state == "unknown"


async def test_removed_queue_is_unavailable(hass, source, queues):
    entry = add_entry(hass, "9.9")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert states(hass, entry)["today"].state == "unavailable"


async def test_device_shows_installed_version(hass, source):
    """The device page tells a develop install (X.Y.Z.devN) from a release."""
    manifest = (
        Path(__file__).parents[1] / "custom_components" / DOMAIN / "manifest.json"
    )
    version = json.loads(manifest.read_text())["version"]
    entry = add_entry(hass, "1.1")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # async_get_device is deprecated on current HA; this works on 2025.1 too.
    [device] = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert device.sw_version == version
    assert await hass.config_entries.async_unload(entry.entry_id)
