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

# Hourly outage schedule (ГПВ) queues; emergency ГАВ/СГАВ queues are separate
# and only have a live status, no schedule.
GPV_QUEUE_TYPE: Final = 3
EMERGENCY_QUEUE_TYPES: Final = {1: "ГАВ", 2: "СГАВ"}

# Keep showing the last published schedule this long while the site is down.
# Live statuses become unavailable at once.
STALE_AFTER: Final = timedelta(hours=1)
# How often an address-bound entry checks the house's queues.
HOUSE_CHECK_INTERVAL: Final = timedelta(hours=12)

CONF_QUEUE: Final = "queue"
CONF_ADDRESS: Final = "address"
CONF_HOUSE: Final = "house"
CONF_EMERGENCY: Final = "emergency"
