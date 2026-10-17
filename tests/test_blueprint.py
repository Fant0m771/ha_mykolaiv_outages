"""The notification blueprint is a valid automation and sends what it should."""

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
# What a user would pick, e.g. telegram_bot.send_message; notify.notify is mocked.
SEND = [
    {
        "action": "notify.notify",
        "data": {"title": "{{ title }}", "message": "{{ message }}"},
    }
]
RESTORED = {
    "event_type": "schedule_published",
    "day": "tomorrow",
    "schedule": "01:00–02:00",
}


def automation_config(**extra):
    blueprint = Blueprint(
        load_yaml_dict(BLUEPRINT),
        expected_domain="automation",
        schema=BLUEPRINT_SCHEMA,
    )
    inputs = BlueprintInputs(
        blueprint,
        {
            "use_blueprint": {
                "path": "mykolaiv_outages/notifications.yaml",
                "input": {
                    "power_entity": "binary_sensor.power",
                    "next_outage_entity": "sensor.next_outage",
                    "schedule_entity": "event.schedule",
                    "notify_actions": SEND,
                    **extra,
                },
            }
        },
    )
    inputs.validate()
    config = inputs.async_substitute()
    config["id"] = "notifications"
    return config


async def start(hass, **extra):
    sent = async_mock_service(hass, "notify", "notify")
    assert await async_setup_component(
        hass, "automation", {"automation": automation_config(**extra)}
    )
    await hass.async_block_till_done()
    return sent


def set_event(hass, stamp, event_type, day, schedule):
    hass.states.async_set(
        "event.schedule",
        stamp,
        {"event_type": event_type, "day": day, "schedule": schedule},
    )


async def test_blueprint_is_valid(hass):
    config = automation_config()
    assert config["actions"] == SEND
    assert config["variables"]["notify_tomorrow"] is True
    result = await async_validate_config_item(hass, "test", config)
    assert result is not None
    assert result.validation_error is None, result.validation_error


# The template trigger re-checks now() every minute; that timer outlives the test.
@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_blueprint_notifications(hass):
    now = dt_util.utcnow()
    hass.states.async_set("binary_sensor.power", "on")
    hass.states.async_set("sensor.next_outage", (now + timedelta(hours=1)).isoformat())
    hass.states.async_set("event.schedule", "unavailable")
    sent = await start(hass)

    # Restored after a restart: not a new schedule.
    hass.states.async_set("event.schedule", "2026-10-17T07:00:00+00:00", RESTORED)
    await hass.async_block_till_done()
    assert sent == []

    hass.states.async_set("binary_sensor.power", "off")
    await hass.async_block_till_done()
    assert sent[-1].data == {
        "title": "🔌 Світло зникло",
        "message": "Обленерго повідомляє про відключення вашої черги.",
    }

    hass.states.async_set("binary_sensor.power", "on")
    await hass.async_block_till_done()
    assert sent[-1].data["title"] == "💡 Світло є"

    set_event(
        hass,
        "2026-10-17T08:00:00+00:00",
        "schedule_published",
        "tomorrow",
        "06:00–07:00",
    )
    await hass.async_block_till_done()
    assert sent[-1].data == {"title": "📅 Графік на завтра", "message": "06:00–07:00"}

    set_event(
        hass, "2026-10-17T08:05:00+00:00", "schedule_changed", "today", "10:30–12:00"
    )
    await hass.async_block_till_done()
    assert sent[-1].data == {
        "title": "📅 Графік на сьогодні змінено",
        "message": "10:30–12:00",
    }

    count = len(sent)
    hass.states.async_set(
        "sensor.next_outage", (now + timedelta(minutes=10)).isoformat()
    )
    await hass.async_block_till_done()
    assert len(sent) == count + 1
    assert sent[-1].data["title"] == "⚡ Скоро відключення"
    assert sent[-1].data["message"].endswith("(через 10 хв).")
    assert "\n" not in sent[-1].data["message"]


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_blueprint_options_off(hass):
    now = dt_util.utcnow()
    hass.states.async_set("binary_sensor.power", "on")
    hass.states.async_set("sensor.next_outage", (now + timedelta(hours=1)).isoformat())
    hass.states.async_set("event.schedule", "2026-10-17T07:00:00+00:00", RESTORED)
    sent = await start(
        hass,
        lead_minutes=0,
        notify_power=False,
        notify_tomorrow=False,
        notify_changes=False,
    )
    hass.states.async_set(
        "sensor.next_outage", (now + timedelta(minutes=5)).isoformat()
    )
    hass.states.async_set("binary_sensor.power", "off")
    set_event(hass, "2026-10-17T08:00:00+00:00", "schedule_published", "tomorrow", "x")
    set_event(hass, "2026-10-17T08:01:00+00:00", "schedule_changed", "today", "y")
    await hass.async_block_till_done()
    assert sent == []
