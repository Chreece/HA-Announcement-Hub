/* Announcement Hub Lovelace composer. No external JavaScript dependencies.
 * All dynamic provider/user content is inserted with textContent and DOM data
 * properties, never with HTML interpolation.
 */
(() => {
  "use strict";
  const TYPE = "announcement-hub-card";
  const ROOT = "/announcement_hub/";
  const DOC_URL = "https://github.com/Chreece/HA-Announcement-Hub#dashboard-card";
  const LEVELS = [
    ["info", "Info"], ["success", "Success"], ["warning", "Warning"],
    ["error", "Error"], ["critical", "Critical"], ["debug", "Debug"],
  ];
  const CHANNELS = [
    ["auto", "Automatic"], ["notification", "Written"], ["tts", "Speech"],
    ["all", "Both"], ["snapcast", "Snapcast"], ["companion_tts", "Phone speech"],
  ];
  const AI_OPTIONS = [
    ["inherit", "Hub default"], ["off", "Off"],
    ["rewrite", "Rewrite"], ["generate", "Generate"],
  ];
  const KINDS = ["area", "integration", "device", "entity"];
  const getLanguage = (hass) => {
    const raw = String(hass?.locale?.language || hass?.language || "en").replace(/_/g, "-");
    if (/^zh-(tw|hk|hant)/i.test(raw)) return "zh-Hant";
    if (/^zh/i.test(raw)) return "zh-Hans";
    if (/^pt-br/i.test(raw)) return "pt-BR";
    return raw.split("-")[0].toLowerCase();
  };
  let localeCache = null;
  function loadLocales() {
    if (!localeCache) localeCache = fetch(ROOT + "announcement-hub-locales.json", { credentials: "same-origin" })
      .then((r) => r.ok ? r.json() : {}).catch(() => ({}));
    return localeCache;
  }
  function translation(dict, key, params = {}) {
    const value = dict?.[key] || key;
    return value.replace(/\{([a-z]+)\}/g, (_, k) => String(params[k] ?? ""));
  }
  function localize(root, dictionary, originals) {
    if (!root?.querySelectorAll) return;
    for (const el of root.querySelectorAll("*")) {
      if (el.tagName === "STYLE" || el.tagName === "SCRIPT") continue;
      for (const attribute of ["placeholder", "aria-label", "title"]) {
        if (!el.hasAttribute?.(attribute)) continue;
        const originalAttr = "data-hub-original-" + attribute;
        if (!el.hasAttribute(originalAttr)) el.setAttribute(originalAttr, el.getAttribute(attribute));
        el.setAttribute(attribute, translation(dictionary, el.getAttribute(originalAttr)));
      }
      for (const node of el.childNodes || []) {
        if (node.nodeType !== 3 || !node.nodeValue.trim()) continue;
        if (!originals.has(node)) originals.set(node, node.nodeValue);
        const source = originals.get(node);
        node.nodeValue = source.replace(source.trim(), translation(dictionary, source.trim()));
      }
    }
  }
  let assetPromise = null;

  function assets() {
    if (!assetPromise) {
      assetPromise = Promise.all(
        ["announcement-hub-card.html", "announcement-hub-card.css"].map(async (name) => {
          const response = await fetch(ROOT + name, { credentials: "same-origin" });
          if (!response.ok) throw new Error("Unable to load " + name + " (" + response.status + ").");
          return response.text();
        })
      ).catch((error) => {
        assetPromise = null;
        throw error;
      });
    }
    return assetPromise;
  }

  function uniq(values) {
    return Array.from(new Set(values.map((value) => String(value).trim()).filter(Boolean)));
  }
  function csv(value) { return uniq(String(value || "").split(",")); }
  function titleCase(value) {
    return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
  }
  function clipped(value, max) {
    const text = String(value || "");
    return text.length > max ? text.slice(0, max - 1) + "…" : text;
  }

  class AnnouncementHubCard extends HTMLElement {
    static getStubConfig() {
      return {
        title: "Announcement Hub",
        default_level: "info",
        show_queue: true,
        show_ai: true,
        clear_after_send: false,
      };
    }
    static getConfigElement() {
      return document.createElement("announcement-hub-card-editor");
    }
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = AnnouncementHubCard.getStubConfig();
      this._selected = Object.fromEntries(KINDS.map((kind) => [kind, new Set()]));
      this._registry = { area: [], integration: [], device: [], entity: [] };
      this._level = "info";
      this._channel = "auto";
      this._ai = "inherit";
      this._targetMode = "automatic";
      this._mounted = false;
      this._mounting = false;
      this._loaded = false;
      this._loading = false;
      this._sending = false;
      this._confirming = false;
      this._localeCode = null;
      this._localeRendered = false;
      this._translations = {};
      this._originalNodes = new WeakMap();
    }
    _t(key, args) { return translation(this._translations, key, args); }
    async _applyLocale() {
      const language = getLanguage(this._hass);
      if (this._localeCode === language && this._localeRendered) return;
      const dictionaries = await loadLocales();
      this._localeCode = language;
      this._translations = dictionaries[language] || {};
      if (typeof this.setAttribute === "function") this.setAttribute("dir", language === "ar" ? "rtl" : "ltr");
      if (this._mounted) {
        localize(this.shadowRoot, this._translations, this._originalNodes);
        this._localeRendered = true;
        this._sync();
        for (const kind of KINDS) this._drawOptions(kind);
      }
    }
    setConfig(config) {
      if (!config || typeof config !== "object") throw new Error("Announcement Hub card needs a configuration.");
      this._config = { ...AnnouncementHubCard.getStubConfig(), ...config };
      if (!LEVELS.some((item) => item[0] === this._config.default_level)) this._config.default_level = "info";
      if (!this._mounted) this._level = this._config.default_level;
      void this._mount();
      this._sync();
    }
    set hass(value) {
      this._hass = value;
      void this._applyLocale();
      if (this._mounted) {
        this._updateQueue();
        if (!this._loaded && !this._loading) void this._loadRegistry();
      }
    }
    connectedCallback() { void this._mount(); }
    getCardSize() { return 8; }
    getLayoutOptions() {
      return { grid_columns: 6, grid_rows: 8, grid_min_columns: 3, grid_min_rows: 5 };
    }
    $(name) { return this.shadowRoot.getElementById(name); }

    async _mount() {
      if (this._mounted || this._mounting) return;
      this._mounting = true;
      try {
        const [html, css] = await assets();
        const style = document.createElement("style");
        style.textContent = css;
        const template = document.createElement("template");
        template.innerHTML = html; // Trusted, package-bundled markup only.
        this.shadowRoot.replaceChildren(style, template.content.cloneNode(true));
        this._mounted = true;
        this._bind();
        await this._applyLocale();
        this._sync();
        if (this._hass) await this._loadRegistry();
      } catch (error) {
        const notice = document.createElement("ha-card");
        notice.textContent = "Announcement Hub card couldn't load its assets. Check the resource URL and integration installation: " + error.message;
        this.shadowRoot.replaceChildren(notice);
      } finally {
        this._mounting = false;
      }
    }

    _bind() {
      const pick = (id, prop) => this.$(id).addEventListener("click", (event) => {
        const button = event.target.closest("button[data-value]");
        if (!button) return;
        this[prop] = button.dataset.value;
        this._confirming = false;
        this.$("critical-confirm").hidden = true;
        this._sync();
      });
      pick("levels", "_level");
      pick("channels", "_channel");
      pick("ai-choices", "_ai");
      this.$("target-mode").addEventListener("click", (event) => {
        const mode = event.target.closest("button[data-mode]")?.dataset.mode;
        if (!mode) return;
        this._targetMode = mode;
        this._confirming = false;
        this.$("critical-confirm").hidden = true;
        this._sync();
      });
      this.$("targets").addEventListener("click", (event) => {
        const button = event.target.closest("button[data-kind][data-value]");
        if (!button) return;
        const kind = button.dataset.kind;
        const value = button.dataset.value;
        if (!this._selected[kind]) return;
        if (this._selected[kind].has(value)) this._selected[kind].delete(value);
        else this._selected[kind].add(value);
        this._drawOptions(kind);
        this._drawChosen();
      });
      for (const kind of KINDS) {
        this.$(kind + "-search").addEventListener("input", () => this._drawOptions(kind));
        this.$("manual-" + kind).addEventListener("input", () => this._updateSummary());
      }
      this.$("message-title").addEventListener("input", () => this._updateAIHint());
      this.$("message").addEventListener("input", () => this._clearNotice());
      this.$("send").addEventListener("click", () => {
        if (this._sending) return;
        if (this._level === "critical") {
          // Only the dedicated Confirm button can submit a Critical send.
          // Repeated taps on Send must never bypass confirmation.
          this._confirming = true;
          this.$("critical-confirm").hidden = false;
          this.$("confirm-critical").focus();
          return;
        }
        void this._send();
      });
      this.$("confirm-critical").addEventListener("click", () => void this._send());
      this.$("cancel-critical").addEventListener("click", () => {
        this._confirming = false;
        this.$("critical-confirm").hidden = true;
      });
      this.$("occupied-only").addEventListener("change", () => this._updateSummary());
    }

    _renderButtons(id, choices, selected) {
      const target = this.$(id);
      target.replaceChildren();
      for (const [value, name] of choices) {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.value = value;
        button.textContent = this._t(name);
        button.setAttribute("aria-pressed", String(value === selected));
        target.appendChild(button);
      }
    }

    _sync() {
      if (!this._mounted) return;
      this.$("card-heading").textContent = this._config.title || this._t("Announcement Hub");
      this.$("queue-pill").hidden = this._config.show_queue === false;
      this.$("ai-block").hidden = this._config.show_ai === false;
      this._renderButtons("levels", LEVELS, this._level);
      this._renderButtons("channels", CHANNELS, this._channel);
      this._renderButtons("ai-choices", AI_OPTIONS, this._ai);
      this.$("targets").hidden = this._targetMode !== "targeted";
      for (const button of this.$("target-mode").querySelectorAll("button[data-mode]")) {
        button.setAttribute("aria-pressed", String(button.dataset.mode === this._targetMode));
      }
      this.$("routing-explanation").textContent = this._targetMode === "automatic"
        ? this._t("Announcement Hub chooses configured recipients using occupancy and fallback rules.")
        : this._t("Select recipients bypasses the default output lists: only chosen rooms and exact integrations/devices/entities are eligible.");
      this._updateAIHint();
      this._drawChosen();
      this._updateQueue();
    }

    _updateAIHint() {
      if (!this._mounted) return;
      const descriptions = {
        inherit: "Use Announcement Hub's configured AI setting.",
        off: "Use your exact wording, without AI rewriting.",
        rewrite: "Polish the message without changing its facts.",
        generate: "Generate the announcement from your instructions. An omitted title becomes an AI heading of at most 3 words.",
      };
      this.$("ai-explanation").textContent = this._t(descriptions[this._config.show_ai === false ? "inherit" : this._ai]);
      this.$("message-title").placeholder = this._config.show_ai !== false && this._ai === "generate"
        ? this._t("AI will generate up to 3 words") : this._t("Optional title");
    }

    async _loadRegistry() {
      if (!this._hass?.callWS || this._loading) return;
      this._loading = true;
      try {
        const commands = ["config/area_registry/list", "config/device_registry/list", "config/entity_registry/list"];
        const results = await Promise.allSettled(commands.map((type) => this._hass.callWS({ type })));
        const get = (index) => results[index].status === "fulfilled" && Array.isArray(results[index].value) ? results[index].value : [];
        const areas = get(0);
        const devices = get(1);
        const entities = get(2).filter((entity) => /^(notify|media_player)\./.test(entity.entity_id) && !entity.disabled_by);
        this._registry.area = areas.map((area) => ({ value: area.area_id, label: area.name || area.area_id }));
        const activeDevices = new Set(entities.map((entity) => entity.device_id).filter(Boolean));
        this._registry.device = devices.filter((device) => activeDevices.has(device.id))
          .map((device) => ({ value: device.id, label: device.name_by_user || device.name || device.id }));
        this._registry.entity = entities.map((entity) => ({
          value: entity.entity_id,
          label: (entity.name || entity.original_name || entity.entity_id) + " · " + entity.entity_id,
        }));
        const integrations = new Set(entities.map((entity) => entity.platform).filter(Boolean));
        integrations.add("mobile_app");
        integrations.add("nfandroidtv");
        this._registry.integration = [...integrations].map((value) => ({ value, label: titleCase(value) }));
        for (const kind of KINDS) {
          this._registry[kind].sort((a, b) => a.label.localeCompare(b.label));
        }
      } finally {
        this._loading = false;
        this._loaded = true;
        if (this._mounted) {
          for (const kind of KINDS) this._drawOptions(kind);
          this._drawChosen();
        }
      }
    }

    _drawOptions(kind) {
      if (!this._mounted) return;
      const holder = this.$(kind + "-options");
      holder.replaceChildren();
      const query = this.$(kind + "-search").value.trim().toLocaleLowerCase();
      const options = this._registry[kind].filter((item) =>
        !query || item.value.toLocaleLowerCase().includes(query) || item.label.toLocaleLowerCase().includes(query)
      );
      for (const item of options.slice(0, 36)) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "option";
        button.dataset.kind = kind;
        button.dataset.value = item.value;
        button.textContent = clipped(item.label, 62);
        button.title = item.label + " (" + item.value + ")";
        button.setAttribute("aria-pressed", String(this._selected[kind].has(item.value)));
        holder.appendChild(button);
      }
      if (!options.length || options.length > 36) {
        const placeholder = document.createElement("span");
        placeholder.className = "option placeholder";
        placeholder.textContent = options.length > 36 ? this._t("Showing {shown} of {total}. Search for more.", { shown: 36, total: options.length })
          : this._loading ? this._t("Discovering...") : this._t("No matches. Manual IDs are available below.");
        holder.appendChild(placeholder);
      }
    }

    _drawChosen() {
      if (!this._mounted) return;
      const target = this.$("chosen-targets");
      target.replaceChildren();
      for (const kind of KINDS) {
        for (const value of this._selected[kind]) {
          const info = this._registry[kind].find((item) => item.value === value);
          const button = document.createElement("button");
          button.type = "button";
          button.dataset.kind = kind;
          button.dataset.value = value;
          button.textContent = this._t(titleCase(kind)) + ": " + clipped(info?.label || value, 36);
          button.setAttribute("aria-label", this._t("Remove {kind} {value}", { kind: this._t(titleCase(kind)), value: info?.label || value }));
          target.appendChild(button);
        }
      }
      this._updateSummary();
    }

    _targets() {
      const recipients = {};
      if (this._targetMode !== "targeted") return recipients;
      for (const kind of KINDS) {
        const values = uniq([...this._selected[kind], ...csv(this.$("manual-" + kind).value)]);
        if (values.length) recipients[kind] = values;
      }
      return recipients;
    }

    _buildPayload() {
      const main = this.$("message").value.trim();
      const textTts = this.$("text-tts").value.trim();
      const textNotify = this.$("text-notify").value.trim();
      if (!main && !textTts && !textNotify) throw new Error(this._t("Enter an announcement or a spoken/written version."));
      const recipients = this._targets();
      if (this._targetMode === "targeted" && !Object.keys(recipients).length) {
        throw new Error(this._t("Choose a room or explicit recipient, or switch to Automatic routing."));
      }
      if (this._targetMode === "automatic" && this._channel !== "auto") {
        throw new Error(this._t("Selecting a delivery service requires a room or exact recipient. Use Automatic channel for automatic routing."));
      }
      const payload = { level: this._level, occupied_only: this.$("occupied-only").checked, ...recipients };
      if (this._targetMode === "targeted") payload.manual_targets = true;
      if (main) payload.text = main;
      if (textTts) payload.text_tts = textTts;
      if (textNotify) payload.text_notify = textNotify;
      const title = this.$("message-title").value.trim();
      if (title) payload.title = title;
      if (this._channel !== "auto") payload.service = [this._channel];
      if (this._config.show_ai !== false && this._ai !== "inherit") {
        payload.use_ai = this._ai !== "off";
        if (this._ai === "rewrite" || this._ai === "generate") payload.ai_mode = this._ai;
      }
      const agent = this.$("ai-agent").value.trim();
      if (this._config.show_ai !== false && this._ai !== "off" && agent) payload.ai_agent = agent;
      const action = this.$("click-action").value.trim();
      if (action) payload.click_action = action;
      return payload;
    }

    _updateSummary() {
      if (!this._mounted) return;
      const targets = this._targets();
      const count = Object.values(targets).reduce((sum, values) => sum + values.length, 0);
      const destination = this._targetMode === "automatic"
        ? this._t("Automatic recipients") : count ? this._t(count === 1 ? "{count} selected target" : "{count} selected targets", { count }) : this._t("Choose recipients");
      const labelForChannel = this._t(CHANNELS.find((channel) => channel[0] === this._channel)?.[1] || "Hub channels");
      this.$("summary").textContent = destination + " · " + (this._channel === "auto" ? this._t("Hub channels") : labelForChannel);
    }

    _updateQueue() {
      if (!this._mounted || this._config.show_queue === false) return;
      const state = this._hass?.states?.["sensor.announcement_hub_queue"];
      const count = state && /^\d+$/.test(String(state.state)) ? String(state.state) : "–";
      this.$("queue-number").textContent = count;
      this.$("queue-pill").title = count === "–" ? this._t("Queue sensor unavailable") : this._t("{count} waiting announcements", { count });
    }

    _clearNotice() {
      const notice = this.$("notice");
      notice.hidden = true;
      notice.textContent = "";
    }

    _notice(message, success) {
      const notice = this.$("notice");
      notice.className = "notice " + (success ? "success" : "error");
      notice.textContent = message;
      notice.hidden = false;
    }

    async _send() {
      if (this._sending) return;
      this._clearNotice();
      let payload;
      try { payload = this._buildPayload(); }
      catch (error) { this._notice(error.message || this._t("Invalid announcement."), false); return; }
      if (!this._hass?.callService) {
        this._notice(this._t("Home Assistant is not connected."), false);
        return;
      }
      this._sending = true;
      this.$("send").disabled = true;
      this.$("send-label").textContent = this._t("Submitting…");
      this.$("critical-confirm").hidden = true;
      this._confirming = false;
      try {
        // Home Assistant's sixth argument requests a service response.
        // Never auto-retry: the backend may already have queued a request.
        const reply = await this._hass.callService(
          "notify", "announcement_hub", payload, undefined, false, true
        );
        if (reply?.accepted === false) throw new Error(this._t("Announcement Hub rejected the request."));
        if (reply?.job_id) {
          const related = Array.isArray(reply.related_job_ids) && reply.related_job_ids.length
            ? " · " + this._t("{count} linked jobs", {count: reply.related_job_ids.length + 1}) : "";
          this._notice(this._t("Queued #{id}{related}. Delivery will follow Hub routing.", {id: reply.job_id.slice(0, 10), related}), true);
        } else {
          this._notice(this._t("Request submitted. Check Announcement Hub's queue for status."), true);
        }
        if (this._config.clear_after_send === true) {
          for (const id of ["message", "text-tts", "text-notify"]) this.$(id).value = "";
        }
      } catch (error) {
        this._notice(this._t("Could not submit: {error}. Check the queue before retrying.", {error: error?.message || this._t("Unknown error")}), false);
      } finally {
        this._sending = false;
        this.$("send").disabled = false;
        this.$("send-label").textContent = this._t("Send announcement");
      }
    }
  }

  const EDITOR_HTML = [
    "<style>",
    ":host{display:block;padding:12px;color:var(--primary-text-color)}",
    "label{display:flex;flex-direction:column;gap:5px;margin-bottom:14px;font-size:12px;font-weight:600}",
    "input,select{padding:10px;border:1px solid var(--divider-color);border-radius:9px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit;font-size:13px}",
    ".check{flex-direction:row;align-items:center;gap:9px}.check input{accent-color:var(--primary-color)}",
    "p{font-size:11px;color:var(--secondary-text-color);line-height:1.5}",
    "</style>",
    '<label>Card title<input id="editor-title" placeholder="Announcement Hub"></label>',
    '<label>Default importance<select id="editor-level">',
    '<option value="info">Info</option><option value="success">Success</option>',
    '<option value="warning">Warning</option><option value="error">Error</option>',
    '<option value="critical">Critical</option><option value="debug">Debug</option>',
    "</select></label>",
    '<label class="check"><input type="checkbox" id="editor-queue"> Show queue count</label>',
    '<label class="check"><input type="checkbox" id="editor-ai"> Show AI wording controls</label>',
    '<label class="check"><input type="checkbox" id="editor-clear"> Clear message after successful send</label>',
    "<p>Recipients and message text are chosen when using the card, not stored in its dashboard configuration.</p>",
  ].join("");

  class AnnouncementHubCardEditor extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.shadowRoot.innerHTML = EDITOR_HTML; // Package-owned static markup.
      this._config = AnnouncementHubCard.getStubConfig();
      this._localeCode = null;
      this._translations = {};
      this._originalNodes = new WeakMap();
      for (const id of ["title", "level", "queue", "ai", "clear"]) {
        this.$(id).addEventListener("change", () => this._changed());
      }
    }
    $(id) { return this.shadowRoot.getElementById("editor-" + id); }
    setConfig(config) { this._config = { ...AnnouncementHubCard.getStubConfig(), ...config }; this._sync(); }
    set hass(value) { this._hass = value; void this._applyLocale(); }
    async _applyLocale() {
      const language = getLanguage(this._hass);
      if (this._localeCode === language) return;
      this._localeCode = language;
      const locales = await loadLocales();
      this._translations = locales[language] || {};
      if (typeof this.setAttribute === "function") this.setAttribute("dir", language === "ar" ? "rtl" : "ltr");
      localize(this.shadowRoot, this._translations, this._originalNodes);
    }
    _sync() {
      this.$("title").value = this._config.title || "";
      this.$("level").value = this._config.default_level || "info";
      this.$("queue").checked = this._config.show_queue !== false;
      this.$("ai").checked = this._config.show_ai !== false;
      this.$("clear").checked = this._config.clear_after_send === true;
    }
    _changed() {
      const next = {
        ...this._config,
        title: this.$("title").value,
        default_level: this.$("level").value,
        show_queue: this.$("queue").checked,
        show_ai: this.$("ai").checked,
        clear_after_send: this.$("clear").checked,
      };
      this._config = next;
      this.dispatchEvent(new CustomEvent("config-changed", {
        detail: { config: next }, bubbles: true, composed: true,
      }));
    }
  }

  if (!customElements.get(TYPE)) customElements.define(TYPE, AnnouncementHubCard);
  if (!customElements.get("announcement-hub-card-editor")) {
    customElements.define("announcement-hub-card-editor", AnnouncementHubCardEditor);
  }
  window.customCards = window.customCards || [];
  if (!window.customCards.some((entry) => entry.type === TYPE)) {
    window.customCards.push({
      type: TYPE,
      name: "Announcement Hub",
      description: "Send room-aware announcements with exact recipients, AI and TTS.",
      preview: true,
      documentationURL: DOC_URL,
    });
  }
})();