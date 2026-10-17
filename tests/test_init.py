"""Real HA setup: entities, shared polling, clock updates and unload."""

from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.mykolaiv_outages.const import DOMAIN, SCAN_INTERVAL

from .conftest import ACTIVE_URL, NOW, QUEUES_URL, TIME_SERIES_URL


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
    }
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
    assert source.call_count == 3
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert source.call_count == 6
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
    aioclient_mock.get(QUEUES_URL, json=queues)
    aioclient_mock.get(TIME_SERIES_URL, json=time_series)
    aioclient_mock.get(ACTIVE_URL, json=active)
    entry = add_entry(hass, "1.1")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    aioclient_mock.clear_requests()
    aioclient_mock.get(QUEUES_URL, status=500)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert all(state.state == "unavailable" for state in states(hass, entry).values())
    aioclient_mock.clear_requests()
    aioclient_mock.get(QUEUES_URL, json=queues)
    aioclient_mock.get(TIME_SERIES_URL, json=time_series)
    aioclient_mock.get(ACTIVE_URL, json=active)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert states(hass, entry)["today"].state == "10:30–12:00"


async def test_removed_queue_is_unavailable(hass, source, queues):
    entry = add_entry(hass, "9.9")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert states(hass, entry)["today"].state == "unavailable"
