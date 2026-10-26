# Mykolaivoblenergo Outages

Home Assistant integration for АТ «Миколаївобленерго» hourly outage schedules (ГПВ), read directly from the operator's public site [off.energy.mk.ua](https://off.energy.mk.ua).

[![Open your Home Assistant instance and open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Fant0m771&repository=ha_mykolaiv_outages&category=integration)

[![Support via monobank](https://img.shields.io/badge/%D0%9F%D1%96%D0%B4%D1%82%D1%80%D0%B8%D0%BC%D0%B0%D1%82%D0%B8-monobank-black?logo=buymeacoffee&logoColor=white)](https://send.monobank.ua/jar/9U2n9h97ti)

[**English**](#english) | [Українською](#українською)

<img src="https://raw.githubusercontent.com/Fant0m771/ha_mykolaiv_outages/main/docs/images/card.png" alt="Mykolaivoblenergo Outages dashboard card" width="480">

## English

### Features

- **Find your queue by address**: branch → settlement → street → house, exactly as on off.energy.mk.ua. Or choose the queue manually.
- **Power**: the operator's live status. It turns off while your queue is actually switched off.
- **Power by schedule**: whether the published schedule has power for the current half hour.
- **Today's / Tomorrow's schedule**: all outage periods, e.g. `10:30–12:00; 16:30–19:00`. The attributes list every period with its kind: `off` (planned), `confirmed` (actual), `possible` (power possible).
- **Next outage** and **Power restoration**: timestamps for automations. They are unknown rather than guessed when the end lies beyond the published schedule.
- **Schedule updated**: when the operator last changed the schedule.
- **Outages** calendar: every outage as a calendar event, for calendar triggers with an offset.
- **Schedule** events: `schedule_published` and `schedule_changed`, with `day` (`today`/`tomorrow`), `date` and `schedule` attributes.
- **Power (emergency queue)**: the live status of your emergency queues (ГАВ/СГАВ). Found automatically when you set up by address, or chosen manually.
- **Keeps working when the operator's site is down**: the last published schedule stays until its last published day is over (attribute `cached: true` on the schedule entities), the live statuses become unavailable, and the **Operator site** diagnostic sensor shows the connection problem. Corrections the operator publishes meanwhile arrive once the site answers again.
- **Repairs**: if the operator moves your house to another queue (address-bound entries are checked twice a day), Settings → Repairs offers to switch with one click, keeping entities and history. A queue that disappears is reported there too.
- **Diagnostics** download for bug reports, with your address removed.
- One shared request every 5 minutes for all configured queues. States also update on every half-hour boundary.
- English and Ukrainian.

When the operator has not published a schedule for a day, that day's sensors are `unknown`. **Power** keeps working regardless.

### Created entities

One device per queue, with these entities (names follow your Home Assistant language; entity IDs depend on the entry title):

| Type | Name | State | Attributes |
|---|---|---|---|
| Binary sensor | **Power** | `off` while the operator reports your queue switched off (live) | `source` |
| Binary sensor | **Power by schedule** | whether the current half hour has power in the published schedule | `source`, `slot` (`on` / `off` / `confirmed` / `possible`), `cached` |
| Binary sensor | **Power (emergency queue)** | `off` while one of your emergency queues (ГАВ/СГАВ) is switched off. Only with emergency queues | `queues`, `switched_off` |
| Sensor | **Today's schedule** / **Tomorrow's schedule** | outage periods, e.g. `10:30–12:00; 16:30–19:00`; `unknown` until published | `queue`, `cached`, `date`, `published`, `schedules_active` (`false` while the operator applies no schedule to any queue), `outages`, `periods` (with `kind`) |
| Sensor (timestamp) | **Next outage** | start of the next outage within the published schedule | `queue`, `outage`, `cached` |
| Sensor (timestamp) | **Power restoration** | end of the current or next outage; `unknown` if beyond the schedule | `queue`, `outage` (`current` / `next` / `none`), `cached` |
| Sensor (timestamp, diagnostic) | **Schedule updated** | when the operator last changed the schedule | `fetched`, `cached` |
| Binary sensor (diagnostic) | **Operator site** | connection to off.energy.mk.ua | `last_success` |
| Calendar | **Outages** | an event for every outage | `cached` |
| Event | **Schedule** | `schedule_published`, `schedule_changed` | `day`, `date`, `schedule` |

### Installation

**HACS**: HACS → ⋮ → Custom repositories → add this repository as *Integration* → install **Mykolaivoblenergo Outages** → restart Home Assistant.

**Manual**: copy `custom_components/mykolaiv_outages` to `config/custom_components/` and restart.

Then go to Settings → Devices & services → Add integration → **Mykolaivoblenergo Outages**. Add one entry per queue. Use ⋮ → *Reconfigure* to change the queue while keeping the entities.

### Dashboard card

The integration ships its own card and adds it to the dashboard resources itself (Settings → Dashboards → ⋮ → Resources), so there is nothing to download. With dashboards in YAML mode it is loaded on every page instead. Edit a dashboard → **Add card** → **By card** → **Mykolaivoblenergo Outages** (under *Community cards*), then choose your queue device.

It shows the live power status, a countdown to the next outage or to restoration, and half-hour timelines for today and tomorrow with a "now" marker. While the operator reports power and applies no hourly schedule to any queue, it says **No outage schedules in effect** on a green background instead of "Schedule not published yet", and shows a single line for today. Its passed half hours show what really happened, from Home Assistant's history of *Your power sensor* or, without one, of the operator's **Power** status: green while power was on, red if it was off (hover for the exact times), grey without history. The rest of the day is hatched as unknown, never drawn as power.

```yaml
type: custom:mykolaiv-outages-card
device: <device id>          # chosen in the visual editor
title: Home                  # optional
show_tomorrow: true          # optional
power_entity: binary_sensor.inverter_grid   # optional
```

**Your own power sensor** (optional): the operator's live status sometimes lags behind reality by an hour or more. If you have a sensor that sees the grid, such as an inverter's grid input, choose it in *Your power sensor*. The card's status then follows it (`on` = power), and a note says when the operator still reports an outage. The timelines, next outage and restoration times still come from the operator.

**Footer times**: *Updated* is when the operator last changed the schedule, *checked* is when Home Assistant last asked the operator (every 5 minutes). The ⟳ button next to them checks right away.

**Colours**: the card uses the theme's `success-color`, `error-color` and `warning-color`. The hatching of unknown time and the outlines of the emergency row and of pending notes use `--mo-divider` (default `rgba(76, 175, 80, 0.6)`); set it in your theme (`mo-divider: ...`) or with card-mod.

### Notifications blueprint

[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FFant0m771%2Fha_mykolaiv_outages%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmykolaiv_outages%2Fnotifications.yaml)

One automation for a queue's notifications: a warning N minutes before a scheduled outage, power lost and restored (add the emergency sensor to **Power** to include emergency outages), tomorrow's schedule published and schedule changes. Each one can be switched off.

In **Send notification**, add the actions that deliver them, using `{{ title }}` and `{{ message }}`. For example, to a Telegram channel through your existing Telegram bot (copy the action your other Telegram automations already use):

```yaml
- action: notify.send_message
  target:
    entity_id: notify.my_telegram_channel   # your Telegram bot's notify entity
  data:
    message: '{{ title }}{{ "\n" }}{{ message }}'
```

`telegram_bot.send_message` works too: pick the chat with `entity_id` (a Telegram notify entity) or `config_entry_id` + `chat_id`, see [the action's documentation](https://www.home-assistant.io/actions/telegram_bot.send_message/).

or to the Companion app: `action: notify.mobile_app_<your_phone>` with the same `title` and `message`. Several actions send to several places.

### Automation examples

Warn 15 minutes before every outage, using the calendar:

```yaml
triggers:
  - trigger: calendar
    event: start
    entity_id: calendar.cherga_4_2_outages
    offset: "-0:15:0"
actions:
  - action: notify.notify
    data:
      message: "Power outage at {{ trigger.calendar_event.start[11:16] }}"
```

Tomorrow's schedule is published:

```yaml
triggers:
  - trigger: state
    entity_id: event.cherga_4_2_schedule
conditions:
  - "{{ trigger.to_state.attributes.event_type == 'schedule_published' }}"
  - "{{ trigger.to_state.attributes.day == 'tomorrow' }}"
actions:
  - action: notify.notify
    data:
      message: "Tomorrow: {{ trigger.to_state.attributes.schedule }}"
```

Entity IDs depend on the entry title and language; check yours under the device. Schedule events compare each refresh with the previous one, so changes made while Home Assistant was off are not reported.

## Українською

Інтеграція Home Assistant для графіків погодинних відключень (ГПВ) АТ «Миколаївобленерго» напряму з [off.energy.mk.ua](https://off.energy.mk.ua).

- **Пошук черги за адресою** (дільниця → населений пункт → вулиця → будинок) або вибір черги вручну.
- **Електропостачання**: поточний стан від обленерго. Вимикається, коли вашу чергу фактично знеструмлено.
- **Електропостачання за графіком**: чи є світло в поточному пів-годинному слоті графіка.
- **Графік на сьогодні / завтра**: усі періоди відключень. В атрибутах є кожен період із типом: `off` (заплановане), `confirmed` (актуальне), `possible` (електропостачання можливе).
- **Наступне відключення** та **Відновлення живлення**: мітки часу для автоматизацій. Якщо кінець виходить за межі опублікованого графіка, значення невідоме, а не вгадане.
- **Оновлення графіка**: коли обленерго востаннє змінило графік.
- Календар **Відключення**: кожне відключення як подія календаря; тригер календаря дозволяє попередження із зсувом, наприклад за 15 хв.
- Події **Графік**: `schedule_published` (графік опубліковано) і `schedule_changed` (графік змінено) з атрибутами `day` (`today`/`tomorrow`), `date` і `schedule`.
- **Електропостачання (аварійна черга)**: поточний стан ваших аварійних черг (ГАВ/СГАВ); під час налаштування за адресою визначаються автоматично.
- **Працює, коли сайт обленерго недоступний**: останній опублікований графік лишається, доки не мине його останній опублікований день (атрибут `cached: true` у сутностей графіка), live-стани стають недоступними, а сенсор **Сайт обленерго** показує проблему зі з'єднанням.
- **Ремонт**: якщо обленерго перенесе ваш будинок в іншу чергу (записи за адресою перевіряються двічі на добу), у Налаштування → Ремонт можна перейти на нову чергу одним кліком, зі збереженням сутностей та історії. Зникнення черги теж повідомляється там.
- **Діагностика** для звітів про проблеми, без вашої адреси.
- Один спільний запит кожні 5 хвилин для всіх черг; стани оновлюються кожні пів години.

Поки графік на день не опубліковано, сенсори цього дня мають стан `unknown`. **Електропостачання** працює завжди.

**Сутності** (по пристрою на кожну чергу; назви залежать від мови Home Assistant, `entity_id` від назви запису):

| Тип | Назва | Стан | Атрибути |
|---|---|---|---|
| Бінарний сенсор | **Електропостачання** | `off`, поки обленерго показує, що вашу чергу вимкнено | `source` |
| Бінарний сенсор | **Електропостачання за графіком** | чи є світло в поточному пів-годинному слоті графіка | `source`, `slot`, `cached` |
| Бінарний сенсор | **Електропостачання (аварійна черга)** | `off`, поки вимкнено одну з ваших аварійних черг (ГАВ/СГАВ); лише якщо вони є | `queues`, `switched_off` |
| Сенсор | **Графік на сьогодні** / **на завтра** | періоди відключень; `unknown`, поки не опубліковано | `queue`, `cached`, `date`, `published`, `schedules_active` (`false`, коли обленерго не застосовує графіки до жодної черги), `outages`, `periods` |
| Сенсор (час) | **Наступне відключення** | початок наступного відключення в межах графіка | `queue`, `outage`, `cached` |
| Сенсор (час) | **Відновлення живлення** | кінець поточного чи наступного відключення | `queue`, `outage` (`current` / `next` / `none`), `cached` |
| Сенсор (час, діагностика) | **Оновлення графіка** | коли обленерго востаннє змінило графік | `fetched`, `cached` |
| Бінарний сенсор (діагностика) | **Сайт обленерго** | зв'язок з off.energy.mk.ua | `last_success` |
| Календар | **Відключення** | подія на кожне відключення | `cached` |
| Подія | **Графік** | `schedule_published`, `schedule_changed` | `day`, `date`, `schedule` |

Встановлення: через HACS (custom repository, тип *Integration*) або скопіюйте `custom_components/mykolaiv_outages` у `config/custom_components/` і перезапустіть Home Assistant. Далі: Налаштування → Пристрої та служби → Додати інтеграцію → **Mykolaivoblenergo Outages**.

**Шаблон сповіщень** (кнопка нижче): попередження за N хвилин до відключення, зникнення та відновлення світла, графік на завтра та зміни графіка. Кожне сповіщення можна вимкнути. У полі **Send notification** додайте дію надсилання з `{{ title }}` і `{{ message }}`, наприклад `telegram_bot.send_message` у ваш Telegram-канал або `notify.mobile_app_<телефон>`.

[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FFant0m771%2Fha_mykolaiv_outages%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmykolaiv_outages%2Fnotifications.yaml)

Інтеграція має власну картку і сама додає її до ресурсів дашбордів, завантажувати нічого не треба: Редагувати дашборд → **Додати картку** → **За карткою** → **Відключення Миколаївобленерго** (розділ *Community cards*) і оберіть пристрій черги. Якщо дані обленерго запізнюються, у полі **Власний сенсор світла** оберіть сенсор, який бачить мережу (наприклад, вхід мережі інвертора): стан на картці братиметься з нього, а графіки як і раніше від обленерго. Коли обленерго повідомляє, що світло є, і не застосовує погодинні графіки до жодної черги, картка пише **Графіків відключень немає** на зеленому тлі замість «Графік ще не опубліковано» і показує одну шкалу на сьогодні. Минулі пів години показують, що було насправді, з історії Home Assistant для **Власного сенсора світла**, а без нього для статусу обленерго **Електропостачання**: зелений, коли світло було, червоний, коли не було (при наведенні видно точний час), сірий, коли історії немає. Решта дня заштрихована як невідоме і ніколи не показується як «світло є». Внизу картки **Оновлено** означає час, коли обленерго востаннє змінило графік, а **перевірено** — коли Home Assistant востаннє звертався до обленерго (кожні 5 хвилин); кнопка ⟳ поруч перевіряє одразу. Колір штрихування і рамок (рядок аварійних черг, повідомлення про неопублікований графік) задає змінна `--mo-divider`, типово `rgba(76, 175, 80, 0.6)`; її можна змінити в темі (`mo-divider: ...`) або через card-mod.

## Development

```sh
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-ha-minimum.txt   # HA 2025.1; requirements-dev.txt for current HA (Python 3.13+)
ruff check . && ruff format --check . && mypy && pytest -q --cov
```

Test fixtures in `tests/fixtures/` are real off.energy.mk.ua responses from 2026-10-17.

If the integration is useful to you, you can buy me a coffee through [monobank](https://send.monobank.ua/jar/9U2n9h97ti) ☕

This project is not affiliated with АТ «Миколаївобленерго». Data comes from its public website and may change without notice.
