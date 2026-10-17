"""Dashboard card registration."""

import json
from unittest.mock import AsyncMock, MagicMock, call, patch

from homeassistant.setup import async_setup_component

from custom_components.mykolaiv_outages import CARD_FILE, CARD_URL
from custom_components.mykolaiv_outages.const import DOMAIN


async def test_card_is_registered_with_frontend(hass):
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    hass.config.components.add("frontend")
    with patch("custom_components.mykolaiv_outages.add_extra_js_url") as add_js:
        assert await async_setup_component(hass, DOMAIN, {})
    (paths,), _ = hass.http.async_register_static_paths.call_args
    assert paths[0].url_path == CARD_URL
    assert paths[0].path == str(CARD_FILE)
    assert CARD_FILE.is_file()
    version = json.loads((CARD_FILE.parents[1] / "manifest.json").read_text())[
        "version"
    ]
    url = f"{CARD_URL}?v={version}"
    assert add_js.call_args_list == [call(hass, url), call(hass, url, es5=True)]


async def test_card_skipped_without_frontend(hass):
    with patch("custom_components.mykolaiv_outages.add_extra_js_url") as add_js:
        assert await async_setup_component(hass, DOMAIN, {})
    add_js.assert_not_called()
