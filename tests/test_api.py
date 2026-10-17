"""Transport and response validation."""

import pytest
from aiohttp import ClientError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.mykolaiv_outages.api import MykolaivApi, MykolaivApiError
from custom_components.mykolaiv_outages.const import API_URL

from .conftest import QUEUES_URL, mock_source


def api(hass):
    return MykolaivApi(async_get_clientsession(hass))


async def test_source(hass, source):
    data = await api(hass).async_get_source()
    assert data.queues["1.1"].live_off is True
    assert data.emergency[9].label == "ГАВ 9"
    assert data.emergency[9].live_off is True
    assert data.emergency[11].label == "СГАВ 1"
    assert source.call_count == 5


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"status": 500}, "connection_error"),
        ({"exc": ClientError("offline")}, "connection_error"),
        ({"exc": TimeoutError()}, "connection_error"),
        ({"text": "<html>"}, "invalid"),
        ({"json": {"not": "a list"}}, "invalid"),
        ({"json": [1]}, "invalid"),
    ],
)
async def test_transport_errors(hass, aioclient_mock, kwargs, reason):
    aioclient_mock.get(QUEUES_URL, **kwargs)
    with pytest.raises(MykolaivApiError) as err:
        await api(hass).async_get_source()
    assert err.value.reason == reason


async def test_invalid_schedule_is_reported(
    hass, aioclient_mock, queues, time_series, emergency
):
    bad = [{"from": "bad", "series": []}]
    mock_source(aioclient_mock, queues, time_series, bad, emergency)
    with pytest.raises(MykolaivApiError) as err:
        await api(hass).async_get_source()
    assert err.value.reason == "invalid"


async def test_address_directory(hass, aioclient_mock):
    aioclient_mock.get(
        f"{API_URL}/addr/filii", json=[{"idfilial": 2, "fullname": " Дільниця "}]
    )
    aioclient_mock.get(
        f"{API_URL}/addr/filii/2/ns", json=[{"idnaspunkt": 7, "naznaspunkt": "Село"}]
    )
    aioclient_mock.get(
        f"{API_URL}/addr/ns/7/street", json=[{"idstreet": 11, "nazstreet": "вул. А"}]
    )
    aioclient_mock.get(
        f"{API_URL}/addr/street/11/dom", json=[{"iddom": 25, "nazdom": "1"}]
    )
    client = api(hass)
    assert await client.async_get_branches() == {2: "Дільниця"}
    assert await client.async_get_settlements(2) == {7: "Село"}
    assert await client.async_get_streets(7) == {11: "вул. А"}
    assert await client.async_get_houses(11) == {25: "1"}


async def test_bad_address_row(hass, aioclient_mock):
    aioclient_mock.get(f"{API_URL}/addr/filii", json=[{"idfilial": "2"}])
    with pytest.raises(MykolaivApiError, match="address"):
        await api(hass).async_get_branches()


async def test_house_queues(hass, aioclient_mock):
    aioclient_mock.get(
        f"{API_URL}/addr/dom/25/outage-queue",
        json=[
            {"outage": {"id": 22, "name": "4.2", "type_id": 3, "deleted": 0}},
            {"outage": {"id": 9, "name": "9", "type_id": 1, "enabled": 1}},
            {"outage": {"id": 14, "name": "1.1", "type_id": 3, "deleted": 1}},
            {"outage": {"id": 99, "name": "x", "type_id": 7}},
        ],
    )
    queues = await api(hass).async_get_house_queues(25)
    assert [(q.type_id, q.label, q.live_off) for q in queues] == [
        (3, "4.2", False),
        (1, "ГАВ 9", True),
    ]


async def test_bad_house_queue_row(hass, aioclient_mock):
    aioclient_mock.get(f"{API_URL}/addr/dom/25/outage-queue", json=[{"outage": None}])
    with pytest.raises(MykolaivApiError, match="house queue"):
        await api(hass).async_get_house_queues(25)
