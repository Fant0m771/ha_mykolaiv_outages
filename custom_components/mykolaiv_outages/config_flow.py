"""Find a queue by address or pick it directly."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorMode

from .api import MykolaivApi, MykolaivApiError
from .const import CONF_ADDRESS, CONF_QUEUE, DOMAIN


def select(choices: dict[str, str]) -> SelectSelector:
    """Searchable dropdown that stores the exact source identifier."""
    return SelectSelector(
        {
            "options": [
                {"value": key, "label": label} for key, label in choices.items()
            ],
            "mode": SelectSelectorMode.DROPDOWN,
            "sort": False,
        }
    )


class MykolaivConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """One entry per queue; reconfigure keeps the entities."""

    VERSION = 1

    def __init__(self) -> None:
        self._entry: ConfigEntry | None = None
        self._address: list[str] = []
        self._parent: int | None = None
        self._house_queues: list[str] = []

    @property
    def _api(self) -> MykolaivApi:
        return MykolaivApi(async_get_clientsession(self.hass))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["branch", "queue"])

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._entry = self._get_reconfigure_entry()
        return self.async_show_menu(
            step_id="reconfigure", menu_options=["branch", "queue"]
        )

    async def _async_address_step(
        self,
        step_id: str,
        load: Callable[[], Awaitable[dict[int, str]]],
        user_input: dict[str, Any] | None,
        next_step: Callable[[], Awaitable[ConfigFlowResult]],
    ) -> ConfigFlowResult:
        """Show one level of the operator's address directory."""
        placeholders = {"address": ", ".join(self._address)}
        try:
            choices = await load()
        except MykolaivApiError:
            # A form without fields, so submitting it retries the request.
            return self.async_show_form(
                step_id=step_id,
                data_schema=vol.Schema({}),
                errors={"base": "cannot_connect"},
                description_placeholders=placeholders,
            )
        if not choices:
            # Some settlements list no streets; an empty required list is a dead end.
            return self.async_abort(reason="empty_address")
        errors: dict[str, str] = {}
        if user_input and step_id in user_input:
            selected = int(user_input[step_id]) if user_input[step_id].isdigit() else -1
            if selected in choices:
                self._address.append(choices[selected])
                self._parent = selected
                return await next_step()
            errors[step_id] = "invalid_selection"
        ordered = dict(sorted(choices.items(), key=lambda item: item[1]))
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(step_id): select(
                        {str(key): label for key, label in ordered.items()}
                    )
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_branch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            self._address = []
        return await self._async_address_step(
            "branch", self._api.async_get_branches, user_input, self._next_settlement
        )

    async def _next_settlement(self) -> ConfigFlowResult:
        # The branch name is only a navigation aid, not part of the address.
        self._address = []
        return await self.async_step_settlement()

    async def async_step_settlement(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        parent = self._parent_id()
        return await self._async_address_step(
            "settlement",
            lambda: self._api.async_get_settlements(parent),
            user_input,
            self.async_step_street,
        )

    async def async_step_street(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        parent = self._parent_id()
        return await self._async_address_step(
            "street",
            lambda: self._api.async_get_streets(parent),
            user_input,
            self.async_step_house,
        )

    async def async_step_house(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        parent = self._parent_id()
        return await self._async_address_step(
            "house",
            lambda: self._api.async_get_houses(parent),
            user_input,
            self.async_step_house_queue,
        )

    def _parent_id(self) -> int:
        assert self._parent is not None
        return self._parent

    async def async_step_house_queue(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Use the house's schedule queue; ask only if the operator lists several."""
        address = ", ".join(self._address)
        if user_input is None:
            try:
                self._house_queues = sorted(
                    set(await self._api.async_get_house_queues(self._parent_id()))
                )
            except MykolaivApiError:
                return self.async_abort(reason="cannot_connect")
            if not self._house_queues:
                return self.async_abort(
                    reason="no_house_queue",
                    description_placeholders={"address": address},
                )
            if len(self._house_queues) == 1:
                return await self._async_finish(self._house_queues[0], address)
        elif user_input[CONF_QUEUE] in self._house_queues:
            return await self._async_finish(user_input[CONF_QUEUE], address)
        return self.async_show_form(
            step_id="house_queue",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_QUEUE): select(
                        {queue: queue for queue in self._house_queues}
                    )
                }
            ),
            description_placeholders={"address": address},
        )

    async def async_step_queue(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        queues: list[str] = []
        try:
            queues = sorted((await self._api.async_get_source()).queues)
        except MykolaivApiError:
            errors["base"] = "cannot_connect"
        if user_input is not None and not errors:
            if user_input[CONF_QUEUE] in queues:
                return await self._async_finish(user_input[CONF_QUEUE], None)
            errors[CONF_QUEUE] = "invalid_selection"
        default = self._entry.data[CONF_QUEUE] if self._entry else None
        return self.async_show_form(
            step_id="queue",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_QUEUE,
                        default=default if default in queues else vol.UNDEFINED,
                    ): select({queue: queue for queue in queues})
                }
            ),
            errors=errors,
        )

    async def _async_finish(self, queue: str, address: str | None) -> ConfigFlowResult:
        await self.async_set_unique_id(queue)
        data = {CONF_QUEUE: queue, CONF_ADDRESS: address}
        title = f"{address} (черга {queue})" if address else f"Черга {queue}"
        if self._entry is not None:
            if queue != self._entry.unique_id:
                self._abort_if_unique_id_configured()
            return self.async_update_reload_and_abort(
                self._entry, unique_id=queue, title=title, data=data
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=data)
