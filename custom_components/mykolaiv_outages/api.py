"""Client for the public Mykolaivoblenergo outage site."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_URL, EMERGENCY_QUEUE_TYPES, GPV_QUEUE_TYPE, SITE_URL
from .schedule import Queue, SourceData, parse_source


class MykolaivApiError(Exception):
    """Raised when the operator site cannot provide valid data."""

    def __init__(
        self,
        message: str,
        *,
        reason: Literal["connection_error", "invalid"] = "connection_error",
    ) -> None:
        super().__init__(message)
        self.reason = reason


class MykolaivApi:
    """Small async client; the session is owned by Home Assistant."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def _async_get_list(self, path: str) -> list[dict[str, Any]]:
        try:
            async with self._session.get(
                f"{API_URL}/{path}",
                headers={"Accept": "application/json", "Referer": SITE_URL},
                timeout=ClientTimeout(total=30),
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError) as err:
            raise MykolaivApiError(str(err) or type(err).__name__) from err
        except ValueError as err:
            raise MykolaivApiError(str(err), reason="invalid") from err
        if not isinstance(payload, list) or any(
            not isinstance(item, dict) for item in payload
        ):
            raise MykolaivApiError("Unexpected response format", reason="invalid")
        return payload

    async def async_get_source(self) -> SourceData:
        """Fetch queues, the half-hour grid and active schedules together."""
        queues = await self._async_get_list(f"outage-queue/by-type/{GPV_QUEUE_TYPE}")
        emergency = []
        for type_id in EMERGENCY_QUEUE_TYPES:
            emergency += await self._async_get_list(f"outage-queue/by-type/{type_id}")
        time_series = await self._async_get_list("schedule/time-series")
        schedules = await self._async_get_list("v2/schedule/active")
        try:
            return parse_source(
                queues, time_series, schedules, datetime.now(UTC), emergency
            )
        except ValueError as err:
            raise MykolaivApiError(str(err), reason="invalid") from err

    async def _async_get_choices(
        self, path: str, id_key: str, name_key: str
    ) -> dict[int, str]:
        rows = await self._async_get_list(path)
        choices = {}
        for row in rows:
            if type(row.get(id_key)) is not int or not isinstance(
                row.get(name_key), str
            ):
                raise MykolaivApiError("Unexpected address format", reason="invalid")
            choices[row[id_key]] = row[name_key].strip()
        return choices

    async def async_get_branches(self) -> dict[int, str]:
        """Return operator branches (дільниці)."""
        return await self._async_get_choices("addr/filii", "idfilial", "fullname")

    async def async_get_settlements(self, branch: int) -> dict[int, str]:
        return await self._async_get_choices(
            f"addr/filii/{branch}/ns", "idnaspunkt", "naznaspunkt"
        )

    async def async_get_streets(self, settlement: int) -> dict[int, str]:
        return await self._async_get_choices(
            f"addr/ns/{settlement}/street", "idstreet", "nazstreet"
        )

    async def async_get_houses(self, street: int) -> dict[int, str]:
        return await self._async_get_choices(
            f"addr/street/{street}/dom", "iddom", "nazdom"
        )

    async def async_get_house_queues(self, house: int) -> list[Queue]:
        """Return the schedule and emergency queues the operator assigns to a house."""
        rows = await self._async_get_list(f"addr/dom/{house}/outage-queue")
        queues = []
        for row in rows:
            outage = row.get("outage")
            if (
                not isinstance(outage, dict)
                or not isinstance(outage.get("name"), str)
                or type(outage.get("id")) is not int
                or type(outage.get("type_id")) is not int
            ):
                raise MykolaivApiError(
                    "Unexpected house queue format", reason="invalid"
                )
            known = outage["type_id"] in (GPV_QUEUE_TYPE, *EMERGENCY_QUEUE_TYPES)
            if known and not outage.get("deleted"):
                queues.append(
                    Queue(
                        id=outage["id"],
                        name=outage["name"],
                        live_off=bool(outage.get("enabled")),
                        type_id=outage["type_id"],
                    )
                )
        return queues
