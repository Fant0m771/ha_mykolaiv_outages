"""Emergency queues, repairs, restored schedule events and diagnostics."""

from datetime import timedelta

from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.mykolaiv_outages.const import API_URL, DOMAIN
from custom_components.mykolaiv_outages.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.mykolaiv_outages.repairs import (
    async_create_fix_flow,
    changed_issue,
    missing_issue,
)
from custom_components.mykolaiv_outages.schedule import parse_source

from .conftest import NOW

HOUSE_URL = f"{API_URL}/addr/dom/25/outage-queue"


def add_entry(hass, queue, **data):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Арбузинка, вул. Свободи, 1 (черга {queue})",
        unique_id=queue,
        data={"queue": queue, "address": None, **data},
    )
    entry.add_to_hass(hass)
    return entry


async def setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    return {
        item.unique_id.removeprefix(f"{entry.entry_id}_"): item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }


def house(aioclient_mock, *queues):
    aioclient_mock.get(
        HOUSE_URL,
        json=[
            {"outage": {"id": id_, "name": name, "type_id": type_id}}
            for id_, name, type_id in queues
        ],
    )


async def test_emergency_power(hass, source):
    ids = await setup(hass, add_entry(hass, "1.1", emergency=[9, 11]))
    state = hass.states.get(ids["emergency_power"])
    # ГАВ 9 is switched off in the fixture.
    assert state.state == "off"
    assert state.attributes["queues"] == ["ГАВ 9", "СГАВ 1"]
    assert state.attributes["switched_off"] == ["ГАВ 9"]


async def test_emergency_power_on(hass, source):
    ids = await setup(hass, add_entry(hass, "1.1", emergency=[11]))
    assert hass.states.get(ids["emergency_power"]).state == "on"


async def test_manual_flow_with_emergency_queues(hass, source):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "queue"}
    )
    options = result["data_schema"].schema["emergency"].config["options"]
    assert options[0] == {"value": "1", "label": "ГАВ 1"}
    assert {"value": "11", "label": "СГАВ 1"} in options
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"queue": "2.2", "emergency": ["11", "9"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["emergency"] == [9, 11]
    assert result["data"]["house"] is None


async def test_house_follows_operator(hass, source):
    house(aioclient_mock := source, (16, "2.1", 3), (9, "9", 1))
    entry = add_entry(hass, "1.1", house=25, emergency=[])
    ids = await setup(hass, entry)
    # Emergency queues follow silently.
    assert entry.data["emergency"] == [9]
    assert hass.states.get(ids["emergency_power"]).state == "off"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, changed_issue(entry.entry_id))
    assert issue is not None and issue.is_fixable
    assert issue.translation_placeholders["new"] == "2.1"

    flow = await async_create_fix_flow(hass, issue.issue_id, issue.data)
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["step_id"] == "confirm"
    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.unique_id == "2.1"
    assert entry.title == "Арбузинка, вул. Свободи, 1 (черга 2.1)"
    # Same entities, now showing the new queue.
    assert hass.states.get(ids["today"]).state == "16:30–19:00"
    # The check after the reload finds the house in its queue again.
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, changed_issue(entry.entry_id))
        is None
    )
    assert aioclient_mock.call_count > 0


async def test_fix_flow_refuses_duplicate_queue(hass, source):
    house(source, (16, "2.1", 3))
    add_entry(hass, "2.1")
    entry = add_entry(hass, "1.1", house=25, emergency=[])
    await setup(hass, entry)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, changed_issue(entry.entry_id))
    flow = await async_create_fix_flow(hass, issue.issue_id, issue.data)
    flow.hass = hass
    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == "1.1"


async def test_house_check_failure_is_quiet(hass, source):
    source.get(HOUSE_URL, status=503)
    entry = add_entry(hass, "1.1", house=25, emergency=[9])
    await setup(hass, entry)
    assert entry.data["emergency"] == [9]
    assert not ir.async_get(hass).issues


async def test_missing_queue_issue(hass, source, freezer):
    entry = add_entry(hass, "9.9")
    ids = await setup(hass, entry)
    assert hass.states.get(ids["today"]).state == "unavailable"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, missing_issue(entry.entry_id))
    assert issue is not None
    assert issue.translation_placeholders["queue"] == "9.9"
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, missing_issue(entry.entry_id))
        is None
    )


async def test_schedule_event_after_restart(hass, source, hass_storage):
    entry = add_entry(hass, "1.1")
    key = f"{DOMAIN}.{entry.entry_id}.schedule"
    # Last run saw no schedule at all; today's was published while HA was off.
    hass_storage[key] = {
        "version": 1,
        "minor_version": 1,
        "key": key,
        "data": {"days": {}},
    }
    ids = await setup(hass, entry)
    await hass.async_block_till_done()
    state = hass.states.get(ids["schedule"])
    assert state.attributes["event_type"] == "schedule_published"
    assert state.attributes["day"] == "today"
    assert state.attributes["schedule"] == "10:30–12:00"


async def test_schedule_baseline_is_saved(hass, source, hass_storage, freezer):
    entry = add_entry(hass, "1.1")
    ids = await setup(hass, entry)
    assert hass.states.get(ids["schedule"]).state == "unknown"
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    stored = hass_storage[f"{DOMAIN}.{entry.entry_id}.schedule"]["data"]["days"]
    assert list(stored) == ["2026-10-17"]
    assert len(stored["2026-10-17"]) == 48
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert f"{DOMAIN}.{entry.entry_id}.schedule" not in hass_storage


async def test_diagnostics_redact_address(hass, source):
    entry = add_entry(
        hass, "1.1", address="Арбузинка, вул. Свободи, 1", house=25, emergency=[9]
    )
    source.get(HOUSE_URL, json=[])
    await setup(hass, entry)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["entry"]["address"] == "**REDACTED**"
    assert result["entry"]["house"] == "**REDACTED**"
    assert result["entry"]["title"] == "**REDACTED**"
    assert result["entry"]["queue"] == "1.1"
    slots = result["queue"]["slots"]["2026-10-17"]
    assert len(slots) == 48
    # 10:00 possible, 10:30–12:00 off, 12:00 possible.
    assert slots[20:25] == "?xxx?"
    assert result["emergency"] == {"9": {"label": "ГАВ 9", "live_off": True}}
    assert result["coordinator"]["last_update_success"] is True
    assert "Арбузинка" not in str(result)


def test_missing_updated_at_is_ignored(queues, time_series, active):
    for item in active[0]["series"]:
        item["updated_at"] = None
    source = parse_source(queues, time_series, active, NOW)
    assert source.updated is None
    assert source.slots("1.1", NOW.date()) is not None
