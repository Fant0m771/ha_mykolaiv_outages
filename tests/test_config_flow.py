"""Address and manual queue selection, duplicates and reconfigure."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mykolaiv_outages.const import API_URL, DOMAIN

from .conftest import QUEUES_URL


def mock_address(aioclient_mock, house_queues):
    aioclient_mock.get(
        f"{API_URL}/addr/filii",
        json=[
            {"idfilial": 3, "fullname": "Баштанська дільниця"},
            {"idfilial": 2, "fullname": "Арбузинська дільниця"},
        ],
    )
    aioclient_mock.get(
        f"{API_URL}/addr/filii/2/ns",
        json=[{"idnaspunkt": 8, "naznaspunkt": "Арбузинка"}],
    )
    aioclient_mock.get(
        f"{API_URL}/addr/ns/8/street",
        json=[{"idstreet": 11, "nazstreet": "вул. Свободи"}],
    )
    aioclient_mock.get(
        f"{API_URL}/addr/street/11/dom", json=[{"iddom": 25, "nazdom": "1"}]
    )
    aioclient_mock.get(
        f"{API_URL}/addr/dom/25/outage-queue",
        json=[
            {"outage": {"name": name, "type_id": 3, "deleted": 0}}
            for name in house_queues
        ],
    )


async def walk_address(hass, flow_id):
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "branch"}
    )
    assert result["step_id"] == "branch"
    options = result["data_schema"].schema["branch"].config["options"]
    assert [item["label"] for item in options] == [
        "Арбузинська дільниця",
        "Баштанська дільниця",
    ]
    for step, value in [
        ("branch", "2"),
        ("settlement", "8"),
        ("street", "11"),
        ("house", "25"),
    ]:
        assert result["step_id"] == step
        result = await hass.config_entries.flow.async_configure(flow_id, {step: value})
    return result


async def start(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    return result["flow_id"]


async def test_address_single_queue(hass, aioclient_mock):
    mock_address(aioclient_mock, ["4.2"])
    result = await walk_address(hass, await start(hass))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Арбузинка, вул. Свободи, 1 (черга 4.2)"
    assert result["data"] == {
        "queue": "4.2",
        "address": "Арбузинка, вул. Свободи, 1",
    }
    assert result["result"].unique_id == "4.2"


async def test_address_several_queues(hass, aioclient_mock):
    mock_address(aioclient_mock, ["5.1", "4.2"])
    flow_id = await start(hass)
    result = await walk_address(hass, flow_id)
    assert result["step_id"] == "house_queue"
    result = await hass.config_entries.flow.async_configure(flow_id, {"queue": "5.1"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["queue"] == "5.1"


async def test_address_without_queue(hass, aioclient_mock):
    mock_address(aioclient_mock, [])
    result = await walk_address(hass, await start(hass))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_house_queue"


async def test_directory_offline_then_retry(hass, aioclient_mock):
    aioclient_mock.get(f"{API_URL}/addr/filii", status=503)
    flow_id = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "branch"}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    # No fields to fill, so submitting the empty form is the retry.
    assert result["data_schema"].schema == {}
    aioclient_mock.clear_requests()
    mock_address(aioclient_mock, ["4.2"])
    result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["step_id"] == "branch"
    assert result["errors"] == {}
    assert "branch" in result["data_schema"].schema


async def test_settlement_without_streets(hass, aioclient_mock):
    # Real case: Богданівка (Березанська дільниця) lists no streets.
    mock_address(aioclient_mock, ["4.2"])
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{API_URL}/addr/filii", json=[{"idfilial": 2, "fullname": "Дільниця"}]
    )
    aioclient_mock.get(
        f"{API_URL}/addr/filii/2/ns", json=[{"idnaspunkt": 8, "naznaspunkt": "Село"}]
    )
    aioclient_mock.get(f"{API_URL}/addr/ns/8/street", json=[])
    flow_id = await start(hass)
    await hass.config_entries.flow.async_configure(flow_id, {"next_step_id": "branch"})
    await hass.config_entries.flow.async_configure(flow_id, {"branch": "2"})
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"settlement": "8"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "empty_address"


async def test_manual_queue_and_duplicate(hass, source):
    flow_id = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "queue"}
    )
    options = result["data_schema"].schema["queue"].config["options"]
    assert [item["value"] for item in options][:3] == ["1.1", "1.2", "2.1"]
    result = await hass.config_entries.flow.async_configure(flow_id, {"queue": "1.1"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Черга 1.1"
    flow_id = await start(hass)
    await hass.config_entries.flow.async_configure(flow_id, {"next_step_id": "queue"})
    result = await hass.config_entries.flow.async_configure(flow_id, {"queue": "1.1"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_queue_offline(hass, aioclient_mock):
    aioclient_mock.get(QUEUES_URL, status=500)
    result = await hass.config_entries.flow.async_configure(
        await start(hass), {"next_step_id": "queue"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_keeps_entry(hass, source):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Черга 1.1",
        unique_id="1.1",
        data={"queue": "1.1", "address": None},
    )
    entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN, unique_id="2.2", data={"queue": "2.2", "address": None}
    )
    other.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "queue"}
    )
    result = await hass.config_entries.flow.async_configure(flow_id, {"queue": "2.2"})
    assert result["reason"] == "already_configured"
    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "queue"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"queue": "3.1"}
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "3.1"
    assert entry.title == "Черга 3.1"
    assert entry.data["queue"] == "3.1"
    await hass.async_block_till_done()
    for item in (entry, other):
        await hass.config_entries.async_unload(item.entry_id)
