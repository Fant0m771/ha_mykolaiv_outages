# Mykolaivoblenergo Outages

Home Assistant integration for АТ «Миколаївобленерго» hourly outage schedules (ГПВ), read directly from the operator's public site [off.energy.mk.ua](https://off.energy.mk.ua).

[**English**](#english) | [Українською](#українською)

## English

### Features

- **Find your queue by address**: branch → settlement → street → house, exactly as on off.energy.mk.ua. Or choose the queue manually.
- **Power**: the operator's live status. It turns off while your queue is actually switched off.
- **Power by schedule**: whether the published schedule has power for the current half hour.
- **Today's / Tomorrow's schedule**: all outage periods, e.g. `10:30–12:00; 16:30–19:00`. The attributes list every period with its kind: `off` (planned), `confirmed` (actual), `possible` (power possible).
- **Next outage** and **Power restoration**: timestamps for automations. They are unknown rather than guessed when the end lies beyond the published schedule.
- **Schedule updated**: when the operator last changed the schedule.
- One shared request every 5 minutes for all configured queues. States also update on every half-hour boundary.
- English and Ukrainian.

When the operator has not published a schedule for a day, that day's sensors are `unknown`. **Power** keeps working regardless.

### Installation

**HACS**: HACS → ⋮ → Custom repositories → add this repository as *Integration* → install **Mykolaivoblenergo Outages** → restart Home Assistant.

**Manual**: copy `custom_components/mykolaiv_outages` to `config/custom_components/` and restart.

Then go to Settings → Devices & services → Add integration → **Mykolaivoblenergo Outages**. Add one entry per queue. Use ⋮ → *Reconfigure* to change the queue while keeping the entities.

### Dashboard card

The integration ships its own card. No separate download or dashboard resource is needed. Edit a dashboard → **Add card** → **By card** → **Mykolaivoblenergo Outages** (under *Community cards*), then choose your queue device.

It shows the live power status, a countdown to the next outage or to restoration, and half-hour timelines for today and tomorrow with a "now" marker.

```yaml
type: custom:mykolaiv-outages-card
device: <device id>          # chosen in the visual editor
title: Home                  # optional
show_tomorrow: true          # optional
```

### Automation example

```yaml
automation:
  - alias: Power outage started
    triggers:
      - trigger: state
        entity_id: binary_sensor.cherga_4_2_power
        to: "off"
    actions:
      - action: notify.notify
        data:
          message: >
            Power is off. Expected back:
            {{ states('sensor.cherga_4_2_power_restoration') | as_datetime | as_local }}
```

Entity IDs depend on the entry title; check yours under the device.

## Українською

Інтеграція Home Assistant для графіків погодинних відключень (ГПВ) АТ «Миколаївобленерго» напряму з [off.energy.mk.ua](https://off.energy.mk.ua).

- **Пошук черги за адресою** (дільниця → населений пункт → вулиця → будинок) або вибір черги вручну.
- **Електропостачання**: поточний стан від обленерго. Вимикається, коли вашу чергу фактично знеструмлено.
- **Електропостачання за графіком**: чи є світло в поточному пів-годинному слоті графіка.
- **Графік на сьогодні / завтра**: усі періоди відключень. В атрибутах є кожен період із типом: `off` (заплановане), `confirmed` (актуальне), `possible` (електропостачання можливе).
- **Наступне відключення** та **Відновлення живлення**: мітки часу для автоматизацій. Якщо кінець виходить за межі опублікованого графіка, значення невідоме, а не вгадане.
- **Оновлення графіка**: коли обленерго востаннє змінило графік.
- Один спільний запит кожні 5 хвилин для всіх черг; стани оновлюються кожні пів години.

Поки графік на день не опубліковано, сенсори цього дня мають стан `unknown`. **Електропостачання** працює завжди.

Встановлення: через HACS (custom repository, тип *Integration*) або скопіюйте `custom_components/mykolaiv_outages` у `config/custom_components/` і перезапустіть Home Assistant. Далі: Налаштування → Пристрої та служби → Додати інтеграцію → **Mykolaivoblenergo Outages**.

Інтеграція має власну картку: Редагувати дашборд → **Додати картку** → **За карткою** → **Відключення Миколаївобленерго** (розділ *Community cards*) і оберіть пристрій черги.

## Development

```sh
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-ha-minimum.txt   # HA 2025.1; requirements-dev.txt for current HA (Python 3.13+)
ruff check . && ruff format --check . && mypy && pytest -q --cov
```

Test fixtures in `tests/fixtures/` are real off.energy.mk.ua responses from 2026-10-17.

This project is not affiliated with АТ «Миколаївобленерго». Data comes from its public website and may change without notice.
