"""Dashboard card registration."""

import json
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.setup import async_setup_component

from custom_components.mykolaiv_outages.card import CARD_FILE, CARD_URL
from custom_components.mykolaiv_outages.const import DOMAIN

from .test_init import add_entry

VERSION = json.loads((CARD_FILE.parents[1] / "manifest.json").read_text())["version"]
URL = f"{CARD_URL}?v={VERSION}"


@pytest.fixture
def frontend(hass):
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    hass.config.components.add("frontend")
    with patch("custom_components.mykolaiv_outages.card.add_extra_js_url") as add_js:
        yield add_js


def resources(hass):
    data = hass.data["lovelace"]
    collection = data["resources"] if isinstance(data, dict) else data.resources
    return collection


def card_items(hass):
    return [
        item
        for item in resources(hass).async_items()
        if item["url"].startswith(CARD_URL)
    ]


async def test_card_is_added_as_dashboard_resource(hass, frontend):
    assert await async_setup_component(hass, "lovelace", {})
    assert await async_setup_component(hass, DOMAIN, {})
    assert [(i["type"], i["url"]) for i in card_items(hass)] == [("module", URL)]
    frontend.assert_not_called()


async def test_card_resource_is_updated_not_duplicated(hass, frontend):
    assert await async_setup_component(hass, "lovelace", {})
    collection = resources(hass)
    await collection.async_get_info()
    await collection.async_create_item(
        {"res_type": "module", "url": f"{CARD_URL}?v=0.4.2"}
    )
    other = await collection.async_create_item(
        {"res_type": "module", "url": "/hacsfiles/other/other.js"}
    )
    assert await async_setup_component(hass, DOMAIN, {})
    assert [i["url"] for i in card_items(hass)] == [URL]
    assert other in collection.async_items()


async def test_card_falls_back_to_page_scripts(hass, frontend):
    """Without UI-managed resources (YAML mode) the page loads the card."""
    assert await async_setup_component(hass, DOMAIN, {})
    (paths,), _ = hass.http.async_register_static_paths.call_args
    assert paths[0].url_path == CARD_URL
    assert paths[0].path == str(CARD_FILE)
    assert CARD_FILE.is_file()
    assert frontend.call_args_list == [call(hass, URL), call(hass, URL, es5=True)]


async def test_card_resource_removed_with_last_entry(hass, frontend, source):
    assert await async_setup_component(hass, "lovelace", {})
    first, second = add_entry(hass, "1.1"), add_entry(hass, "4.2")
    assert await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(first.entry_id)
    assert len(card_items(hass)) == 1
    await hass.config_entries.async_remove(second.entry_id)
    assert card_items(hass) == []

    # Added back without a restart: the resource returns.
    third = add_entry(hass, "1.1")
    assert await hass.config_entries.async_setup(third.entry_id)
    await hass.async_block_till_done()
    assert [i["url"] for i in card_items(hass)] == [URL]
    assert await hass.config_entries.async_unload(third.entry_id)


async def test_card_skipped_without_frontend(hass):
    with patch("custom_components.mykolaiv_outages.card.add_extra_js_url") as add_js:
        assert await async_setup_component(hass, DOMAIN, {})
    add_js.assert_not_called()
