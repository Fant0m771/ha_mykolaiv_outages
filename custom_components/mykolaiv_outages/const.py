"""Constants for the Mykolaivoblenergo Outages integration."""

from datetime import timedelta
from typing import Final
from zoneinfo import ZoneInfo

DOMAIN: Final = "mykolaiv_outages"
MANUFACTURER: Final = "АТ «Миколаївобленерго»"

SITE_URL: Final = "https://off.energy.mk.ua"
API_URL: Final = f"{SITE_URL}/api"
TIME_ZONE: Final = ZoneInfo("Europe/Kyiv")
SCAN_INTERVAL: Final = timedelta(minutes=5)

# Hourly outage schedule (ГПВ) queues; emergency ГАВ/СГАВ queues are separate.
GPV_QUEUE_TYPE: Final = 3

CONF_QUEUE: Final = "queue"
CONF_ADDRESS: Final = "address"
