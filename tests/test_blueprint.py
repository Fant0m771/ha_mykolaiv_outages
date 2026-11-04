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
                    "power_entity": ["binary_sensor.power", "binary_sensor.emergency"],
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
    hass.states.async_set("binary_sensor.emergency", "on", {"source": "emergency"})
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

    hass.states.async_set(
        "binary_sensor.emergency",
        "off",
        {"source": "emergency", "switched_off": ["ГАВ 9"]},
    )
    await hass.async_block_till_done()
    assert sent[-1].data == {
        "title": "🔌 Світло зникло",
        "message": "Аварійне відключення (ГАВ 9). Час відновлення не публікується.",
    }

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

    # The emergency outage is still on: no "outage soon" for power that is gone.
    count = len(sent)
    hass.states.async_set(
        "sensor.next_outage", (now + timedelta(minutes=10)).isoformat()
    )
    await hass.async_block_till_done()
    assert len(sent) == count

    hass.states.async_set("binary_sensor.emergency", "on", {"source": "emergency"})
    await hass.async_block_till_done()
    count = len(sent)
    hass.states.async_set("sensor.next_outage", (now + timedelta(hours=1)).isoformat())
    await hass.async_block_till_done()
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


async def test_manual_run_sends_test_message(hass):
    sent = await start(hass)
    await hass.services.async_call(
        "automation", "trigger", {"entity_id": "all"}, blocking=True
    )
    await hass.async_block_till_done()
    assert sent[-1].data == {
        "title": "🧪 Перевірка сповіщень",
        "message": "Сповіщення про відключення світла працюють.",
    }


async def test_single_power_entity_still_valid(hass):
    """Automations created before 0.4.0 store one entity, not a list."""
    config = automation_config(power_entity="binary_sensor.power")
    result = await async_validate_config_item(hass, "test", config)
    assert result.validation_error is None, result.validation_error


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_own_power_sensor_decides_the_warning(hass):
    now = dt_util.utcnow()
    hass.states.async_set("binary_sensor.power", "on")
    hass.states.async_set("binary_sensor.emergency", "on", {"source": "emergency"})
    hass.states.async_set("binary_sensor.grid", "off")
    hass.states.async_set("sensor.next_outage", (now + timedelta(hours=1)).isoformat())
    sent = await start(hass, own_power_entity="binary_sensor.grid")

    async def warn():
        hass.states.async_set(
            "sensor.next_outage", (now + timedelta(hours=1)).isoformat()
        )
        await hass.async_block_till_done()
        hass.states.async_set(
            "sensor.next_outage", (now + timedelta(minutes=10)).isoformat()
        )
        await hass.async_block_till_done()

    # The grid is already gone, though the operator still reports power.
    await warn()
    assert sent == []

    # The grid is there, though the operator already reports an outage.
    hass.states.async_set("binary_sensor.grid", "on")
    hass.states.async_set("binary_sensor.power", "off")
    await hass.async_block_till_done()
    sent.clear()
    await warn()
    assert [call.data["title"] for call in sent] == ["⚡ Скоро відключення"]

    # Unavailable: the operator's status decides again.
    hass.states.async_set("binary_sensor.grid", "unavailable")
    sent.clear()
    await warn()
    assert sent == []


async def test_own_power_sensor_skips_late_operator_status(hass):
    hass.states.async_set("binary_sensor.power", "on")
    hass.states.async_set("binary_sensor.emergency", "on", {"source": "emergency"})
    hass.states.async_set("binary_sensor.grid", "on")
    sent = await start(hass, own_power_entity="binary_sensor.grid")

    async def operator(entity, state, **attributes):
        hass.states.async_set(entity, state, attributes)
        await hass.async_block_till_done()
        titles = [call.data["title"] for call in sent]
        sent.clear()
        return titles

    # The operator reports the outage first: sent.
    assert await operator("binary_sensor.power", "off") == ["🔌 Світло зникло"]
    # Your sensor saw the power come back before the operator did: skipped.
    hass.states.async_set("binary_sensor.grid", "on")
    assert await operator("binary_sensor.power", "on") == []
    # Your sensor saw the outage 20 minutes before the operator: skipped.
    hass.states.async_set("binary_sensor.grid", "off")
    assert await operator("binary_sensor.power", "off") == []
    # An emergency outage says what happened: still sent.
    assert await operator(
        "binary_sensor.emergency", "off", source="emergency", switched_off=["5.1"]
    ) == ["🔌 Світло зникло"]
