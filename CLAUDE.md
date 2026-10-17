# CLAUDE.md

Home Assistant custom integration for АТ «Миколаївобленерго» outage schedules
(`custom_components/mykolaiv_outages`), installed through HACS. Data comes only
from the operator's public JSON API at https://off.energy.mk.ua/api.

## Always use the home-assistant skill

Before writing or changing anything in this repository (integration code, tests,
the dashboard card, the blueprint, README examples), load the `home-assistant`
skill and check the relevant official documentation pages with its
`find_doc.py`. Home Assistant changes every month; this project already shipped
one bug (calendar description class) and one outdated README example (Telegram
`target`) that the current docs would have prevented. Read the skill's
`references/field-notes.md` sections for the area you touch.

## Layout

- `api.py`: HTTP client and address directory (`addr/...`), errors carry a `reason`.
- `schedule.py`: pure parsing of queues, the half-hour time series and active
  schedules; DST-aware timeline, outage periods and forecast. No HA imports.
- `coordinator.py`: one `DataUpdateCoordinator` shared by all entries
  (`config_entry=None`, reference counted via `async_acquire`/`async_release`),
  polling every 5 minutes plus a half-hour clock tick without network requests.
- Platforms: `binary_sensor.py` (live operator status, scheduled power),
  `sensor.py` (today/tomorrow, next outage, restoration, last update),
  `calendar.py`, `event.py` (schedule published/changed, first refresh is the
  baseline). Shared base class in `entity.py`; entity unique IDs use the entry ID
  so reconfiguring the queue keeps entities.
- `repairs.py`: repair issues (queue missing, house moved to another queue,
  with a fix flow) and the twice-daily house check for address-bound entries.
- `diagnostics.py`: config entry diagnostics; the address, house and title are
  redacted.
- `config_flow.py`: address lookup (branch → settlement → street → house) or
  manual queue; reconfigure; one entry per queue (unique ID = queue name).
- `frontend/mykolaiv-outages-card.js`: bundled Lovelace card, no build step.
  `card.py` serves it and adds it as a dashboard resource (storage mode; kept
  up to date with the version, removed with the last entry). Only in YAML mode
  does it fall back to `add_extra_js_url` (both builds): page scripts load
  independently of the dashboard, and the Android app then showed
  "Configuration error" intermittently.
- `blueprints/automation/mykolaiv_outages/notifications.yaml`: notifications
  blueprint; users import it from GitHub `main`, so changes reach them without a
  release (they must "Re-import blueprint").

## Rules

- Never infer data the operator did not publish: an unpublished day is
  `unknown`, an outage that reaches the end of the published horizon has an
  unknown end. `PROBABLY_OFF` ("power possible") is not an outage.
- Keep entity keys, unique IDs and attribute names stable; they are used by
  users' automations, the card and the blueprint.
- Minimum Home Assistant is 2025.1 (`hacs.json`). Code must work on it and on
  the current release.
- Live statuses (`power`, `emergency_power`) need fresh data; schedule-based
  entities keep the last data for `STALE_AFTER` while the site is down.
- Translations: every user-visible string goes into `strings.json`,
  `translations/en.json` and `translations/uk.json`.

## Checks

```sh
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-ha-minimum.txt
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/mypy
.venv/bin/python -m pytest -q --cov
node --check custom_components/mykolaiv_outages/frontend/mykolaiv-outages-card.js
```

Locally only the HA 2025.1 fixture runs (Python 3.12). CI
(`.github/workflows/validate.yml`) also runs HA 2026.10 on Python 3.14, hassfest
and the HACS action; a change is done only when CI is green. Card changes should
also be rendered in headless Chrome with a fake `hass` (see the skill's field
notes, section 4).

## Releases

1. Bump `version` in `manifest.json` and `CARD_VERSION` in the card (the version
   also busts the card's browser cache).
2. Commit, push, wait for green CI.
3. Annotated tag `vX.Y.Z` on that commit, push the tag, then create a GitHub
   release with English and Ukrainian notes. HACS only offers releases, and
   renders the README from the release tag.

Commits are signed through the 1Password SSH agent; if signing fails, ask the
user to unlock 1Password rather than disabling signing.

## Communication

The user usually writes in Ukrainian; answer in the language they use.
