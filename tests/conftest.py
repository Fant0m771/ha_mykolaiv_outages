"""Shared fixtures built from real off.energy.mk.ua responses (2026-10-17)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from custom_components.mykolaiv_outages.const import API_URL

FIXTURES = Path(__file__).parent / "fixtures"
QUEUES_URL = f"{API_URL}/outage-queue/by-type/3"
TIME_SERIES_URL = f"{API_URL}/schedule/time-series"
ACTIVE_URL = f"{API_URL}/v2/schedule/active"
# 11:00 in Kyiv: queue 1.1 is inside its 10:30–12:00 outage.
NOW = datetime(2026, 10, 17, 8, tzinfo=UTC)


def load(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow loading the integration from this repository."""


@pytest.fixture(autouse=True)
def fixed_time(freezer):
    freezer.move_to(NOW)


@pytest.fixture
def queues():
    return load("queues")


@pytest.fixture
def time_series():
    return load("time_series")


@pytest.fixture
def active():
    return load("active")


@pytest.fixture
def source(aioclient_mock, queues, time_series, active):
    """Mock the three polling endpoints."""
    aioclient_mock.get(QUEUES_URL, json=queues)
    aioclient_mock.get(TIME_SERIES_URL, json=time_series)
    aioclient_mock.get(ACTIVE_URL, json=active)
    return aioclient_mock
