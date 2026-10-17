/* Mykolaivoblenergo Outages card: live power, countdown and day timelines. */
const CARD_VERSION = "0.4.1";
const DOMAIN = "mykolaiv_outages";
const TIME_ZONE = "Europe/Kyiv";

const TEXT = {
  en: {
    name: "Mykolaivoblenergo Outages",
    description: "Live power status, countdown and today/tomorrow outage timelines.",
    queue: "Queue",
    power_on: "Power on",
    power_off: "Power off",
    unknown: "Unknown",
    outage_now: "Power outage",
    back_in: "back in",
    restore_unknown: "Restoration time not published",
    scheduled_now: "Scheduled outage now",
    until: "until",
    next_outage: "Next outage",
    no_outages: "No outages scheduled",
    not_published: "Schedule not published yet",
    lasts: "lasts",
    in: "in",
    today: "Today",
    tomorrow: "Tomorrow",
    tomorrow_pending: "Not published yet",
    off: "Outage",
    confirmed: "Confirmed outage",
    possible: "Power possible",
    on: "Power",
    updated: "Updated",
    emergency_outage: "Emergency outage",
    emergency_detail: "Emergency outages have no published end time",
    emergency_queues: "Emergency queues",
    emergency_off: "switched off",
    stale: "No connection to the operator since",
    example: "Example",
    h: "h",
    min: "min",
    pick_device: "Choose a queue in the card editor.",
    device: "Queue device",
    title: "Title (optional)",
    show_tomorrow: "Show tomorrow",
  },
  uk: {
    name: "Відключення Миколаївобленерго",
    description: "Стан світла, зворотний відлік і графіки на сьогодні та завтра.",
    queue: "Черга",
    power_on: "Світло є",
    power_off: "Світла немає",
    unknown: "Невідомо",
    outage_now: "Відключення",
    back_in: "відновлення через",
    restore_unknown: "Час відновлення не опубліковано",
    scheduled_now: "За графіком зараз відключення",
    until: "до",
    next_outage: "Наступне відключення",
    no_outages: "Відключень не заплановано",
    not_published: "Графік ще не опубліковано",
    lasts: "триватиме",
    in: "через",
    today: "Сьогодні",
    tomorrow: "Завтра",
    tomorrow_pending: "Ще не опубліковано",
    off: "Відключення",
    confirmed: "Актуальне відключення",
    possible: "Можливе відключення",
    on: "Світло є",
    updated: "Оновлено",
    emergency_outage: "Аварійне відключення",
    emergency_detail: "Для аварійних відключень час відновлення не публікується",
    emergency_queues: "Аварійні черги",
    emergency_off: "відключено",
    stale: "Немає зв'язку з обленерго з",
    example: "Приклад",
    h: "год",
    min: "хв",
    pick_device: "Оберіть чергу в редакторі картки.",
    device: "Пристрій черги",
    title: "Заголовок (необов'язково)",
    show_tomorrow: "Показувати завтра",
  },
};

const KEYS = [
  "power",
  "scheduled_power",
  "today",
  "tomorrow",
  "next_outage",
  "restoration",
  "last_update",
  "emergency_power",
  "site",
];

function text(hass) {
  const language = (hass && (hass.locale?.language || hass.language)) || "en";
  return language.startsWith("uk") ? TEXT.uk : TEXT.en;
}

function escape(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

function clock(date) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: TIME_ZONE,
  }).format(date);
}

function dayLabel(date, t, hass) {
  const language = t === TEXT.uk ? "uk" : hass?.locale?.language || "en";
  return new Intl.DateTimeFormat(language, {
    day: "numeric",
    month: "short",
    timeZone: TIME_ZONE,
  }).format(date);
}

function duration(ms, t) {
  const minutes = Math.max(0, Math.round(ms / 60000));
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest} ${t.min}`;
  return rest ? `${hours} ${t.h} ${rest} ${t.min}` : `${hours} ${t.h}`;
}

function kyivMinutes(date) {
  const [h, m] = clock(date).split(":").map(Number);
  return h * 60 + m;
}

function toSlot(value) {
  const [h, m] = value.split(":").map(Number);
  return h * 2 + (m >= 30 ? 1 : 0);
}

/** 48 half-hour kinds from the sensor's "periods" attribute. */
function slotsFromPeriods(periods) {
  const slots = Array(48).fill("on");
  for (const period of periods || []) {
    const end = period.end === "24:00" ? 48 : toSlot(period.end);
    for (let i = toSlot(period.start); i < end; i++) slots[i] = period.kind;
  }
  return slots;
}

function demoData(t) {
  const now = new Date();
  const nowMinutes = kyivMinutes(now);
  const at = (minutes) => new Date(now.getTime() + (minutes - nowMinutes) * 60000);
  const slot = Math.floor(nowMinutes / 30);
  const clamp = (value) => Math.max(0, Math.min(48, value));
  const today = Array(48).fill("on");
  const fill = (slots, from, to, kind) => {
    for (let i = clamp(from); i < clamp(to); i++) slots[i] = kind;
  };
  fill(today, slot - 9, slot - 8, "possible");
  fill(today, slot - 8, slot - 5, "off");
  fill(today, slot + 3, slot + 4, "possible");
  const start = Math.min(slot + 4, 44);
  const end = Math.min(start + 5, 48);
  fill(today, start, end, "confirmed");
  const tomorrow = Array(48).fill("on");
  fill(tomorrow, 12, 17, "off");
  fill(tomorrow, 28, 32, "off");
  fill(tomorrow, 32, 33, "possible");
  const upcoming = start > slot;
  return {
    demo: true,
    title: `${t.queue} 1.1`,
    queue: "1.1",
    power: true,
    today,
    todayPublished: true,
    tomorrow,
    tomorrowPublished: true,
    nextOutage: upcoming ? at(start * 30) : null,
    restoration: upcoming ? at(end * 30) : null,
    outageContext: upcoming ? "next" : "none",
    emergency: true,
    emergencyAll: ["ГАВ 9"],
    emergencyQueues: [],
    updated: at(nowMinutes - 25),
  };
}

class MykolaivOutagesCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("mykolaiv-outages-card-editor");
  }

  static getStubConfig(hass) {
    const entry = Object.values(hass?.entities || {}).find(
      (item) => item.platform === DOMAIN && item.device_id,
    );
    return entry ? { device: entry.device_id } : {};
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._renderKey = "";
  }

  setConfig(config) {
    this._config = { show_tomorrow: true, ...config };
    this._renderKey = "";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  connectedCallback() {
    this._timer = setInterval(() => {
      this._renderKey = "";
      this._render();
    }, 30000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  getCardSize() {
    return this._config?.show_tomorrow === false ? 4 : 5;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _entities() {
    const found = {};
    if (!this._hass || !this._config?.device) return found;
    for (const entry of Object.values(this._hass.entities || {})) {
      if (
        entry.platform === DOMAIN &&
        entry.device_id === this._config.device &&
        KEYS.includes(entry.translation_key)
      ) {
        found[entry.translation_key] = entry.entity_id;
      }
    }
    return found;
  }

  _data() {
    if (!this._config?.device) return demoData(text(this._hass));
    const ids = this._entities();
    const state = (key) => (ids[key] ? this._hass.states[ids[key]] : undefined);
    const time = (key) => {
      const value = state(key)?.state;
      return value && !["unknown", "unavailable"].includes(value) ? new Date(value) : null;
    };
    const today = state("today");
    const tomorrow = state("tomorrow");
    const power = state("power");
    const emergency = state("emergency_power");
    const site = state("site");
    const bool = (item) =>
      !item || ["unavailable", "unknown"].includes(item.state) ? null : item.state === "on";
    const device = this._hass.devices?.[this._config.device];
    return {
      ids,
      // The queue has its own line, so drop the "(черга 1.1)" title suffix.
      title: (device?.name_by_user || device?.name || "").replace(/\s*\((черга|queue) [^)]*\)$/i, ""),
      queue: today?.attributes.queue,
      power:
        !power || power.state === "unavailable" || power.state === "unknown"
          ? null
          : power.state === "on",
      today: slotsFromPeriods(today?.attributes.periods),
      todayPublished: Boolean(today?.attributes.published) && today.state !== "unavailable",
      tomorrow: slotsFromPeriods(tomorrow?.attributes.periods),
      tomorrowPublished:
        Boolean(tomorrow?.attributes.published) && tomorrow.state !== "unavailable",
      nextOutage: time("next_outage"),
      restoration: time("restoration"),
      outageContext: state("restoration")?.attributes.outage,
      updated: time("last_update"),
      emergency: bool(emergency),
      emergencyQueues: emergency?.attributes.switched_off || [],
      emergencyAll: emergency?.attributes.queues || [],
      siteOk: bool(site),
      siteSince: site?.attributes.last_success ? new Date(site.attributes.last_success) : null,
      missing: !today && !power,
    };
  }

  _render() {
    // HA calls setConfig() before it assigns hass.
    if (!this._config || (this._config.device && !this._hass)) return;
    const t = text(this._hass);
    const data = this._data();
    const key = JSON.stringify([data, t === TEXT.uk, this._config]);
    if (key === this._renderKey) return;
    this._renderKey = key;

    const now = new Date();
    const title = escape(this._config.title || data.title || t.name);
    // An emergency switch-off means no power whatever the schedule queue says.
    const powered = data.emergency === false ? false : data.power;
    const powerClass = powered === null ? "unknown" : powered ? "on" : "off";
    const powerText = powered === null ? t.unknown : powered ? t.power_on : t.power_off;

    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="header" data-more="power">
          <div class="icon ${powerClass}">${powerClass === "off" ? ICON_OFF : ICON_ON}</div>
          <div class="heading">
            <div class="title">${title}</div>
            ${data.queue ? `<div class="sub">${t.queue} ${escape(data.queue)}</div>` : ""}
          </div>
          ${data.demo ? `<span class="badge demo">${t.example}</span>` : ""}
          <span class="badge ${powerClass}"><i></i>${powerText}</span>
        </div>
        ${data.missing ? `<div class="hint">${t.pick_device}</div>` : this._hero(data, t, now)}
        ${this._emergencyRow(data, t)}
        ${this._timeline(t.today, dayLabel(now, t, this._hass), data.today, data.todayPublished, t, now)}
        ${
          this._config.show_tomorrow === false
            ? ""
            : this._timeline(
                t.tomorrow,
                dayLabel(new Date(now.getTime() + 86400000), t, this._hass),
                data.tomorrow,
                data.tomorrowPublished,
                t,
                null,
              )
        }
        <div class="footer">
          <div class="legend">
            <span><i class="off"></i>${t.off}</span>
            <span><i class="confirmed"></i>${t.confirmed}</span>
            <span><i class="possible"></i>${t.possible}</span>
            <span><i class="on"></i>${t.on}</span>
          </div>
          ${
            data.siteOk === false && data.siteSince
              ? `<span class="stale" data-more="site">⚠ ${t.stale} ${clock(data.siteSince)}</span>`
              : data.updated
                ? `<span>${t.updated} ${clock(data.updated)}</span>`
                : ""
          }
        </div>
      </ha-card>`;

    this.shadowRoot.querySelectorAll("[data-more]").forEach((element) => {
      const entityId = data.ids?.[element.dataset.more];
      if (!entityId) return;
      element.classList.add("clickable");
      element.addEventListener("click", () => {
        this.dispatchEvent(
          new CustomEvent("hass-more-info", {
            detail: { entityId },
            bubbles: true,
            composed: true,
          }),
        );
      });
    });
  }

  _emergencyRow(data, t) {
    // Shown whenever the house has emergency queues, not only during an outage.
    if (!data.emergencyAll?.length) return "";
    const tone = data.emergency === null ? "unknown" : data.emergency ? "on" : "off";
    const status =
      data.emergency === null ? t.unknown : data.emergency ? t.power_on : t.emergency_off;
    return `
      <div class="emergency ${tone}" data-more="emergency_power">
        <span class="queues"><i></i>${t.emergency_queues}: ${escape(data.emergencyAll.join(", "))}</span>
        <span class="status">${status}</span>
      </div>`;
  }

  _hero(data, t, now) {
    let label;
    let value;
    let detail = "";
    let tone = "calm";
    const scheduledNow = data.outageContext === "current";
    if (data.emergency === false) {
      tone = "alert";
      label = t.outage_now;
      value = `${t.emergency_outage}${
        data.emergencyQueues.length ? ` · ${escape(data.emergencyQueues.join(", "))}` : ""
      }`;
      detail = t.emergency_detail;
    } else if (data.power === false || (scheduledNow && data.power === null)) {
      tone = "alert";
      label = t.outage_now;
      if (data.restoration) {
        value = `${t.until} ${clock(data.restoration)}`;
        detail = `${t.back_in} ${duration(data.restoration - now, t)}`;
      } else {
        value = t.restore_unknown;
      }
    } else if (scheduledNow) {
      // The schedule says off, but the operator reports power: trust the operator.
      tone = "next";
      label = t.scheduled_now;
      value = data.restoration ? `${t.until} ${clock(data.restoration)}` : t.restore_unknown;
    } else if (data.nextOutage) {
      tone = "next";
      label = t.next_outage;
      const end = data.outageContext === "next" ? data.restoration : null;
      value = end
        ? `${clock(data.nextOutage)} – ${clock(end)}`
        : clock(data.nextOutage);
      detail = `${t.in} ${duration(data.nextOutage - now, t)}`;
      if (end) detail += ` · ${t.lasts} ${duration(end - data.nextOutage, t)}`;
    } else {
      label = data.todayPublished ? t.no_outages : t.not_published;
    }
    return `
      <div class="hero ${tone}" data-more="${
        data.emergency === false ? "emergency_power" : tone === "alert" ? "restoration" : "next_outage"
      }">
        <div class="label">${label}</div>
        ${value ? `<div class="value">${value}</div>` : ""}
        ${detail ? `<div class="detail">${detail}</div>` : ""}
      </div>`;
  }

  _timeline(name, date, slots, published, t, now) {
    const head = `<div class="day"><span>${name}</span><span class="date">${date}</span></div>`;
    if (!published) {
      return `<div class="timeline">${head}<div class="pending">${t.tomorrow_pending}</div></div>`;
    }
    const current = now ? kyivMinutes(now) / 1440 : null;
    const cells = slots
      .map((kind, i) => {
        const start = `${String(Math.floor(i / 2)).padStart(2, "0")}:${i % 2 ? "30" : "00"}`;
        const endIndex = i + 1;
        const end =
          endIndex === 48
            ? "24:00"
            : `${String(Math.floor(endIndex / 2)).padStart(2, "0")}:${endIndex % 2 ? "30" : "00"}`;
        const past = current !== null && (i + 1) / 48 <= current ? " past" : "";
        return `<div class="cell ${kind}${past}" title="${start}–${end} · ${t[kind]}"></div>`;
      })
      .join("");
    const marker =
      current === null ? "" : `<div class="now" style="left:${(current * 100).toFixed(2)}%"></div>`;
    return `
      <div class="timeline">
        ${head}
        <div class="bar">${cells}${marker}</div>
        <div class="ticks"><span>00</span><span>06</span><span>12</span><span>18</span><span>24</span></div>
      </div>`;
  }
}

class MykolaivOutagesCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    const t = text(this._hass);
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (event) => {
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: event.detail.value },
            bubbles: true,
            composed: true,
          }),
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = { show_tomorrow: true, ...this._config };
    this._form.schema = [
      { name: "device", selector: { device: { integration: DOMAIN } } },
      { name: "title", selector: { text: {} } },
      { name: "show_tomorrow", selector: { boolean: {} } },
    ];
    this._form.computeLabel = (schema) => t[schema.name] || schema.name;
  }
}

const ICON_ON = `<svg viewBox="0 0 24 24"><path d="M11 15H6l7-14v8h5l-7 14z"/></svg>`;
const ICON_OFF = `<svg viewBox="0 0 24 24"><path d="M11 15H6l7-14v8h5l-7 14z" opacity=".55"/><path d="M3.3 4.7l1.4-1.4 16 16-1.4 1.4z"/></svg>`;

const STYLE = `
  :host { --mo-off: var(--error-color, #db4437); --mo-possible: var(--warning-color, #ffa600);
          --mo-on: var(--success-color, #43a047); }
  ha-card { padding: 16px; display: flex; flex-direction: column; gap: 14px; }
  .clickable { cursor: pointer; }
  .header { display: flex; align-items: center; gap: 12px; }
  .icon { width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center; flex: none;
          background: color-mix(in srgb, var(--mo-on) 18%, transparent); color: var(--mo-on); }
  .icon.off { background: color-mix(in srgb, var(--mo-off) 18%, transparent); color: var(--mo-off); }
  .icon.unknown { background: var(--secondary-background-color); color: var(--secondary-text-color); }
  .icon svg { width: 24px; height: 24px; fill: currentColor; }
  .heading { flex: 1; min-width: 0; }
  .title { font-size: 16px; font-weight: 600; line-height: 1.25; color: var(--primary-text-color);
           display: -webkit-box; -webkit-line-clamp: 2; overflow-wrap: anywhere; -webkit-box-orient: vertical; overflow: hidden; }
  .sub { font-size: 12px; color: var(--secondary-text-color); }
  .badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px;
           font-size: 12px; font-weight: 600; white-space: nowrap; flex: none;
           background: color-mix(in srgb, var(--mo-on) 16%, transparent); color: var(--mo-on); }
  .badge i { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
  .badge.off { background: color-mix(in srgb, var(--mo-off) 16%, transparent); color: var(--mo-off); }
  .badge.unknown, .badge.demo { background: var(--secondary-background-color); color: var(--secondary-text-color); }
  .hero { border-radius: 14px; padding: 12px 14px; background: var(--secondary-background-color); }
  .hero.alert { background: color-mix(in srgb, var(--mo-off) 14%, transparent); }
  .hero.next { background: color-mix(in srgb, var(--mo-possible) 14%, transparent); }
  .hero .label { font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
                 color: var(--secondary-text-color); }
  .hero .value { font-size: 22px; font-weight: 700; margin-top: 2px; color: var(--primary-text-color);
                 font-variant-numeric: tabular-nums; }
  .hero.calm .label { font-size: 15px; text-transform: none; letter-spacing: 0; font-weight: 600;
                      color: var(--primary-text-color); }
  .hero .detail { font-size: 13px; margin-top: 2px; color: var(--secondary-text-color); }
  .timeline .day { display: flex; justify-content: space-between; font-size: 13px; font-weight: 600;
                   color: var(--primary-text-color); margin-bottom: 6px; }
  .timeline .date { font-weight: 400; color: var(--secondary-text-color); }
  .bar { position: relative; display: grid; grid-template-columns: repeat(48, 1fr); gap: 2px; height: 22px; }
  .cell { border-radius: 3px; background: color-mix(in srgb, var(--mo-on) 30%, transparent); }
  .cell.off { background: color-mix(in srgb, var(--mo-off) 70%, transparent); }
  .cell.confirmed { background: var(--mo-off); }
  .cell.possible { background: color-mix(in srgb, var(--mo-possible) 75%, transparent); }
  .cell.past { opacity: .35; }
  .now { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; border-radius: 1px;
         background: var(--primary-text-color); box-shadow: 0 0 0 2px var(--card-background-color, #fff); }
  .ticks { display: flex; justify-content: space-between; font-size: 10px; margin-top: 3px;
           color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
  .pending { font-size: 13px; color: var(--secondary-text-color); padding: 10px 12px; border-radius: 10px;
             border: 1px dashed var(--divider-color); }
  .stale { color: var(--mo-possible); font-weight: 600; }
  .emergency { display: flex; align-items: center; justify-content: space-between; gap: 8px;
               padding: 8px 12px; border-radius: 10px; font-size: 13px;
               border: 1px solid var(--divider-color); color: var(--primary-text-color); }
  .emergency .queues { display: inline-flex; align-items: center; gap: 8px; min-width: 0; }
  .emergency i { width: 8px; height: 8px; border-radius: 50%; flex: none; background: var(--mo-on); }
  .emergency .status { font-weight: 600; color: var(--mo-on); white-space: nowrap; }
  .emergency.off { border-color: transparent;
                   background: color-mix(in srgb, var(--mo-off) 14%, transparent); }
  .emergency.off i { background: var(--mo-off); }
  .emergency.off .status { color: var(--mo-off); }
  .emergency.unknown i { background: var(--secondary-text-color); }
  .emergency.unknown .status { color: var(--secondary-text-color); }
  .hint { font-size: 13px; color: var(--secondary-text-color); }
  .footer { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 12px;
            font-size: 11px; color: var(--secondary-text-color); }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 12px; }
  .legend span { display: inline-flex; align-items: center; gap: 5px; }
  .legend i { width: 10px; height: 10px; border-radius: 3px; }
  .legend i.off { background: color-mix(in srgb, var(--mo-off) 70%, transparent); }
  .legend i.confirmed { background: var(--mo-off); }
  .legend i.on { background: color-mix(in srgb, var(--mo-on) 30%, transparent); }
  .legend i.possible { background: color-mix(in srgb, var(--mo-possible) 75%, transparent); }
`;

if (!customElements.get("mykolaiv-outages-card")) {
  customElements.define("mykolaiv-outages-card", MykolaivOutagesCard);
  customElements.define("mykolaiv-outages-card-editor", MykolaivOutagesCardEditor);
  window.customCards = window.customCards || [];
  const t = text({ language: navigator.language });
  window.customCards.push({
    type: "mykolaiv-outages-card",
    name: t.name,
    description: t.description,
    preview: true,
    documentationURL: "https://github.com/Fant0m771/ha_mykolaiv_outages",
  });
  console.info(`%c MYKOLAIV-OUTAGES-CARD %c ${CARD_VERSION} `, "color:#fff;background:#1e5aa8", "");
}
