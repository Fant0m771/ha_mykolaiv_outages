"""Diagnostics: what the integration received, without the user's address."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import MykolaivConfigEntry
from .const import CONF_ADDRESS, CONF_EMERGENCY, CONF_HOUSE, CONF_QUEUE, TIME_ZONE
from .schedule import SlotKind

TO_REDACT = {CONF_ADDRESS, CONF_HOUSE, "title"}
SYMBOLS = {
    SlotKind.ON: ".",
    SlotKind.POSSIBLE: "?",
    SlotKind.OFF: "x",
    SlotKind.CONFIRMED: "X",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MykolaivConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    queue = entry.data[CONF_QUEUE]
    today = dt_util.utcnow().astimezone(TIME_ZONE).date()
    days = {}
    for day in sorted(data.days):
        slots = data.slots(queue, day)
        days[day.isoformat()] = (
            None if slots is None else "".join(SYMBOLS[kind] for kind in slots)
        )
    return {
        "entry": async_redact_data({"title": entry.title, **entry.data}, TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception)
            if coordinator.last_exception
            else None,
            "fetched": data.fetched.isoformat(),
            "operator_updated": data.updated.isoformat() if data.updated else None,
            "entries_sharing_poll": coordinator.users,
        },
        "today": today.isoformat(),
        "queue": {
            "name": queue,
            "known": queue in data.queues,
            "live_off": data.queues[queue].live_off if queue in data.queues else None,
            # One symbol per half hour from 00:00, see SYMBOLS.
            "slots": days,
        },
        "emergency": {
            str(item): (
                {
                    "label": data.emergency[item].label,
                    "live_off": data.emergency[item].live_off,
                }
                if item in data.emergency
                else None
            )
            for item in entry.data.get(CONF_EMERGENCY, [])
        },
        "operator_queues": sorted(data.queues),
    }
