/* Announcement Hub Lovelace composer. No external JavaScript dependencies.
 * All dynamic provider/user content is inserted with textContent and DOM data
 * properties, never with HTML interpolation.
 */
(() => {
  "use strict";
  const TYPE = "announcement-hub-card";
  const ROOT = "/announcement_hub/";
  // Keep this aligned with the beta manifest. Version each companion asset so
  // an old JS module cannot silently mix with a newer HTML/CSS card.
  const FRONTEND_VERSION = "0.10.0b41";
  const assetUrl = (name) => ROOT + name + "?v=" + encodeURIComponent(FRONTEND_VERSION);
  const DOC_URL = "https://github.com/Chreece/HA-Announcement-Hub#dashboard-card";
  const LEVELS = [
    ["info", "Info"], ["success", "Success"], ["warning", "Warning"],
    ["error", "Error"], ["critical", "Critical"], ["debug", "Debug"],
  ];
  const LEVEL_ICONS = {
    info: "mdi:information-outline",
    success: "mdi:check-circle-outline",
    warning: "mdi:alert-outline",
    error: "mdi:alert-circle-outline",
    critical: "mdi:alert-octagon-outline",
    debug: "mdi:bug-outline",
  };
  const CHANNELS = [
    ["auto", "Automatic"], ["notification", "Written"], ["tts", "Speech"],
    ["all", "Both"], ["snapcast", "Snapcast"], ["companion_tts", "Phone speech"],
  ];
  const AI_OPTIONS = [
    ["inherit", "Hub default"], ["off", "Off"],
    ["rewrite", "Rewrite"], ["generate", "Generate"],
  ];
  const KINDS = ["area", "integration", "device", "entity"];
  const PERSON_TRANSLATION = [["inherit", "Person setting"], ["on", "Translate"], ["off", "Original language"]];
  const PERSON_SWITCH = [["inherit", "Person setting"], ["on", "Yes"], ["off", "No"]];
  const PERSON_DESTINATIONS = [["room", "Room"]];
  const TARGET_MODES = [
    ["automatic", "Automatic routing"], ["targeted", "Choose recipients"], ["person", "People"],
  ];
  // Icon-only selections: the full, localized choice is always displayed
  // beside each group's heading and in the icon's title / accessible label.
  const CHOICE_ICONS = {
    "target-mode": {
      automatic: "mdi:auto-fix", targeted: "mdi:target", person: "mdi:account-multiple-outline",
    },
    channels: {
      auto: "mdi:auto-fix", notification: "mdi:message-text-outline",
      tts: "mdi:volume-high", all: "mdi:layers-outline",
      snapcast: "mdi:speaker-multiple", companion_tts: "mdi:cellphone-sound",
    },
    "ai-choices": {
      inherit: "mdi:robot-outline", off: "mdi:robot-off-outline",
      rewrite: "mdi:pencil-outline", generate: "mdi:creation-outline",
    },
    "person-translation": {
      inherit: "mdi:account-cog-outline", on: "mdi:translate",
      off: "mdi:translate-off",
    },
    "person-greeting": {
      inherit: "mdi:cog-outline", on: "mdi:check-circle-outline", off: "mdi:close-circle-outline",
    },
    "pre-chime": {
      inherit: "mdi:cog-outline", on: "mdi:bell-outline", off: "mdi:bell-off-outline",
    },
    "person-destinations": {
      room: "mdi:home-outline",
    },
  };
  const getLanguage = (hass) => {
    const raw = String(hass?.locale?.language || hass?.language || "en").replace(/_/g, "-");
    if (/^zh-(tw|hk|hant)/i.test(raw)) return "zh-Hant";
    if (/^zh/i.test(raw)) return "zh-Hans";
    if (/^pt-br/i.test(raw)) return "pt-BR";
    return raw.split("-")[0].toLowerCase();
  };
  let localeCache = null;
  function loadLocales() {
    if (!localeCache) localeCache = fetch(assetUrl("announcement-hub-locales.json"), { credentials: "same-origin", cache: "no-store" })
      .then((r) => r.ok ? r.json() : {}).catch(() => ({}));
    return localeCache;
  }
  function translation(dict, key, params = {}) {
    const value = dict?.[key] || key;
    return value.replace(/\{([a-z]+)\}/g, (_, k) => String(params[k] ?? ""));
  }
  // Home Assistant's hass.callService resolves with { context, response }.
  // Older mocks/clients may yield the direct service payload instead.
  // Do not mistake the outer transport envelope for the response body.
  function servicePayload(result) {
    return result !== null && typeof result === "object" && "response" in result
      ? result.response : result;
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
          const response = await fetch(assetUrl(name), { credentials: "same-origin", cache: "no-store" });
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
      this._selected = Object.fromEntries([...KINDS, "person"].map((kind) => [kind, new Set()]));
      this._personDestinations = new Set(["room"]);
      this._personOwned = { integration: new Set(), device: new Set() };
      this._personOwnedOpen = { integration: false, device: false };
      this._personOwnedCatalog = {};
      this._personOwnedLoaded = false;
      this._personOwnedLoading = false;
      this._personOwnedLastFetch = 0;
      this._personTranslation = "inherit";
      this._personGreeting = "inherit";
      this._preChime = "inherit";
      this._registry = { area: [], integration: [], device: [], entity: [], person: [] };
      this._providerCatalog = { ai_agents: [], tts_engines: [] };
      this._providerSignatures = {};
      this._providerLoading = false;
      this._providerLastFetch = 0;
      this._level = "info";
      this._channel = "auto";
      this._ai = "inherit";
      this._targetMode = "automatic";
      this._mounted = false;
      this._mounting = false;
      this._loaded = false;
      this._loading = false;
      this._sending = false;
      this._stopping = false;
      this._stopConfirming = false;
      this._queueOpen = false;
      this._queueLoading = false;
      this._queueBusy = false;
      this._queueJobs = [];
      this._queueActive = [];
      this._queueRemoveId = null;
      this._queueError = "";
      this._queueStatus = "";
      this._queueObservedCount = null;
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
        this._providerSignatures = {};
        this._sync();
        for (const kind of [...KINDS, "person"]) this._drawOptions(kind);
        if (this._queueOpen) this._renderQueue();
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
        this._refreshPeople();
        if (this._targetMode === "person") void this._refreshPersonOwned();
        this._renderProviderSelectors();
        if (!this._loaded && !this._loading) void this._loadRegistry();
      }
    }
    connectedCallback() { void this._mount(); }
    getCardSize() { return 4; }
    getLayoutOptions() {
      return { grid_columns: 6, grid_rows: 5, grid_min_columns: 3, grid_min_rows: 3 };
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
        if (this._hass) {
          void this._refreshProviders();
          if (this._targetMode === "person") void this._refreshPersonOwned();
          await this._loadRegistry();
        }
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
      pick("person-translation", "_personTranslation");
      pick("person-greeting", "_personGreeting");
      pick("pre-chime", "_preChime");
      this.$("target-mode").addEventListener("click", (event) => {
        const mode = event.target.closest("button[data-mode]")?.dataset.mode;
        if (!mode) return;
        this._targetMode = mode;
        if (mode === "person" && this._selected.person.size) {
          // Show both sets of owned choices immediately. Clicking an already
          // visible option must be enough to select it (no focus-first tap).
          this._personOwnedOpen = { integration: true, device: true };
        }
        this._confirming = false;
        this.$("critical-confirm").hidden = true;
        this._sync();
        if (mode === "person") void this._refreshPersonOwned(true);
      });
      for (const container of ["targets", "person-targets"]) this.$(container).addEventListener("click", (event) => {
        const button = event.target.closest("button[data-kind][data-value]");
        if (!button) return;
        this._toggleTargetSelection(button.dataset.kind, button.dataset.value);
      });
      for (const kind of KINDS) {
        this.$(kind + "-search").addEventListener("input", () => this._drawOptions(kind));
        this.$("manual-" + kind).addEventListener("input", () => this._updateSummary());
      }
      this.$("person-search").addEventListener("input", () => this._drawOptions("person"));
      // Each group is a searchable, in-card multi-select. Options stay open
      // while ticking several items and selected values remain removable.
      for (const kind of ["integration", "device"]) {
        const search = this.$("person-" + kind + "-search");
        search.addEventListener("focus", () => this._showPersonOwnedOptions(kind));
        search.addEventListener("input", () => this._showPersonOwnedOptions(kind));
        search.addEventListener("keydown", (event) => {
          if (event.key === "Escape") {
            this._personOwnedOpen[kind] = false;
            this._drawPersonOwnedTargets();
          }
        });
      }
      this.$("person-owned-targets").addEventListener("click", (event) => {
        const button = event.target.closest("button[data-person-kind][data-value]");
        if (!button) return;
        this._selectPersonOwned(button.dataset.personKind, button.dataset.value);
      });
      this.$("person-owned-targets").addEventListener("focusout", (event) => {
        // Replacing a checked option node can emit focusout with a null
        // relatedTarget. Do not close the menu while ticking several options.
        if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) {
          this._personOwnedOpen = { integration: false, device: false };
          this._drawPersonOwnedTargets();
        }
      });
      this.$("person-destinations").addEventListener("click", (event) => {
        if (event.target.closest("button[data-destination=room]")) {
          this._selectPersonRoom();
        }
      });
      this.$("message-title").addEventListener("input", () => this._updateAIHint());
      // Provider choices expand in the card's document flow, never as a native
      // browser menu that can escape Lovelace's narrow or mobile columns.
      for (const id of ["ai-agent", "tts-engine"]) {
        const picker = this.$(id + "-picker");
        this.$(id + "-options").addEventListener("click", (event) => {
          const button = event.target.closest("button[data-provider-value]");
          if (!button || button.disabled) return;
          this.$(id).value = button.dataset.providerValue;
          picker.open = false;
          this._providerSignatures[id] = "";
          this._renderProviderSelectors();
        });
        picker.addEventListener("toggle", () => {
          if (!picker.open) return;
          const peer = id === "ai-agent" ? "tts-engine" : "ai-agent";
          this.$(peer + "-picker").open = false;
        });
      }
      this.$("advanced").addEventListener("toggle", () => {
        if (this.$("advanced").open) void this._refreshProviders(true);
      });
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
      this.$("stop-clear").addEventListener("click", () => {
        if (this._stopping) return;
        if (this._sending) {
          this._notice(this._t("Wait for the current submission before stopping."), false);
          return;
        }
        this._stopConfirming = true;
        this.$("stop-clear-confirm").hidden = false;
        this.$("stop-clear").setAttribute("aria-expanded", "true");
        this.$("confirm-stop-clear").focus();
      });
      this.$("confirm-stop-clear").addEventListener("click", () => void this._stopAndClear());
      this.$("cancel-stop-clear").addEventListener("click", () => this._closeStopConfirmation());
      this.$("queue-pill").addEventListener("click", () => this._toggleQueue());
      this.$("queue-close").addEventListener("click", () => this._toggleQueue(false));
      this.$("queue-refresh").addEventListener("click", () => void this._fetchQueue());
      this.$("queue-list").addEventListener("click", (event) => {
        const button = event.target.closest("button[data-queue-action]");
        if (button) void this._queueAction(button.dataset.queueAction, button.dataset.queueId);
      });
      this.$("occupied-only").addEventListener("change", () => this._updateSummary());
    }

    _renderButtons(id, choices, selected, dataKey = "value") {
      const target = this.$(id);
      const chosen = choices.find(([value]) => value === selected);
      const selectedLabel = this._t(chosen?.[1] || choices[0]?.[1] || "");
      this.$(id + "-selected").textContent = selectedLabel;
      if (id === "channels") this.$("delivery-section-selected").textContent = selectedLabel;
      target.replaceChildren();
      for (const [value, name] of choices) {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset[dataKey] = value;
        button.title = this._t(name);
        button.setAttribute("aria-label", this._t(name));
        button.setAttribute("aria-pressed", String(value === selected));
        const symbol = document.createElement("ha-icon");
        symbol.setAttribute("icon", CHOICE_ICONS[id]?.[value] || "mdi:circle-outline");
        button.appendChild(symbol);
        target.appendChild(button);
      }
    }

    _renderPriority() {
      const selected = LEVELS.find(([value]) => value === this._level);
      this.$("priority-selected").textContent = this._t(selected?.[1] || "Info");
      const target = this.$("levels");
      target.replaceChildren();
      for (const [level, label] of LEVELS) {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.value = level;
        button.title = this._t(label);
        button.setAttribute("aria-label", this._t(label));
        button.setAttribute("aria-pressed", String(level === this._level));
        const symbol = document.createElement("ha-icon");
        symbol.setAttribute("icon", LEVEL_ICONS[level]);
        button.appendChild(symbol);
        target.appendChild(button);
      }
    }

    _sync() {
      if (!this._mounted) return;
      this.$("card-heading").textContent = this._config.title || this._t("Announcement Hub");
      this.$("queue-pill").hidden = this._config.show_queue === false;
      if (this._config.show_queue === false && this._queueOpen) this._toggleQueue(false);
      this.$("ai-block").hidden = this._config.show_ai === false;
      this._renderPriority();
      this._renderButtons("target-mode", TARGET_MODES, this._targetMode, "mode");
      this._renderButtons("channels", CHANNELS, this._channel);
      this._renderButtons("ai-choices", AI_OPTIONS, this._ai);
      this._renderButtons("person-translation", PERSON_TRANSLATION, this._personTranslation);
      this._renderButtons("person-greeting", PERSON_SWITCH, this._personGreeting);
      this._renderButtons("pre-chime", PERSON_SWITCH, this._preChime);
      this.$("targets").hidden = this._targetMode !== "targeted";
      this.$("person-targets").hidden = this._targetMode !== "person";
      this.$("routing-explanation").textContent = this._targetMode === "automatic"
        ? this._t("Announcement Hub chooses configured recipients using occupancy and fallback rules.")
        : this._targetMode === "person"
          ? this._t("People") + " → " + [
              this._t("Room"), this._t("Integrations"), this._t("Devices"),
            ].join(" · ")
          : this._t("Select recipients bypasses the default output lists: only chosen rooms and exact integrations/devices/entities are eligible.");
      this._updateAIHint();
      this._drawChosen();
      this._drawPersonDestinations();
      this._drawPersonOwnedTargets();
      this._renderProviderSelectors();
      this._updateQueue();
    }

    _renderProviderSelectors() {
      if (!this._mounted) return;
      const stateChoices = (domain) => Object.entries(this._hass?.states || {})
        .filter(([id]) => id.startsWith(domain + "."))
        .map(([id, state]) => ({
          value: id,
          label: domain === "tts"
            ? "TTS – " + String(state?.attributes?.friendly_name || id.split(".")[1])
            : String(state?.attributes?.friendly_name || id) + " · " + id,
        }));
      const groups = [
        ["ai-agent", "ai_agents", [
          { value: "default", label: this._t("Home Assistant preferred agent") },
          ...stateChoices("conversation"), ...stateChoices("ai_task"),
        ]],
        ["tts-engine", "tts_engines", stateChoices("tts")],
      ];
      for (const [id, catalogKey, discovered] of groups) {
        const select = this.$(id);
        if (!select) continue;
        const selected = String(select.value || "");
        const choices = new Map();
        // Authenticated backend catalogue is authoritative for integration
        // names. HA states provide a fallback during backend upgrades.
        for (const candidate of [...(this._providerCatalog[catalogKey] || []), ...discovered]) {
          const value = String(candidate?.value || "");
          if (!value || choices.has(value)) continue;
          if (id === "tts-engine" && !value.startsWith("tts.")) continue;
          choices.set(value, String(candidate.label || value));
        }
        const options = [
          { value: "", label: this._t("Hub default"), disabled: false },
          ...[...choices.entries()].sort((a, b) => (
            a[0] === "default" ? -1 : b[0] === "default" ? 1 :
              a[1].localeCompare(b[1])
          )).map(([value, label]) => ({ value, label, disabled: false })),
        ];
        if (selected && !choices.has(selected)) {
          options.push({
            value: selected,
            label: this._t("Unavailable provider: {id}", { id: selected }),
            disabled: false,
          });
        }
        if (options.length === 1) {
          options.push({
            value: "__no_provider__", label: this._t("No providers available"),
            disabled: true,
          });
        }
        const signature = JSON.stringify(options) + "|" + selected + "|" + this._localeCode;
        if (this._providerSignatures[id] === signature) continue;
        this._providerSignatures[id] = signature;

        // Retain a non-visible select as a stable value store for the sender
        // and existing dashboards. The visible picker is owned by the card.
        select.replaceChildren();
        const holder = this.$(id + "-options");
        holder.replaceChildren();
        for (const choice of options) {
          const nativeOption = document.createElement("option");
          nativeOption.value = choice.value;
          nativeOption.textContent = choice.label;
          nativeOption.disabled = choice.disabled;
          select.appendChild(nativeOption);

          const button = document.createElement("button");
          button.type = "button";
          button.className = "provider-option";
          button.dataset.providerValue = choice.value;
          button.textContent = choice.label;
          button.title = choice.label;
          button.disabled = choice.disabled;
          button.setAttribute("aria-pressed", String(choice.value === selected));
          holder.appendChild(button);
        }
        select.value = selected;
        this.$(id + "-selected").textContent =
          options.find((choice) => choice.value === selected)?.label || this._t("Hub default");
      }
    }

    async _refreshProviders(force = false) {
      if (!this._mounted || !this._hass?.callService || this._providerLoading) return;
      const now = Date.now();
      if (!force && now - this._providerLastFetch < 120000) return;
      this._providerLoading = true;
      this._providerLastFetch = now;
      try {
        // Service returns both entity-backed providers and Conversation
        // agents that Home Assistant has registered without an entity.
        const response = servicePayload(await this._hass.callService(
          "announcement_hub", "list_providers", {}, undefined, false, true
        ));
        if (!Array.isArray(response?.ai_agents) || !Array.isArray(response?.tts_engines)) {
          throw new Error("Provider inventory unavailable");
        }
        this._providerCatalog = response;
      } catch (error) {
        // On an older integration version, continue with the local HA entity
        // inventory; never erase a previously selected override or message.
        this._providerLastFetch = 0;
      } finally {
        this._providerLoading = false;
        this._renderProviderSelectors();
      }
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
        this._refreshPeople();
        for (const kind of KINDS) {
          this._registry[kind].sort((a, b) => a.label.localeCompare(b.label));
        }
      } finally {
        this._loading = false;
        this._loaded = true;
        if (this._mounted) {
          for (const kind of [...KINDS, "person"]) this._drawOptions(kind);
          this._drawChosen();
        }
      }
    }

    _toggleTargetSelection(kind, value) {
      if (!this._selected[kind]) return;
      // A single click/tap handles the entire transition; there is no
      // separate "activate" step before selecting an actual person.
      if (this._selected[kind].has(value)) this._selected[kind].delete(value);
      else this._selected[kind].add(value);
      if (kind === "person") {
        const show = this._selected.person.size > 0;
        this._personOwnedOpen = { integration: show, device: show };
      }
      this._drawOptions(kind);
      this._drawChosen();
    }

    _refreshPeople() {
      const all = Object.entries(this._hass?.states || {});
      const persons = all
        .filter(([key]) => key.startsWith("person."))
        .map(([value, state]) => ({
          value, label: state.attributes?.friendly_name || value,
        }))
        .sort((a, b) => a.label.localeCompare(b.label));
      // Home Assistant reassigns hass on every state update. Replacing all
      // person buttons on every refresh can detach a pressed button between
      // pointerdown and click, silently eating the first tap.
      const previous = this._registry.person;
      if (previous.length === persons.length &&
          persons.every((item, i) =>
            item.value === previous[i].value && item.label === previous[i].label
          )) return;
      this._registry.person = persons;
      if (this._mounted) {
        this._drawOptions("person");
        this._drawChosen();
      }
    }

    _showPersonOwnedOptions(kind) {
      if (this._personOwnedOpen[kind]) return;
      // Focusing search never closes the other group's visible choices.
      // List entries remain directly clickable even without using search.
      this._personOwnedOpen[kind] = true;
      this._drawPersonOwnedTargets();
    }

    _selectPersonRoom() {
      // Explicit personal device/integration targets and Room are exclusive.
      this._personOwned.integration.clear();
      this._personOwned.device.clear();
      this._personDestinations.clear();
      this._personDestinations.add("room");
      this._drawPersonOwnedTargets();
    }

    _selectPersonOwned(kind, value) {
      const selected = this._personOwned[kind];
      if (!selected || !this._personOwnedLoaded || !this._selected.person.size) return;
      if (!this._personOwnedOptions(kind).some((item) => item.value === value)) return;
      if (selected.has(value)) selected.delete(value);
      else selected.add(value);
      if (this._personOwned.integration.size || this._personOwned.device.size) {
        // Never send a room leg together with person-owned exact recipients.
        this._personDestinations.delete("room");
      } else {
        // Emptying the multi-select restores the safe, explicit Room default.
        this._personDestinations.add("room");
      }
      this._drawPersonOwnedTargets();
    }

    _availablePersonDestinations() {
      // Personal integrations/devices are selected by exact owned IDs below.
      return ["room"];
    }

    _drawPersonDestinations() {
      if (!this._mounted) return;
      const holder = this.$("person-destinations");
      holder.replaceChildren();
      const chosen = PERSON_DESTINATIONS.filter(([value]) => this._personDestinations.has(value));
      this.$("person-destinations-selected").textContent =
        chosen.map(([, name]) => this._t(name)).join(" · ") || "—";
      for (const [value, name] of PERSON_DESTINATIONS) {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.destination = value;
        button.title = this._t(name);
        button.setAttribute("aria-label", this._t(name));
        button.setAttribute("aria-pressed", String(this._personDestinations.has(value)));
        const symbol = document.createElement("ha-icon");
        symbol.setAttribute("icon", CHOICE_ICONS["person-destinations"][value]);
        button.appendChild(symbol);
        holder.appendChild(button);
      }
    }

    async _refreshPersonOwned(force = false) {
      if (!this._mounted || !this._hass?.callService || this._personOwnedLoading) return;
      const now = Date.now();
      if (!force && now - this._personOwnedLastFetch < 120000) return;
      this._personOwnedLoading = true;
      this._personOwnedLastFetch = now;
      try {
        const response = servicePayload(await this._hass.callService(
          "announcement_hub", "list_person_targets", {}, undefined, false, true
        ));
        if (!response?.people || typeof response.people !== "object" || Array.isArray(response.people)) {
          throw new Error("Person target inventory unavailable");
        }
        this._personOwnedCatalog = response.people;
        this._personOwnedLoaded = true;
      } catch (error) {
        // An older Hub version must not turn person targeting into an HA-wide
        // integration/device broadcast. No owned choices are shown on failure.
        this._personOwnedCatalog = {};
        this._personOwnedLoaded = false;
        // A missing service on an older backend must not retry on every
        // Home Assistant state refresh; retry when the person tab is reopened.
        this._personOwnedLastFetch = now;
      } finally {
        this._personOwnedLoading = false;
        this._drawPersonOwnedTargets();
      }
    }

    _personOwnedOptions(kind) {
      const group = kind === "integration" ? "integrations" : "devices";
      const combined = new Map();
      for (const person of this._selected.person) {
        const options = this._personOwnedCatalog[person]?.[group] || [];
        const personName = this._registry.person.find((item) => item.value === person)?.label || person;
        for (const option of options) {
          const value = String(option?.value || "");
          if (!value) continue;
          if (!combined.has(value)) combined.set(value, {
            value, name: String(option.label || value), owners: new Set(),
          });
          combined.get(value).owners.add(personName);
        }
      }
      return [...combined.values()].map((item) => ({
        value: item.value,
        label: item.name + " · " + [...item.owners].join(", "),
      })).sort((a, b) => a.label.localeCompare(b.label));
    }

    _drawPersonOwnedTargets() {
      if (!this._mounted) return;
      const status = this.$("person-owned-status");
      const hasPerson = !!this._selected.person.size;
      const hasAssignedOutputs = ["integration", "device"].some(
        (kind) => this._personOwnedOptions(kind).length
      );
      status.textContent = !hasPerson
        ? this._t("Choose at least one person.")
        : this._personOwnedLoading
          ? this._t("Discovering...")
          : !this._personOwnedLoaded
            ? this._t("Person device list unavailable. Check Announcement Hub.")
            : !hasAssignedOutputs
              ? this._t("No assigned outputs for this person. Configure them in Announcement Hub.")
              : "";
      status.hidden = !status.textContent;
      let removedStale = false;
      for (const kind of ["integration", "device"]) {
        const holder = this.$("person-" + kind + "-options");
        const chosen = this.$("person-" + kind + "-chosen");
        const search = this.$("person-" + kind + "-search");
        const counter = this.$("person-" + kind + "-count");
        holder.replaceChildren();
        chosen.replaceChildren();
        const options = this._personOwnedOptions(kind);
        const permitted = new Set(options.map((item) => item.value));
        if (this._personOwnedLoaded) {
          for (const value of this._personOwned[kind]) {
            if (!permitted.has(value)) {
              this._personOwned[kind].delete(value);
              removedStale = true;
            }
          }
        }
        const query = search.value.trim().toLocaleLowerCase();
        const filtered = options.filter((item) =>
          !query || item.value.toLocaleLowerCase().includes(query) ||
            item.label.toLocaleLowerCase().includes(query)
        );
        for (const item of filtered.slice(0, 36)) {
          const button = document.createElement("button");
          const active = this._personOwned[kind].has(item.value);
          button.type = "button";
          button.className = "person-multi-option";
          button.dataset.personKind = kind;
          button.dataset.value = item.value;
          button.title = item.label;
          button.setAttribute("role", "option");
          button.setAttribute("aria-selected", String(active));
          button.setAttribute("aria-pressed", String(active));
          const icon = document.createElement("ha-icon");
          icon.setAttribute("icon", active ? "mdi:checkbox-marked" : "mdi:checkbox-blank-outline");
          const name = document.createElement("span");
          name.textContent = item.label;
          button.appendChild(icon);
          button.appendChild(name);
          holder.appendChild(button);
        }
        if (filtered.length > 36) {
          const notice = document.createElement("span");
          notice.className = "person-multi-empty";
          notice.textContent = this._t("Showing {shown} of {total}. Search for more.", {
            shown: 36, total: filtered.length,
          });
          holder.appendChild(notice);
        } else if (!filtered.length) {
          const notice = document.createElement("span");
          notice.className = "person-multi-empty";
          notice.textContent = !this._selected.person.size
            ? this._t("Choose at least one person.")
            : this._personOwnedLoading
              ? this._t("Discovering...")
              : !this._personOwnedLoaded
                ? this._t("Person device list unavailable. Check Announcement Hub.")
                : !options.length
                  ? this._t("No assigned outputs for this person. Configure them in Announcement Hub.")
                  : this._t("No matching items.");
          holder.appendChild(notice);
        }
        // The dropdown is in the card's flow, not a viewport-sized native menu.
        holder.hidden = !this._personOwnedOpen[kind];
        search.setAttribute("aria-expanded", String(this._personOwnedOpen[kind]));
        counter.textContent = this._personOwned[kind].size
          ? "(" + this._personOwned[kind].size + ")" : "";
        for (const value of this._personOwned[kind]) {
          const button = document.createElement("button");
          const item = options.find((option) => option.value === value);
          button.type = "button";
          button.className = "person-multi-chip";
          button.dataset.personKind = kind;
          button.dataset.value = value;
          button.textContent = clipped(item?.label || value, 48) + " ×";
          button.title = item?.label || value;
          button.setAttribute("aria-label", this._t("Remove {kind} {value}", {
            kind: this._t(titleCase(kind)), value: item?.label || value,
          }));
          chosen.appendChild(button);
        }
      }
      if (this._personOwned.integration.size || this._personOwned.device.size) {
        this._personDestinations.delete("room");
      } else if (removedStale && !this._personDestinations.size) {
        this._personDestinations.add("room");
      }
      this._drawPersonDestinations();
      this._updateSummary();
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
      const people = this.$("person-chosen");
      people.replaceChildren();
      for (const value of this._selected.person) {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.kind = "person";
        button.dataset.value = value;
        button.textContent = this._registry.person.find((item) => item.value === value)?.label || value;
        people.appendChild(button);
      }
      this._drawPersonDestinations();
      this._drawPersonOwnedTargets();
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
      if (this._targetMode === "person" && !this._selected.person.size) {
        throw new Error(this._t("Choose at least one person."));
      }
      if (this._targetMode === "person" && !this._personDestinations.size &&
          !this._personOwned.integration.size && !this._personOwned.device.size) {
        throw new Error(this._t("Choose at least one person destination."));
      }
      if (this._targetMode === "targeted" && !Object.keys(recipients).length) {
        throw new Error(this._t("Choose a room or explicit recipient, or switch to Automatic routing."));
      }
      if (this._targetMode === "automatic" && this._channel !== "auto") {
        throw new Error(this._t("Selecting a delivery service requires a room or exact recipient. Use Automatic channel for automatic routing."));
      }
      const payload = { level: this._level, occupied_only: this.$("occupied-only").checked, ...recipients };
      if (this._targetMode === "targeted") payload.manual_targets = true;
      if (this._targetMode === "person") {
        payload.target_person = [...this._selected.person];
        // Fail safe even if stale frontend state still contains "room".
        const exactPersonTargets = this._personOwned.integration.size || this._personOwned.device.size;
        payload.person_destination = exactPersonTargets ? [] : [...this._personDestinations];
        if (this._personOwned.integration.size) payload.person_integration = [...this._personOwned.integration];
        if (this._personOwned.device.size) payload.person_device = [...this._personOwned.device];
        if (this._personTranslation !== "inherit") payload.person_translate = this._personTranslation === "on";
        if (this._personGreeting !== "inherit") payload.person_greeting = this._personGreeting === "on";
      }
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
      if (this._preChime !== "inherit") payload.pre_announce_sound = this._preChime === "on";
      const engine = this.$("tts-engine").value.trim();
      if (engine) payload.tts_engine = engine;
      const agent = this.$("ai-agent").value.trim();
      if (this._config.show_ai !== false && this._ai !== "off" && agent) payload.ai_agent = agent;
      const action = this.$("click-action").value.trim();
      if (action) payload.click_action = action;
      return payload;
    }

    _updateSummary() {
      if (!this._mounted) return;
      const targets = this._targets();
      const count = this._targetMode === "person" ? this._selected.person.size
        : Object.values(targets).reduce((sum, values) => sum + values.length, 0);
      const destination = this._targetMode === "automatic"
        ? this._t("Automatic recipients") : this._targetMode === "person"
          ? this._t("{count} selected people", { count }) : count ? this._t(count === 1 ? "{count} selected target" : "{count} selected targets", { count }) : this._t("Choose recipients");
      const labelForChannel = this._t(CHANNELS.find((channel) => channel[0] === this._channel)?.[1] || "Hub channels");
      this.$("summary").textContent = destination + " · " + (this._channel === "auto" ? this._t("Hub channels") : labelForChannel);
    }

    _toggleQueue(force) {
      if (!this._mounted) return;
      this._queueOpen = typeof force === "boolean" ? force : !this._queueOpen;
      this.$("queue-panel").hidden = !this._queueOpen;
      this.$("queue-pill").setAttribute("aria-expanded", String(this._queueOpen));
      if (this._queueOpen) {
        void this._fetchQueue();
      } else {
        // Do not retain private message text in the hidden DOM or card state.
        this._queueJobs = [];
        this._queueActive = [];
        this._queueRemoveId = null;
        this.$("queue-list").replaceChildren();
      }
    }

    async _fetchQueue() {
      if (!this._queueOpen || this._queueLoading) return;
      if (!this._hass?.callService) {
        this._queueError = this._t("Home Assistant is not connected.");
        this._renderQueue();
        return;
      }
      this._queueLoading = true;
      this._queueError = "";
      this._renderQueue();
      try {
        // Full message bodies are returned ONLY to this authenticated client.
        const reply = servicePayload(await this._hass.callService(
          "announcement_hub", "list_queue", {}, undefined, false, true
        ));
        if (!Array.isArray(reply?.jobs) || !Array.isArray(reply?.active)) {
          throw new Error(this._t("Invalid queue response."));
        }
        if (!this._queueOpen) return;
        this._queueJobs = reply.jobs;
        this._queueActive = reply.active;
        this._queueStatus = "";
        if (this._queueRemoveId && ![...this._queueJobs, ...this._queueActive].some(
          (job) => job.job_id === this._queueRemoveId
        )) this._queueRemoveId = null;
        this.$("queue-total").textContent = this._t("{count} waiting · {active} active", {
          count: this._queueJobs.length, active: this._queueActive.length,
        });
      } catch (error) {
        this._queueError = this._t("Could not load queue: {error}", {
          error: error?.message || this._t("Unknown error"),
        });
      } finally {
        this._queueLoading = false;
        if (this._queueOpen) this._renderQueue();
      }
    }

    _renderQueue() {
      if (!this._mounted || !this._queueOpen) return;
      const holder = this.$("queue-list");
      const feedback = this.$("queue-feedback");
      feedback.textContent = this._queueError || this._queueStatus || (
        this._queueLoading ? this._t("Loading queue…") : ""
      );
      feedback.hidden = !feedback.textContent;
      this.$("queue-refresh").disabled = this._queueLoading || this._queueBusy;
      holder.replaceChildren();

      const jobs = [...this._queueActive, ...this._queueJobs];
      if (!jobs.length) {
        const empty = document.createElement("div");
        empty.className = "queue-empty";
        empty.textContent = this._queueLoading ? this._t("Loading queue…")
          : this._queueError ? this._t("Queue unavailable.")
          : this._t("No announcements waiting.");
        holder.appendChild(empty);
        return;
      }

      const actionButton = (name, icon, label, id, disabled = false) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.queueAction = name;
        button.dataset.queueId = id;
        button.setAttribute("aria-label", this._t(label));
        button.title = this._t(label);
        button.disabled = this._queueBusy || disabled;
        button.className = name;
        if (icon) {
          const symbol = document.createElement("ha-icon");
          symbol.setAttribute("icon", icon);
          button.appendChild(symbol);
        }
        if (!icon) button.textContent = this._t(label);
        return button;
      };

      for (const item of jobs) {
        const active = Boolean(item.active);
        const index = active ? -1 : this._queueJobs.findIndex((job) => job.job_id === item.job_id);
        const row = document.createElement("article");
        row.className = "queue-item" + (active ? " active" : "");
        row.setAttribute("role", "listitem");
        const heading = document.createElement("div");
        heading.className = "queue-item-head";
        const icon = document.createElement("ha-icon");
        icon.setAttribute("icon", LEVEL_ICONS[item.level] || LEVEL_ICONS.info);
        const title = document.createElement("strong");
        title.className = "queue-item-title";
        title.textContent = item.title || this._t("Untitled announcement");
        const status = document.createElement("span");
        status.className = "queue-item-meta";
        status.textContent = active ? this._t("Active") :
          this._t("#{position} · Waiting", { position: index + 1 });
        heading.append(icon, title, status);
        row.appendChild(heading);

        const body = document.createElement("div");
        body.className = "queue-item-body";
        const generatePrompt = item.ai_pending && item.ai_mode === "generate";
        const spoken = String(item.text_tts || "");
        const visual = String(item.text_notify || "");
        const contents = [];
        if (visual) contents.push([generatePrompt ? "AI prompt" : "Written", visual]);
        if (spoken && spoken !== visual) contents.push([generatePrompt ? "AI prompt" : "Speech", spoken]);
        if (!contents.length) contents.push(["Message", this._t("No message text available.")]);
        for (const [channel, content] of contents) {
          const text = document.createElement("div");
          const label = document.createElement("small");
          label.textContent = this._t(channel);
          text.appendChild(label);
          const value = document.createElement("span");
          value.textContent = content;
          text.appendChild(value);
          body.appendChild(text);
        }
        row.appendChild(body);

        const controls = document.createElement("div");
        controls.className = "queue-actions";
        if (!active) {
          controls.appendChild(actionButton("up", "mdi:chevron-up", "Move up", item.job_id, index <= 0));
          controls.appendChild(actionButton("down", "mdi:chevron-down", "Move down", item.job_id, index >= this._queueJobs.length - 1));
        }
        if (this._queueRemoveId === item.job_id) {
          controls.appendChild(actionButton("confirm-remove", "", active ? "Confirm stop" : "Confirm remove", item.job_id));
          controls.appendChild(actionButton("keep", "", "Keep", item.job_id));
        } else {
          controls.appendChild(actionButton("remove", "mdi:trash-can-outline", active ? "Stop active announcement" : "Remove queued announcement", item.job_id));
        }
        row.appendChild(controls);
        holder.appendChild(row);
      }
    }

    async _queueAction(action, id) {
      if (!id || this._queueBusy || this._queueLoading || !this._hass?.callService) return;
      if (action === "keep") {
        this._queueRemoveId = null;
        this._renderQueue();
        return;
      }
      if (action === "remove") {
        this._queueRemoveId = id;
        this._renderQueue();
        return;
      }
      const index = this._queueJobs.findIndex((job) => job.job_id === id);
      if (action === "confirm-remove" && this._queueRemoveId !== id) return;
      if (!["up", "down", "confirm-remove"].includes(action)) return;
      if (action !== "confirm-remove" && index < 0) return;
      const neighbor = action === "up" ? this._queueJobs[index - 1]
        : action === "down" ? this._queueJobs[index + 1] : null;
      if (action !== "confirm-remove" && !neighbor) return;

      this._queueBusy = true;
      this._queueError = "";
      this._queueStatus = "";
      this._renderQueue();
      try {
        if (action === "confirm-remove") {
          const response = servicePayload(await this._hass.callService(
            "announcement_hub", "cancel", { job_id: id }, undefined, false, true
          ));
          if (!["cancelled", "cancelling"].includes(response?.status)) {
            throw new Error(this._t("Remove was not acknowledged."));
          }
          this._queueStatus = this._t("Announcement removal requested.");
        } else {
          const reply = servicePayload(await this._hass.callService(
            "announcement_hub", "reorder_queue", {
              job_id: id, direction: action, neighbor_job_id: neighbor.job_id,
            }, undefined, false, true
          ));
          if (reply?.moved !== true) {
            throw new Error(this._t("Queue was not moved. Refresh and retry."));
          }
          this._queueStatus = this._t("Queue order saved.");
        }
        this._queueRemoveId = null;
        await this._fetchQueue();
      } catch (error) {
        this._queueError = this._t("Could not change queue: {error}", {
          error: error?.message || this._t("Unknown error"),
        });
      } finally {
        this._queueBusy = false;
        this._renderQueue();
      }
    }

    _updateQueue() {
      if (!this._mounted || this._config.show_queue === false) return;
      const state = this._hass?.states?.["sensor.announcement_hub_queue"];
      const count = state && /^\d+$/.test(String(state.state)) ? String(state.state) : "–";
      this.$("queue-number").textContent = count;
      this.$("queue-pill").title = count === "–" ? this._t("Queue sensor unavailable") : this._t("{count} waiting announcements", { count });
      if (this._queueOpen && this._queueObservedCount !== count) {
        this._queueObservedCount = count;
        void this._fetchQueue();
      }
    }


    _closeStopConfirmation() {
      this._stopConfirming = false;
      this.$("stop-clear-confirm").hidden = true;
      this.$("stop-clear").setAttribute("aria-expanded", "false");
    }

    async _stopAndClear() {
      // No destructive action on the first tap. Only the confirmation button
      // invokes the authenticated integration service.
      if (!this._stopConfirming || this._stopping || this._sending) return;
      this._clearNotice();
      if (!this._hass?.callService) {
        this._notice(this._t("Home Assistant is not connected."), false);
        return;
      }
      this._stopping = true;
      this.$("stop-clear").disabled = true;
      this.$("confirm-stop-clear").disabled = true;
      this.$("send").disabled = true;
      try {
        // Do not use queue-only default: also request cancellation of
        // every active delivery and interruption of Hub-owned audio.
        const reply = servicePayload(await this._hass.callService(
          "announcement_hub", "clear_queue", { include_current: true }, undefined, false, true
        ));
        if (Number.isInteger(reply?.cleared) && reply.cleared >= 0) {
          this._notice(this._t("Cleared {count} queued jobs. Stop requested for active Hub outputs.", { count: reply.cleared }), true);
        } else {
          // The service may have run even if its response was lost.
          this._notice(this._t("Stop request sent. Check the queue before retrying."), true);
        }
        this._updateQueue();
        if (this._queueOpen) void this._fetchQueue();
      } catch (error) {
        // Never automatically repeat a destructive service call.
        this._notice(this._t("Could not stop or clear: {error}. Check the queue before retrying.", { error: error?.message || this._t("Unknown error") }), false);
      } finally {
        this._stopping = false;
        this.$("stop-clear").disabled = false;
        this.$("confirm-stop-clear").disabled = false;
        this.$("send").disabled = this._sending;
        this._closeStopConfirmation();
      }
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
      if (this._sending || this._stopping) return;
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
        const reply = servicePayload(await this._hass.callService(
          "notify", "announcement_hub", payload, undefined, false, true
        ));
        if (reply?.accepted === false) throw new Error(this._t("Announcement Hub rejected the request."));
        if (reply?.job_id) {
          const related = Array.isArray(reply.related_job_ids) && reply.related_job_ids.length
            ? " · " + this._t("{count} linked jobs", {count: reply.related_job_ids.length + 1}) : "";
          this._notice(this._t("Queued #{id}{related}. Delivery will follow Hub routing.", {id: reply.job_id.slice(0, 10), related}), true);
        } else {
          this._notice(this._t("Request submitted. Check Announcement Hub's queue for status."), true);
        }
        if (this._queueOpen) void this._fetchQueue();
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