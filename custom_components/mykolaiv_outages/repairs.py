"""Repair issues: the queue disappeared, or the house moved to another queue."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .api import MykolaivApiError
from .const import CONF_EMERGENCY, CONF_HOUSE, CONF_QUEUE, DOMAIN, GPV_QUEUE_TYPE

_LOGGER = logging.getLogger(__name__)


def missing_issue(entry_id: str) -> str:
    return f"queue_missing_{entry_id}"


def changed_issue(entry_id: str) -> str:
    return f"queue_changed_{entry_id}"


@callback
def async_check_queue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Tell the user when the configured queue no longer exists at the operator."""
    coordinator = entry.runtime_data
    if not coordinator.last_update_success or coordinator.data is None:
        return
    queue = entry.data[CONF_QUEUE]
    if queue in coordinator.data.queues:
        ir.async_delete_issue(hass, DOMAIN, missing_issue(entry.entry_id))
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        missing_issue(entry.entry_id),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="queue_missing",
        translation_placeholders={"queue": queue, "title": entry.title},
    )


async def async_check_house(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Follow the operator's queue assignment for an address-bound entry.

    Emergency queues follow silently; a different schedule queue changes what
    the user sees, so it is offered as a repair the user confirms.
    """
    house = entry.data.get(CONF_HOUSE)
    if not house:
        return
    try:
        queues = await entry.runtime_data.api.async_get_house_queues(house)
    except MykolaivApiError as err:
        _LOGGER.debug("House queue check failed: %s", err)
        return
    if not queues:
        # An empty answer says nothing about the house; keep what we have.
        return
    schedule = sorted({q.name for q in queues if q.type_id == GPV_QUEUE_TYPE})
    emergency = sorted(q.id for q in queues if q.type_id != GPV_QUEUE_TYPE)
    if emergency != entry.data.get(CONF_EMERGENCY, []):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_EMERGENCY: emergency}
        )
        # Entities read the queue list from the entry; show the change now.
        entry.runtime_data.async_update_listeners()
    current = entry.data[CONF_QUEUE]
    if not schedule or current in schedule:
        ir.async_delete_issue(hass, DOMAIN, changed_issue(entry.entry_id))
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        changed_issue(entry.entry_id),
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="queue_changed",
        translation_placeholders={
            "title": entry.title,
            "old": current,
            "new": schedule[0],
        },
        data={"entry_id": entry.entry_id, "queue": schedule[0]},
    )


class QueueChangedRepairFlow(RepairsFlow):
    """Switch the entry to the house's new queue, keeping its entities."""

    def __init__(self, entry_id: str, queue: str) -> None:
        self._entry_id = entry_id
        self._queue = queue

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="entry_removed")
        old = entry.data[CONF_QUEUE]
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    "title": entry.title,
                    "old": old,
                    "new": self._queue,
                },
            )
        if any(
            other.unique_id == self._queue
            for other in self.hass.config_entries.async_entries(DOMAIN)
            if other.entry_id != entry.entry_id
        ):
            return self.async_abort(
                reason="already_configured",
                description_placeholders={"new": self._queue},
            )
        self.hass.config_entries.async_update_entry(
            entry,
            unique_id=self._queue,
            title=entry.title.replace(f"(черга {old})", f"(черга {self._queue})"),
            data={**entry.data, CONF_QUEUE: self._queue},
        )
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_create_entry(title="", data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    assert data is not None
    return QueueChangedRepairFlow(str(data["entry_id"]), str(data["queue"]))
