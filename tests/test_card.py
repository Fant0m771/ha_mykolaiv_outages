"""Dashboard card registration."""

from unittest.mock import AsyncMock, MagicMock, patch

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
    add_js.assert_called_once_with(hass, f"{CARD_URL}?v=0.2.0")


async def test_card_skipped_without_frontend(hass):
    with patch("custom_components.mykolaiv_outages.add_extra_js_url") as add_js:
        assert await async_setup_component(hass, DOMAIN, {})
    add_js.assert_not_called()
