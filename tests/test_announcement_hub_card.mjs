/* Runtime smoke tests: execute the actual Lovelace card source in Node.
 * No Home Assistant install, DOM library, CDN or network access needed.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const CARD_PATH = new URL("../custom_components/announcement_hub/frontend/announcement-hub-card.js", import.meta.url);
const HTML_PATH = new URL("../custom_components/announcement_hub/frontend/announcement-hub-card.html", import.meta.url);
const CSS_PATH = new URL("../custom_components/announcement_hub/frontend/announcement-hub-card.css", import.meta.url);
const registered = new Map();

globalThis.HTMLElement = class HTMLElement {
  attachShadow() {
    this.shadowRoot = {
      getElementById: () => null,
      replaceChildren: () => {},
    };
  }
};
globalThis.customElements = {
  define: (name, implementation) => registered.set(name, implementation),
  get: (name) => registered.get(name),
};
globalThis.window = { customCards: [] };
globalThis.document = {
  createElement: (name) => ({
    tagName: name, dataset: {}, attributes: {}, children: [],
    setAttribute(name, value) { this.attributes[name] = value; },
    appendChild(child) { this.children.push(child); },
  }),
};
await import(pathToFileURL(CARD_PATH.pathname).href);

const Card = registered.get("announcement-hub-card");
const Editor = registered.get("announcement-hub-card-editor");
const inputIds = [
  "message", "text-tts", "text-notify", "message-title", "ai-agent",
  "click-action", "tts-engine", "occupied-only", "manual-area", "manual-integration",
  "manual-device", "manual-entity",
];

function harness() {
  const card = new Card();
  card._mounted = true;
  const fields = Object.fromEntries(
    inputIds.map((name) => [name, { value: "", checked: name === "occupied-only" }])
  );
  fields.send = { disabled: false };
  fields["send-label"] = { textContent: "" };
  fields["priority-selected"] = { textContent: "" };
  fields.levels = {
    nodes: [],
    replaceChildren() { this.nodes = []; },
    appendChild(node) { this.nodes.push(node); },
  };
  fields["queue-number"] = { textContent: "" };
  fields["queue-pill"] = { title: "", hidden: false, setAttribute(key, value) { this[key] = value; } };
  fields["queue-panel"] = { hidden: true };
  fields["queue-list"] = { replaceChildren() {} };
  fields["queue-refresh"] = { disabled: false };
  fields["queue-close"] = { disabled: false };
  fields["queue-total"] = { textContent: "" };
  fields["queue-feedback"] = { textContent: "", hidden: true };
  fields["stop-clear-confirm"] = { hidden: true };
  fields["stop-clear"] = { disabled: false, setAttribute(k, v) { this[k] = v; } };
  fields["confirm-stop-clear"] = { disabled: false, focus() {} };
  fields["cancel-stop-clear"] = { disabled: false };
  fields["critical-confirm"] = { hidden: true };
  const notices = [];
  card.$ = (name) => {
    if (!fields[name]) throw new Error("Unmocked field: " + name);
    return fields[name];
  };
  card._notice = (message, success) => notices.push({ message, success });
  card._clearNotice = () => {};
  return { card, fields, notices };
}

test("card registers in Lovelace picker and exposes a graphical editor", () => {
  assert.equal(typeof Card, "function");
  assert.equal(typeof Editor, "function");
  assert.equal(Card.getConfigElement().tagName, "announcement-hub-card-editor");
  assert.equal(Card.getStubConfig().show_ai, true);
  assert.equal(new Card().getCardSize(), 4);
  assert.equal(window.customCards.filter((c) => c.type === "announcement-hub-card").length, 1);
});

test("bundled HTML/CSS support a modern card with safe input controls", () => {
  const html = readFileSync(HTML_PATH, "utf8");
  const css = readFileSync(CSS_PATH, "utf8");
  for (const id of ["message", "text-tts", "text-notify", "message-title",
    "area-options", "integration-options", "device-options", "entity-options",
    "level", "channels", "ai-choices", "send", "critical-confirm",
    "stop-clear", "stop-clear-confirm", "confirm-stop-clear", "cancel-stop-clear",
    "queue-pill", "queue-panel", "queue-list", "queue-refresh", "queue-close",
    "priority-selected",
  ]) {
    const actual = id === "level" ? "levels" : id;
    assert.match(html, new RegExp("id=" + JSON.stringify(actual)));
  }
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /max-width:550px/);
  assert.match(css, /--primary-text-color/);
  assert.match(html, /role="status"/);
  assert.doesNotMatch(html, /<script\b/i);
  assert.doesNotMatch(css, /https?:\/\//i);
});

test("automatic routing sends no forced recipient or service", () => {
  const { card, fields } = harness();
  fields.message.value = "Laundry finished";
  assert.deepEqual(card._buildPayload(), {
    level: "info", occupied_only: true, text: "Laundry finished",
  });
});

test("manual area sends only selected recipient channel", () => {
  const { card, fields } = harness();
  card._targetMode = "targeted";
  card._channel = "notification";
  card._level = "warning";
  card._selected.area.add("kitchen");
  fields.message.value = "Kitchen window open";
  assert.deepEqual(card._buildPayload(), {
    level: "warning", occupied_only: true, manual_targets: true, area: ["kitchen"],
    text: "Kitchen window open", service: ["notification"],
  });
});

test("combining an area, integration, device and entity preserves all targets", () => {
  const { card, fields } = harness();
  card._targetMode = "targeted";
  card._channel = "all";
  card._selected.area.add("kitchen");
  card._selected.integration.add("nfandroidtv");
  card._selected.device.add("device-123");
  card._selected.entity.add("notify.phone");
  fields["manual-entity"].value = "notify.phone,notify.tablet";
  fields.message.value = "Dinner is ready";
  assert.deepEqual(card._buildPayload(), {
    level: "info", occupied_only: true, manual_targets: true,
    area: ["kitchen"], integration: ["nfandroidtv"],
    device: ["device-123"],
    entity: ["notify.phone", "notify.tablet"],
    service: ["all"], text: "Dinner is ready",
  });
});

test("an exact phone notification never adds a TTS or Snapcast recipient", () => {
  const { card, fields } = harness();
  card._targetMode = "targeted";
  card._channel = "notification";
  card._selected.entity.add("notify.phone");
  fields["text-notify"].value = "Please check the door";
  assert.deepEqual(card._buildPayload(), {
    level: "info", occupied_only: true, manual_targets: true,
    entity: ["notify.phone"], service: ["notification"],
    text_notify: "Please check the door",
  });
});

test("phone speech uses exactly the chosen Companion TTS service and target", () => {
  const { card, fields } = harness();
  card._targetMode = "targeted";
  card._channel = "companion_tts";
  card._selected.integration.add("mobile_app");
  fields["text-tts"].value = "The timer has ended";
  assert.deepEqual(card._buildPayload(), {
    level: "info", occupied_only: true, manual_targets: true,
    integration: ["mobile_app"], service: ["companion_tts"],
    text_tts: "The timer has ended",
  });
});

test("AI generation with blank title leaves title out for a three-word AI title", () => {
  const { card, fields } = harness();
  fields.message.value = "Tell the household in Greek that laundry is done";
  card._ai = "generate";
  assert.deepEqual(card._buildPayload(), {
    level: "info", occupied_only: true,
    text: "Tell the household in Greek that laundry is done",
    use_ai: true, ai_mode: "generate",
  });
  fields["message-title"].value = "My Title";
  assert.equal(card._buildPayload().title, "My Title");
});

test("AI off is explicit and keeps independent speech and visual text", () => {
  const { card, fields } = harness();
  card._ai = "off";
  fields.message.value = "Laundry";
  fields["text-tts"].value = "Speech version";
  fields["text-notify"].value = "Written version";
  const body = card._buildPayload();
  assert.equal(body.use_ai, false);
  assert.equal(body.ai_mode, undefined);
  assert.equal(body.text_tts, "Speech version");
  assert.equal(body.text_notify, "Written version");
});

test("service only with automatic recipient mode is rejected, not broadcast", () => {
  const { card, fields } = harness();
  fields.message.value = "Hi";
  card._channel = "tts";
  assert.throws(() => card._buildPayload(), /requires a room or exact recipient/);
});

test("targeted mode with no actual selection fails closed", () => {
  const { card, fields } = harness();
  fields.message.value = "Hi";
  card._targetMode = "targeted";
  assert.throws(() => card._buildPayload(), /Choose a room or explicit recipient/);
});

test("empty announcement cannot be queued", () => {
  const { card } = harness();
  assert.throws(() => card._buildPayload(), /Enter an announcement/);
});

test("send calls the one supported Hub service with response flag, no duplicate send", async () => {
  const { card, fields, notices } = harness();
  fields.message.value = "Washing machine done";
  let calls = 0;
  card._hass = { callService: async (...args) => {
    calls += 1;
    assert.deepEqual(args.slice(0, 2), ["notify", "announcement_hub"]);
    assert.deepEqual(args[2], {
      level: "info", occupied_only: true, text: "Washing machine done",
    });
    assert.equal(args[5], true);
    assert.equal(fields.send.disabled, true);
    return { context: { id: "test" }, response: {
      accepted: true, job_id: "948f37d533f1486a997a4d44b7054ed1",
    } };
  }};
  await Promise.all([card._send(), card._send()]);
  assert.equal(calls, 1);
  assert.equal(fields.send.disabled, false);
  assert.equal(notices.length, 1);
  assert.equal(notices[0].success, true);
  assert.match(notices[0].message, /Queued #948f37d533/);
});

test("errors do not retry automatically or claim delivery", async () => {
  const { card, fields, notices } = harness();
  fields.message.value = "Door open";
  let count = 0;
  card._hass = { callService: async () => { count++; throw new Error("Provider offline"); } };
  await card._send();
  assert.equal(count, 1);
  assert.equal(notices.length, 1);
  assert.equal(notices[0].success, false);
  assert.match(notices[0].message, /Check the queue before retrying/);
});

test("Stop & Clear requires explicit confirmation and stops active jobs with the queue", async () => {
  const { card, fields, notices } = harness();
  let calls = 0;
  card._hass = {
    callService: async (...args) => {
      calls++;
      assert.deepEqual(args, [
        "announcement_hub", "clear_queue", { include_current: true },
        undefined, false, true,
      ]);
      assert.equal(fields["stop-clear"].disabled, true);
      assert.equal(fields.send.disabled, true);
      return { context: { id: "test" }, response: {
        cleared: 12, active_cancel_requested: 2, queue_size: 0,
      } };
    },
  };
  await card._stopAndClear();
  assert.equal(calls, 0, "first tap cannot execute a destructive operation");
  card._stopConfirming = true;
  await Promise.all([card._stopAndClear(), card._stopAndClear()]);
  assert.equal(calls, 1, "repeated confirmation cannot clear twice");
  assert.equal(fields["stop-clear"].disabled, false);
  assert.equal(fields.send.disabled, false);
  assert.equal(fields["stop-clear-confirm"].hidden, true);
  assert.equal(fields["stop-clear"]["aria-expanded"], "false");
  assert.equal(notices.length, 1);
  assert.equal(notices[0].success, true);
  assert.match(notices[0].message, /Cleared 12 queued jobs/);
});

test("Stop & Clear fails safely without an automatic retry", async () => {
  const { card, notices } = harness();
  let calls = 0;
  card._hass = { callService: async () => { calls++; throw new Error("Device unavailable"); } };
  card._stopConfirming = true;
  await card._stopAndClear();
  assert.equal(calls, 1);
  assert.equal(notices.length, 1);
  assert.equal(notices[0].success, false);
  assert.match(notices[0].message, /Check the queue before retrying/);
});

test("Stop & Clear cannot race a pending send on this card", async () => {
  const { card, notices } = harness();
  card._sending = true;
  card._stopConfirming = true;
  card._hass = { callService: async () => { throw new Error("should not call service"); } };
  await card._stopAndClear();
  assert.equal(notices.length, 0);
});


test("compact card keeps message/title/icon priority visible and folds all other sections", () => {
  const html = readFileSync(HTML_PATH, "utf8");
  const css = readFileSync(CSS_PATH, "utf8");
  assert.match(html, /id="message"/);
  assert.match(html, /id="message-title"/);
  assert.match(html, /id="levels" class="choices priority-pills"/);
  assert.match(html, /<details class="section folded-section" id="recipients-section">/);
  assert.match(html, /<details class="section folded-section" id="delivery-section">/);
  assert.doesNotMatch(html, /id="recipients-section" open/);
  assert.doesNotMatch(html, /id="delivery-section" open/);
  assert.doesNotMatch(html, /class="kicker"/);
  assert.match(css, /h2\{[^}]*white-space:nowrap/);
  const js = readFileSync(CARD_PATH, "utf8");
  for (const severity of ["info", "success", "warning", "error", "critical", "debug"]) {
    assert.match(js, new RegExp(severity + ': "mdi:'));
  }
  assert.match(js, /symbol\.setAttribute\("icon", LEVEL_ICONS\[level\]\)/);
});

test("mobile card keeps title and priority icons separate even inside narrow dashboard columns", () => {
  const css = readFileSync(CSS_PATH, "utf8");
  const html = readFileSync(HTML_PATH, "utf8");
  // A responsive dashboard grid can be narrow on a WIDE viewport,
  // so use the card's own size in addition to the viewport fallback.
  assert.match(css, /ha-card\s*\{[^}]*container-name:\s*announcement-hub-card/);
  assert.match(css, /ha-card\s*\{[^}]*container-type:\s*inline-size/);
  const narrow = css.split("@container announcement-hub-card (max-width:430px) {")[1];
  assert.ok(narrow, "narrow-card container query missing");
  const inner = narrow.split("@container announcement-hub-card (max-width:300px) {")[0];
  assert.match(inner, /\.compose-details\s*\{\s*grid-template-columns:minmax\(0,1fr\)/);
  assert.match(inner, /\.priority-pills\s*\{\s*flex-wrap:wrap;\s*overflow:visible;\s*justify-content:flex-start/);
  assert.match(inner, /\.priority-pills button\s*\{\s*flex:0 0 30px/);
  const header = css.split("@container announcement-hub-card (max-width:300px) {")[1];
  assert.match(header, /\.top\s*\{\s*grid-template-columns:minmax\(0,1fr\)/);
  assert.match(header, /\.top-actions\s*\{\s*width:100%/);
  // Older mobile WebViews still get the stacked title/priority layout.
  const fallback = css.slice(css.lastIndexOf("@media(max-width:550px)"));
  assert.match(fallback, /\.compose-details\s*\{\s*grid-template-columns:minmax\(0,1fr\)/);
  assert.match(fallback, /\.priority-pills\s*\{\s*flex-wrap:wrap/);
  assert.match(css, /#card-heading\s*\{[^}]*text-overflow:ellipsis/);
  assert.match(html, /class="compose-details"/);
  assert.match(html, /class="field compact-title"/);
  assert.match(html, /class="field compact-priority"/);
});


test("priority label stays visible and follows the selected icon in Greek", () => {
  const { card, fields } = harness();
  const html = readFileSync(HTML_PATH, "utf8");
  const css = readFileSync(CSS_PATH, "utf8");
  assert.match(html, /<output id="priority-selected" aria-live="polite">Info<\/output>/);
  assert.match(html, /class="priority-caption"/);
  assert.match(css, /\.priority-caption output\{/);
  card._translations = { "Warning": "Προειδοποίηση", "Critical": "Κρίσιμο" };
  card._level = "warning";
  card._renderPriority();
  assert.equal(fields["priority-selected"].textContent, "Προειδοποίηση");
  assert.equal(fields.levels.nodes.length, 6);
  assert.equal(fields.levels.nodes.filter((node) =>
    node.attributes["aria-pressed"] === "true").length, 1);
  assert.equal(fields.levels.nodes.find((node) =>
    node.attributes["aria-pressed"] === "true").dataset.value, "warning");
  card._level = "critical";
  card._renderPriority();
  assert.equal(fields["priority-selected"].textContent, "Κρίσιμο");
  assert.equal(fields.levels.nodes.find((node) =>
    node.attributes["aria-pressed"] === "true").dataset.value, "critical");
});

test("empty wrapped queue payload reports a problem rather than inventing messages", async () => {
  const { card } = harness();
  card._queueOpen = true;
  card._renderQueue = () => {};
  card._hass = { callService: async () => ({
    context: { id: "test" }, response: null,
  }) };
  await card._fetchQueue();
  assert.match(card._queueError, /Invalid queue response/);
  assert.equal(card._queueJobs.length, 0);
});

test("HA-wrapped cancellation confirms removal without a duplicate service call", async () => {
  const { card } = harness();
  const calls = [];
  card._queueOpen = true;
  card._renderQueue = () => {};
  card._queueJobs = [{ job_id: "j1" }];
  card._hass = { callService: async (...args) => {
    calls.push(args);
    return { context: { id: "test" }, response: { status: "cancelled", job_id: "j1" } };
  }};
  card._fetchQueue = async () => {};
  await card._queueAction("remove", "j1");
  assert.equal(calls.length, 0);
  await card._queueAction("confirm-remove", "j1");
  assert.equal(calls.length, 1);
  assert.equal(card._queueError, "");
  assert.equal(card._queueRemoveId, null);
});

test("legacy flat-shaped service response is still accepted", async () => {
  const { card } = harness();
  card._queueOpen = true;
  card._renderQueue = () => {};
  card._hass = { callService: async () => ({
    jobs: [{ job_id: "flat", text_notify: "old", active: false }],
    active: [],
  }) };
  await card._fetchQueue();
  assert.equal(card._queueError, "");
  assert.equal(card._queueJobs[0].job_id, "flat");
});

test("tapping the queue badge loads all message bodies only through authenticated service", async () => {
  const { card, fields } = harness();
  const requests = [];
  card._renderQueue = () => {};
  card._hass = { callService: async (...args) => {
    requests.push(args);
    // Actual Home Assistant 2026 frontend return shape is {context,response}.
    return { context: { id: "test" }, response: { jobs: [
      { job_id: "j1", title: "Open door", text_notify: "PRIVATE_MESSAGE_ONE",
        text_tts: null, level: "info", status: "pending", active: false },
      { job_id: "j2", title: "Wash", text_tts: "PRIVATE_MESSAGE_TWO",
        text_notify: null, level: "warning", status: "pending", active: false },
    ], active: [], queue_size: 2 } };
  }};
  card._toggleQueue(true);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(fields["queue-panel"].hidden, false);
  assert.equal(fields["queue-pill"]["aria-expanded"], "true");
  assert.equal(card._queueJobs.length, 2);
  assert.equal(card._queueJobs[0].text_notify, "PRIVATE_MESSAGE_ONE");
  assert.equal(card._queueJobs[1].text_tts, "PRIVATE_MESSAGE_TWO");
  assert.deepEqual(requests[0], [
    "announcement_hub", "list_queue", {}, undefined, false, true,
  ]);
  card._toggleQueue(false);
  assert.equal(card._queueJobs.length, 0, "private text is cleared when panel closes");
  assert.equal(fields["queue-panel"].hidden, true);
});

test("queue move is durable and sends the expected adjacent job guard", async () => {
  const { card } = harness();
  const requests = [];
  card._queueOpen = true;
  card._renderQueue = () => {};
  card._queueJobs = [
    { job_id: "j1" }, { job_id: "j2" }, { job_id: "j3" },
  ];
  card._hass = { callService: async (...args) => {
    requests.push(args);
    return { context: { id: "test" }, response: {
      moved: true, job_id: "j3", queue_size: 3,
    } };
  }};
  card._fetchQueue = async () => {};
  await card._queueAction("up", "j3");
  assert.equal(requests.length, 1);
  assert.deepEqual(requests[0], [
    "announcement_hub", "reorder_queue",
    { job_id: "j3", direction: "up", neighbor_job_id: "j2" },
    undefined, false, true,
  ]);
  assert.equal(card._queueBusy, false);
});

test("remove requires a second click and never repeats a failed cancellation", async () => {
  const { card } = harness();
  const requests = [];
  card._queueOpen = true;
  card._renderQueue = () => {};
  card._queueJobs = [{ job_id: "j1" }];
  card._hass = { callService: async (...args) => {
    requests.push(args);
    throw new Error("Device offline");
  }};
  card._fetchQueue = async () => {};
  await card._queueAction("remove", "j1");
  assert.equal(requests.length, 0);
  assert.equal(card._queueRemoveId, "j1");
  await card._queueAction("confirm-remove", "j1");
  assert.equal(requests.length, 1);
  assert.deepEqual(requests[0], [
    "announcement_hub", "cancel", { job_id: "j1" }, undefined, false, true,
  ]);
  assert.match(card._queueError, /Could not change queue/);
  await card._queueAction("keep", "j1");
  assert.equal(card._queueRemoveId, null);
});

test("queue renders dynamic messages as text, never untrusted HTML", () => {
  const js = readFileSync(CARD_PATH, "utf8");
  const block = js.split("    _renderQueue() {", 2)[1].split("    async _queueAction(", 1)[0];
  assert.match(block, /value\.textContent = content/);
  assert.match(block, /title\.textContent = item\.title/);
  assert.doesNotMatch(block, /innerHTML|insertAdjacentHTML|eval\(/);
});

test("module does not embed external JS/CSS dependencies or unsafe user markup", () => {
  const js = readFileSync(CARD_PATH, "utf8");
  assert.doesNotMatch(js, /\bimport\s*\(\s*["']https?:/);
  assert.match(js, /button.textContent =/);
  assert.match(js, /template.innerHTML = html; \/* Trusted/);
  assert.match(js, /getStubConfig\(/);
  assert.match(js, /callWS/);
  assert.match(js, /config\/area_registry\/list/);
});


test("Greek, German and regional languages use correct card translations", async () => {
  const path = new URL("../custom_components/announcement_hub/frontend/announcement-hub-locales.json", import.meta.url);
  const payload = JSON.parse(readFileSync(path, "utf8"));
  globalThis.fetch = async (url) => {
    assert.equal(url, "/announcement_hub/announcement-hub-locales.json");
    return { ok: true, json: async () => payload };
  };
  const card = new Card();
  card._hass = { language: "el" };
  await card._applyLocale();
  assert.equal(card._t("Send announcement"), "Αποστολή ανακοίνωσης");
  assert.equal(card._t("Stop & Clear"), "Διακοπή & Εκκαθάριση");
  assert.equal(card._t("Confirm"), "Επιβεβαίωση");
  assert.equal(card._t("Queued #{id}{related}. Delivery will follow Hub routing.",
    { id: "12345", related: "" }).includes("12345"), true);
  card._hass = { locale: { language: "de-DE" } };
  await card._applyLocale();
  assert.equal(card._t("Send announcement"), "Ankündigung senden");
  assert.equal(card._t("Stop & Clear"), "Stopp & Leeren");
  card._hass = { locale: { language: "pt-BR" } };
  await card._applyLocale();
  assert.equal(card._t("Send announcement"), "Enviar anúncio");
  card._hass = { locale: { language: "zh-TW" } };
  await card._applyLocale();
  assert.equal(card._t("Choose recipients"), "選擇接收者");
  card._hass = { locale: { language: "es-ES" } };
  await card._applyLocale();
  assert.equal(card._t("Choose recipients"), "Elegir destinatarios");
  card._hass = { language: "zz" };
  await card._applyLocale();
  assert.equal(card._t("Send announcement"), "Send announcement");
});


test("person mode selects named destinations, not device entity IDs", () => {
  const { card, fields } = harness();
  fields.message.value = "Η πόρτα είναι ανοιχτή.";
  card._targetMode = "person";
  card._selected.person.add("person.alex");
  card._selected.person.add("person.maria");
  card._personDestinations = new Set(["mobile", "watch"]);
  assert.deepEqual(card._buildPayload(), {
    level: "info", occupied_only: true,
    target_person: ["person.alex", "person.maria"],
    person_destination: ["mobile", "watch"],
    text: "Η πόρτα είναι ανοιχτή.",
  });
  assert.ok(!Object.hasOwn(card._buildPayload(), "entity"));
  assert.ok(!Object.hasOwn(card._buildPayload(), "manual_targets"));
});

test("person mode rejects unselected people or empty destinations", () => {
  const { card, fields } = harness();
  card._targetMode = "person";
  fields.message.value = "Alert";
  assert.throws(() => card._buildPayload(), /Choose at least one person/);
  card._selected.person.add("person.alex");
  card._personDestinations.clear();
  assert.throws(() => card._buildPayload(), /Choose at least one person destination/);
});

test("only room and destinations assigned for all selected people appear", () => {
  const { card } = harness();
  card._selected.person.add("person.alex");
  card._selected.person.add("person.maria");
  card._hass = { states: {
    "sensor.announcement_hub_queue": {
      entity_id: "sensor.announcement_hub_queue",
      attributes: { person_destinations: {
        "person.alex": ["room", "mobile", "watch"],
        "person.maria": ["room", "mobile"],
      }},
    },
  }};
  assert.deepEqual(card._availablePersonDestinations(), ["room", "mobile"]);
});

test("person translation override is optional and maps to action boolean", () => {
  const { card, fields } = harness();
  card._targetMode = "person";
  card._selected.person.add("person.alex");
  fields.message.value = "Door open";
  assert.equal(card._buildPayload().person_translate, undefined);
  card._personTranslation = "on";
  assert.equal(card._buildPayload().person_translate, true);
  card._personTranslation = "off";
  assert.equal(card._buildPayload().person_translate, false);
});

test("person greeting and room chime are explicit tri-state overrides", () => {
  const { card, fields } = harness();
  card._targetMode = "person";
  card._selected.person.add("person.alex");
  fields.message.value = "Dinner ready";
  const baseline = card._buildPayload();
  assert.equal(baseline.person_greeting, undefined);
  assert.equal(baseline.pre_announce_sound, undefined);
  card._personGreeting = "on";
  card._preChime = "off";
  fields["tts-engine"].value = "tts.piper";
  const changed = card._buildPayload();
  assert.equal(changed.person_greeting, true);
  assert.equal(changed.pre_announce_sound, false);
  assert.equal(changed.tts_engine, "tts.piper");
});
