"""The notification blueprint is a valid automation once filled in."""

from datetime import timedelta
from pathlib import Path

import pytest
from homeassistant.components.automation.config import async_validate_config_item
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml_dict
from pytest_homeassistant_custom_component.common import async_mock_service

BLUEPRINT = (
    Path(__file__).parents[1]
    / "blueprints"
    / "automation"
    / "mykolaiv_outages"
    / "notifications.yaml"
)


def without_device_actions(steps):
    """mobile_app cannot load in the minimum HA fixture (no hassil); validate the
    same title/message templates through notify.notify instead."""
    result = []
    for step in steps:
        if step.get("domain") == "mobile_app":
            step = {
                "action": "notify.notify",
                "data": {"title": step["title"], "message": step["message"]},
            }
        elif "choose" in step:
            step = {
                "choose": [
                    {**option, "sequence": without_device_actions(option["sequence"])}
                    for option in step["choose"]
                ]
            }
        result.append(step)
    return result


async def test_blueprint_is_valid(hass):
    blueprint = Blueprint(
        load_yaml_dict(BLUEPRINT), expected_domain="automation", schema=BLUEPRINT_SCHEMA
    )
    inputs = BlueprintInputs(
        blueprint,
        {
            "use_blueprint": {
                "path": "mykolaiv_outages/notifications.yaml",
                "input": {
                    "power_entity": "binary_sensor.cherga_1_1_power",
                    "next_outage_entity": "sensor.cherga_1_1_next_outage",
                    "schedule_entity": "event.cherga_1_1_schedule",
                    "notify_device": "abc123",
                },
            }
        },
    )
    inputs.validate()
    config = inputs.async_substitute()
    assert config["triggers"][0]["id"] == "soon"
    assert config["variables"]["notify_tomorrow"] is True
    assert (
        sum(
            option["sequence"][0]["domain"] == "mobile_app"
            for option in config["actions"][0]["choose"]
        )
        == 5
    )
    config["actions"] = without_device_actions(config["actions"])
    result = await async_validate_config_item(hass, "test", config)
    assert result is not None
    assert result.validation_error is None, result.validation_error


def automation_config(lead=15):
    blueprint = Blueprint(
        load_yaml_dict(BLUEPRINT),
        expected_domain="automation",
        schema=BLUEPRINT_SCHEMA,
    )
    config = BlueprintInputs(
        blueprint,
        {
            "use_blueprint": {
                "path": "mykolaiv_outages/notifications.yaml",
                "input": {
                    "power_entity": "binary_sensor.power",
                    "next_outage_entity": "sensor.next_outage",
                    "schedule_entity": "event.schedule",
                    "notify_device": "abc123",
                    "lead_minutes": lead,
                },
            }
        },
    ).async_substitute()
    config["id"] = "notifications"
    config["actions"] = without_device_actions(config["actions"])
    return config


# The template trigger re-checks now() every minute; that timer outlives the test.
@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_blueprint_notifications(hass, freezer):
    sent = async_mock_service(hass, "notify", "notify")
    now = dt_util.utcnow()
    hass.states.async_set("binary_sensor.power", "on")
    hass.states.async_set("sensor.next_outage", (now + timedelta(hours=1)).isoformat())
    hass.states.async_set("event.schedule", "unavailable")
    assert await async_setup_component(
        hass, "automation", {"automation": automation_config()}
    )
    await hass.async_block_till_done()

    # Restored after a restart: not a new schedule.
    hass.states.async_set("event.schedule", "2026-10-17T07:00:00+00:00", RESTORED)
    await hass.async_block_till_done()
    assert sent == []

    hass.states.async_set("binary_sensor.power", "off")
    await hass.async_block_till_done()
    assert sent[-1].data["title"] == "🔌 Світло зникло"

    hass.states.async_set("binary_sensor.power", "on")
    await hass.async_block_till_done()
    assert sent[-1].data["title"] == "💡 Світло є"

    hass.states.async_set("event.schedule", "2026-10-17T08:00:00+00:00", PUBLISHED)
    await hass.async_block_till_done()
    assert sent[-1].data["title"] == "📅 Графік на завтра"
    assert sent[-1].data["message"] == "06:00–07:00"

    count = len(sent)
    hass.states.async_set(
        "sensor.next_outage", (now + timedelta(minutes=10)).isoformat()
    )
    await hass.async_block_till_done()
    assert len(sent) == count + 1
    assert sent[-1].data["title"] == "⚡ Скоро відключення"
    assert "(через 10 хв)" in sent[-1].data["message"]


# The template trigger re-checks now() every minute; that timer outlives the test.
@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_blueprint_warning_off(hass):
    sent = async_mock_service(hass, "notify", "notify")
    now = dt_util.utcnow()
    hass.states.async_set("sensor.next_outage", (now + timedelta(hours=1)).isoformat())
    assert await async_setup_component(
        hass, "automation", {"automation": automation_config(lead=0)}
    )
    hass.states.async_set(
        "sensor.next_outage", (now + timedelta(minutes=5)).isoformat()
    )
    await hass.async_block_till_done()
    assert sent == []


RESTORED = {
    "event_type": "schedule_published",
    "day": "tomorrow",
    "schedule": "01:00–02:00",
}
PUBLISHED = {
    "event_type": "schedule_published",
    "day": "tomorrow",
    "schedule": "06:00–07:00",
}
