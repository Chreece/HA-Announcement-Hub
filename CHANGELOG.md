# Changelog

## 0.10.0b4 - 2026-10-22

**Beta — Smart Announcements feature-parity additions (opt-in by default).**

- Add persisted **per-person and per-area enable/disable switches** and
  positive, fail-closed binary-sensor presence verification for person
  and room routes. Recheck live permissions during queue selection and
  again before device service calls; disabled or unverified rooms must
  never substitute unrelated receivers.
- Configure a different **AI provider (Conversation or AI Task), rewrite
  preference and TTS engine per person and for a shared-room group**.
  Explicit action overrides take priority, then person/group settings,
  then global defaults; explicit AI off remains authoritative. Preserve
  existing per-person language, voice and translation preferences.
- Support optional literal `{{ name }}` replacement and **opt-in personal
  and group greetings**. Default is no automatic prefix, avoiding
  unsolicited names in shared-room or sensitive messages.
- Add validated **Advanced AI style templates** for rewrite, translation,
  and the combined operation with only `{message}` and `{language}`
  placeholders. Existing non-action/tool restrictions, strict JSON,
  channel separation, factual validation and fallback remain enforced.
- Add optional **direct-room chimes and audio ducking**, both disabled
  by default. Chimes accept local audio files; ducking snapshots current
  media-player volume before adjusting and restores it if unchanged,
  with guarded recovery after interruption. Neither touches the shared
  Snapcast source or authorizes a new recipient.
- Expand the Lovelace People composer with greeting and audio/engine
  overrides, and add associated provider selectors, configuration menus
  and localization fields, including reviewed Greek and German help.
  Add tests for the presence, routing isolation, audio and AI contracts.
- This is an opt-in hardware-testing beta. Older native help descriptions
  in some locales remain on the localization issue tracker.


## 0.10.0b3 - 2026-10-22

**Beta — room-tracker verification and international localization**

- Verify compatibility with Bermuda room sensor states, ESPresense-style
  device tracker room/area attributes, and area_id-based room reports.
  Regression tests confirm that an unavailable configured tracker does
  not reuse stale room data or broadcast to unrelated rooms.
- Complete all People configuration field labels, help descriptions,
  destination assignments, translation preferences, validation messages,
  and person-target action descriptions across every shipped native
  language catalog, including Greek and German.
- Translate the newly added People dashboard mode, Room/Mobile/Watch/
  Tablet/Other instructions, translation choices, selection errors and
  manual-output help across all 19 localized dashboard languages.
- Expand reviewed French and Spanish translations of output levels, TTS
  configuration, media display profiles, queue settings, errors, and
  reconfiguration navigation (138 string occurrences per language plus
  the new People descriptions).
- Add automated native/catalog and card regression checks for complete
  People strings, locale parity and interpolation tokens, and document
  how to connect Bermuda/ESPresense entities to persons. Ordinary
  announcement routing, services, and stored configuration remain
  backward compatible.
- Older native configuration descriptions in several languages still
  use English fallback where they have not been reviewed.


## 0.10.0b2 - 2026-10-22

**Beta — person language translation and named personal destinations**

- Introduce assigned personal destinations **Room, Mobile, Watch, Tablet, Other**
  for person announcements. Assign each person's existing HA notify or
  media-player entities in **Configure → People**. The service and dashboard
  choose human-readable destination names, not physical entity IDs.
- Room targeting retains strict person-room tracking and group deduplication.
  Mobile, Watch, Tablet and Other reach only their specifically assigned
  outputs, including when a person is away or room tracking is unavailable.
  Missing/disabled or unassigned outputs cause validation errors rather
  than routing to another person's devices or broadcasting an integration.
- Add opt-in individual and group AI translation into the intended language
  with TTS voice/language options. Separate visual and spoken text remain
  isolated, numeric readings and meaning are safeguarded, and AI failure
  preserves the original announcement. An explicit use_ai: false disables AI.
- Add per-action person_destination and person_translate options, plus
  People mode and optional translation override in the Lovelace card.
  Expose only configured personal destination labels (not entity mappings)
  through the queue sensor for the card's recipient picker.
- Add regression tests, native service/config field and selector translations,
  updated dashboard translations and documentation. Leave automatic routing
  and existing exact device/integration actions unchanged.


## 0.10.0b1 - 2026-10-22

**Beta — person-aware and manual-recipient routing.**

- Add `target_person` announcements with per-person room tracking
  (Bermuda/ESPresense or other room sensors), optional individual language/
  voice settings and single group announcements for shared rooms.
  Separate targeted rooms retain independent FIFO delivery and fail closed
  for unknown locations or away persons unless expressly allowed.
- Extend the integration's People configuration and native translations;
  preserve existing devices, notify services, TTS engine and shared Snapcast
  configuration rather than create redundant phone/watch outputs.
- Make dashboard **Choose recipients** independent of integration default
  output selections: discover HA area/integration/device/entity endpoints at
  send time and freeze only the selected output paths. Automatic routing
  retains the configured defaults.
- Manual area targeting never escalates into generic mobile broadcasts;
  integration selectors intentionally include eligible devices in that
  integration; service/channel filtering and Snapcast isolation remain strict.
- Add tests for missing/away people, group fan-out, dashboard requests and
  manual-room discovery. This pre-release is intended for real-hardware beta
  verification before a stable release.


## 0.9.44 - 2026-10-21

- Recover online Conversation AI responses that contain exactly one usable
  JSON object inside a short explanation, or mark text-only action_done replies
  as safe when HA reports no device/action data.
- Accept an omitted null/unrequested channel and discard an unused AI title
  without permitting extra recipients, tools, unexpected action fields,
  missing requested text or changed numeric readings.
- If the final AI provider returns invalid JSON, an incomplete response or
  changed measurements, make **one bounded short-prompt retry** instead of
  immediately delivering the original. Prefer a configured backup AI to
  repeating the primary provider; preserve the original after unsafe retries.
- Expose a persisted, capped **recent_ai** summary of the latest 20 AI
  outcomes in the Hub queue sensor, including successes, failed validation,
  exact failure category, retry count and AI-disabled requests or overrides.
  This remains visible when a newer successful announcement replaces last.ai
  and excludes all source text, prompts and model output.
- Add regressions for prefaced/fenced JSON, ambiguous multiple objects,
  actual action-field rejection, optional null channels/titles, one safe
  retry, numeric integrity, backup precedence and diagnostic persistence.
- Keep room-specific FIFO delivery, provider isolation and AI Task native
  structured output unchanged.

## 0.9.43 - 2026-10-21

- Fix intermittent **AI-enabled announcements delivered unchanged** when a
  Home Assistant Conversation agent returns a valid text response marked
  `action_done` with empty `targets`, `success` and `failed` lists.
  Continue rejecting actual Home Assistant action executions.
- Use Home Assistant **AI Task native structured output** for announcement
  speech, visual text and optional three-word generated titles. Request only
  the channels the caller supplied, preserving channel and recipient safety.
- When an AI Task provider explicitly rejects structured output, retry once
  using the compatible JSON-in-text request. Generic provider failures do
  not trigger duplicate calls.
- Prevent overlapping AI preprocessing jobs for the **same selected provider**
  across different rooms. Independent AI providers and room delivery queues
  remain concurrent.
- Improve safe queue diagnostics to separate malformed JSON, unexpected
  response fields, missing output text, refused device-action responses and
  preserved-number validation failures from provider timeouts/errors.
- Add targeted regressions for valid actionless Conversation results, real
  structured AI Task responses, disabled-channel protection, schema fallback,
  provider serialization and AI failure classifications. Document diagnostics
  under `sensor.announcement_hub_queue` without exposing announcement text.

## 0.9.42 - 2026-10-21

- Complete every existing dashboard composer/card-editor locale string across
  all 20 supported frontend languages (English source and 19 translations).
  This includes room/explicit-device targeting help, TTS and AI choices,
  dynamic queue messages, validation/errors, critical confirmation and
  recipient selections, without altering entity IDs or service payloads.
- Finish native integration Greek and German selector translations, including
  Android TV placement, notification color, font size and severity labels.
- Add reviewed French and Spanish native integration descriptions for 24
  critical room routing, occupied-room, fallback-door, Snapcast/TTS and AI
  settings, mirrored across initial configuration and options.
- Correct the announcement action's AI provider description to explicitly
  support both Conversation agents and AI Task entities.
- Enforce card key coverage and interpolation parity in automated regressions.
  Retain reviewed text and remove rejected machine translation experiments
  that produced inaccurate fallback and room-targeting explanations.
- Other non-Greek/German native integration catalogs still contain English
  fallback descriptions. Their remaining review work is tracked in issue #50;
  a full schema is not claimed to equal a complete human translation.

## 0.9.41 - 2026-10-21

- Internationalize the **Announcement Hub dashboard composer and card editor**,
  including localized controls, placeholders, help, severity, AI modes,
  recipients, queue summaries, validation feedback and send results.
- Follow each user's Home Assistant frontend language, support region-specific
  Portuguese and Chinese variants, right-to-left Arabic and safe English
  fallback. Preserve all language-independent service, device and entity IDs.
- Include **20 interface locales**: English, Greek, German, French, Spanish,
  Italian, Portuguese (PT/BR), Dutch, Polish, Russian, Turkish, Ukrainian,
  Arabic, Chinese (Simplified/Traditional), Japanese, Korean, Swedish, Czech.
- Extend native integration translation catalogs from EN/EL/DE to every listed
  locale; translate core setup headings and descriptions, routing/service
  labels, AI provider, recipient fields and severity. Detailed help in newer
  locales falls back to English when not yet localized.
- Keep Greek and German integration translation coverage complete; add Greek
  and German dashboard card strings, include the locale file in the manual
  installer and test translations, placeholders and runtime locale changes.

## 0.9.40 - 2026-10-21

- Automatically register the bundled **Announcement Hub** composer card in
  Home Assistant's Lovelace card picker after the integration starts.
  No manual JavaScript resource installation is needed in storage mode.
- Safely load existing Lovelace resources before registering to prevent
  overwriting other dashboard cards on older Home Assistant versions.
- Avoid duplicate resources across restarts, preserve manually configured
  resources and update auto-managed module URLs with a version cache-buster.
- Leave YAML-managed Lovelace resources untouched and keep documented
  manual resource registration as a fallback.
- Add registration safety, idempotency, upgrade and YAML-mode regression
  tests; document the exact picker name and custom-card type.

## 0.9.39 - 2026-10-21

- **Queue liveness:** Refill bounded AI and TTS preparation slots when a
  pending job is cancelled. A cancelled cold-start task can no longer leave
  unrelated rooms waiting for new traffic to trigger the scheduler.
- **Cross-room fairness:** Pending or unavailable jobs reserve their own
  rooms, not idle physical notification targets. Explicit-device jobs with no
  room no longer share a fictitious global FIFO lane.
- **Snapcast isolation and recovery:** Restore a held shared-audio route while
  unrelated rooms continue working. Retain the original mute-state snapshot
  when restoring fails, retry with bounded backoff, refuse new shared
  playback on an uncertain route, and requeue undelivered announcements.
- Add executable regressions for cancelled producer slots, independent
  device delivery, shared-output fairness, retained Snapcast restoration
  state, fail-closed playback and concurrent room delivery. Preserve
  existing room FIFO, occupancy fallback and explicit-target restrictions.

## 0.9.38 - 2026-10-21

- Deliver announcements in **strict FIFO order per room**, including jobs awaiting
  AI preprocessing, output readiness, fallback stages or retry backoff.
- Dispatch independent rooms concurrently in up to four protected delivery
  lanes. Reserve shared physical notification/speaker endpoints and the
  common Snapcast audio source so unrelated rooms can proceed without
  unsafe overlapping playback or cross-room announcements.
- Limit active AI generation and TTS rendering to two jobs each; select room
  heads fairly to prevent burst loads from monopolizing a local model.
  Preserve durable jobs, ordering, targeted cancellation, restart recovery
  and combined-delivery deduplication.
- Support Home Assistant `ai_task.*` entities as primary, backup and
  per-announcement AI providers using `ai_task.generate_data`; retain JSON
  validation, fallback to original text and conversation-agent compatibility.
- Recover safely from errors restoring a shared Snapcast route, retaining
  announcements for later retry without leaking a delivery lane.
- Add executable concurrent FIFO, shared-output isolation, AI Task and
  burst-management regressions; refresh EN/DE/EL UI wording and documentation.

## 0.9.37 - 2026-10-20

- Fix an unsafe shared TTS path that could play on the central MPD player
  even with **zero authorized Snapcast clients**. Require physical recipients
  at planning, readiness, round dispatch and media-playback boundaries.
- Stop broadening legacy queued TTS jobs with an empty physical route to all
  currently configured Snapcast clients on Home Assistant restart.
- Re-validate the live client mute route immediately before and throughout
  shared playback, including the buffered audio tail. On an external unmute,
  stop shared playback, mute unintended listeners and allow the queue to
  recover without continuing the broadcast. Log the unexpected client IDs.
- Do not send the media-player `announce` option to the dedicated Snapcast
  shared MPD player. Provide a translated optional **Direct-speaker
  announcement mode** setting to disable provider-specific bells/chimes
  on standalone TTS media players; default preserves existing behavior.
- Document how a competing Home Assistant volume automation can overwrite
  Hub's route and how to keep existing room-specific scripts from expanding
  their requested rooms to every configured area.
- Add executable regressions for missing clients, unexpected unmuting,
  shared/direct announcement modes, persisted legacy routing and tail
  re-isolation.


## 0.9.36 - 2026-10-20

- Ship a fully functional, responsive Lovelace announcement-composer card,
  including a graphical card configuration editor and dashboard card-picker
  registration. All assets are served locally by Announcement Hub through
  Home Assistant's asynchronous HTTP static-path API.
- Provide shared message and optional independent TTS/visual variants,
  severity, optional notification title, service channel restrictions,
  AI inherit/off/rewrite/generate, conversation agent and click-action fields.
- Discover Home Assistant rooms, integration domains and exact devices and
  entities via registry WebSocket APIs, with manual recipient IDs if registry
  access is unavailable. Preserve room fallback and explicit-recipient union.
- Show queue count and service acceptance status, prevent simultaneous
  duplicate submissions, confirm Critical severity, and never claim
  device-side receipt from an accepted queue submission.
- Add a graphical card editor and English dashboard installation guide.
  Include front-end resource assets in manual installation validation and
  add automated frontend smoke/security tests.


## 0.9.35 - 2026-10-20

- Generate a descriptive title (up to three words) within the existing AI
  generation request when no explicit title is supplied by the action.
- Never overwrite caller-provided titles; default rewrite mode remains
  unchanged and makes no title request.
- Normalize model titles to plain text, remove decorations, enforce the
  three-word limit and retain the configured fallback title if generation
  fails or returns an unusable title. No extra model invocation is needed.
- The generation flag is saved with the original queued job so restart can
  retry without losing title generation; generated titles remain private in
  normal queue diagnostics until visual delivery.


## 0.9.34 - 2026-10-20

- Add a configurable channel-fallback policy under General settings:
  Visual → TTS, TTS → Visual or Both. Default Both preserves the existing
  behavior for previously configured integrations.
- Apply channel priority only when both spoken and written source texts
  AND both permitted output types exist. Never invent a missing channel,
  broaden explicit recipients or bypass severity and room/door restrictions.
- For room-aware announcements, attempt the alternate channel within the
  same room after provider failure before escalating to occupied, alternate
  or general outputs. The retry direction persists across restarts.
- In explicit-recipient delivery, run visual and speech sequentially when
  a directional mode is chosen; the second channel runs only if the first
  reports no successful output. Both retains existing parallel dispatch.
- Replace the misleading Notification/TTS start-order selector with
  localized, explanatory visual/TTS fallback choices.


## 0.9.33 - 2026-10-20

- Add per-announcement AI generation mode in addition to strict copyediting.
  It can turn fact-bearing instructions into finished natural TTS and written
  notification text inside the durable queue preprocessing stage.
- Respect the configured provider and backup, source language, hard selected
  delivery targets and independent TTS/written channel boundaries. AI never
  controls Home Assistant.
- Preserve the original unprocessed text as the final fallback when generation
  fails; add regression tests and document usage.


## 0.9.32 - 2026-10-19

- Separate recipients and channels in announcement actions: area, integration,
  device, and entity select the actual physical destinations, while service
  restricts to written notifications, TTS, Snapcast or Companion TTS.
- Preserve requested-room, occupied-room, open-door alternate room and
  General fallback only for area-based requests. Explicit recipients are
  never broadened into other integrations or devices.
- Compose area and exact-recipient requests as linked, separately tracked
  deliveries with shared successful-output receipts, preventing duplicates
  while preserving the requested room's original candidate set.
- Never infer all Snapcast/direct room players from a selected TTS engine.
- Preserve channel text boundaries: text_tts speaks only; text_notify
  displays only; shared text supplies both unless individually overridden.
  This remains true at Critical level and on provider failure.
- Display area instead of output in the action interface, preserving the
  old output key as a hidden compatibility alias for existing automations.
- Add registry-backed device selection, selectors in the service description,
  test coverage for service filtering and union targeting, and English docs.


## 0.9.31 - 2026-10-19

- Prioritize actual room delivery over the soft minimum TTS severity. At Info
  or Success, a ready visual notification suppresses speech in the requested
  room, but if no visual can run, a configured room TTS/Snapcast/opted-in
  Companion audio path can speak at any non-Never level.
- For occupied-room and door-gated alternate-room fallback, prefer audible
  delivery when available even below the usual TTS threshold, so the person
  can hear the announcement. A ready visual device remains usable if audio
  cannot run; otherwise wait within the configured room availability grace
  before moving to the next permitted tier.
- If a ready visual provider fails and no output succeeded, retry eligible
  spoken output in the SAME room before escalating to another room. Preserve
  TTS "Never" (except Critical), notification severity thresholds, explicit
  service allowlists, occupancy and door gates, and General-only scope.
- Persist the same-room audio retry flag, and add executable regressions for
  ready/unready room Snapcast, visual preference, occupied-area speech,
  door-open/closed alternate areas, provider failures and restrictions.


## 0.9.30 - 2026-10-19

- Make AI announcements durable before requesting AI: queue and persist the
  original notification, acknowledge the Hub action promptly, then rewrite
  asynchronously in a separate config-entry background task. This prevents
  cancelling an unqueued message when local model loading or provider errors
  delay the caller.
- A slow model never blocks newer ready announcements. The delivery worker
  waits only for the given job's AI result; on provider failure, deliver its
  preserved original text using the same configured room/severity rules.
- Restore interrupted AI preprocessing from the persisted original after
  Home Assistant restarts. Cancel preprocessing when a queued job is cleared,
  and wait for all background tasks on integration shutdown.
- Expose pending AI job IDs through queue diagnostics, and retain per-attempt
  results on completion without changing notification recipients.
- Add regression coverage for skipping AI-pending jobs and for the
  queue-before-AI service handoff.


## 0.9.29 - 2026-10-19

- Removed Announcement Hub's fixed 12-second AI request timeout, which
  prematurely discarded slow responses while local language models were
  loading. Await the actual result of each selected Home Assistant
  conversation agent, including cloud and third-party providers.
- Record an advisory warning if an AI call is still pending after 60 seconds,
  without cancelling it or submitting a duplicate request. Include AI
  processing time and per-attempt duration in response diagnostics.
- Keep the existing backup-agent/original-text fallback for actual provider
  failures (including provider-owned timeouts), invalid replies and unsafe
  outputs. Preserve cancellation propagation, channel integrity, queue
  ordering, severity and area-routing rules.
- Add regressions proving a slow but successful agent response is accepted,
  no backup is contacted, and native provider errors remain distinguishable
  from the removed Hub-side timeout.


## 0.9.28 - 2026-10-18

- Fixed Air Quality Advisor Info-level announcements targeting real HA rooms
  such as `Küche` being rejected when the room had no eligible visual output
  and TTS was below its configured severity threshold.
- Added staged, persistent room routing: explicit preferred rooms, remaining
  occupied rooms, the configured fallback room only when its door rule allows,
  and finally eligible General/non-room outputs.
- Each stage with configured but unavailable targets waits the configured
  output-availability grace period before escalation; empty/ineligible stages
  advance immediately. Minimum TTS and notification levels remain enforced.
- Stopped silently completing/discarding queued announcements after the
  availability timeout. Jobs stay persisted and retry permitted routes until
  some output can receive them, without blocking newer runnable jobs.
- Recover from failed staged provider deliveries by requeueing instead of
  discarding undelivered messages; throttle retries of failing General
  providers to prevent busy loops.
- Preserved explicit service/device allowlists across all routing stages,
  occupied_only behavior, room bindings, and no-broadcast safety. No changes
  to Air Quality Advisor or its message/routing inputs.
- Added routing stage/priority diagnostics to action responses and persistent
  queue status, with executable regressions for Info-level Küche,
  unavailable/unknown room devices, timeout, occupied-room alternatives,
  door-open/closed fallback, General delivery, and indefinite pending jobs.

## 0.9.27 - 2026-10-17

- Fixed the Announcement Hub banner failing to display in the HACS repository
  information page. The README now references the existing repository SVG
  through an absolute raw GitHub URL instead of a relative asset path.
- Added tests to ensure README images use absolute HTTPS links and verify
  that repository-owned image assets exist and contain valid SVG markup.
- No announcement routing, AI, playback, or integration configuration changes.

## 0.9.26 - 2026-10-17

- Added primary `text` field to the `notify.announcement_hub` action and
  legacy `announcement_hub.send` alias, shown as required for new actions.
  Optional `text_tts` and `text_notify` fields independently override
  the common text for the spoken and visual channels.
- Channel text is resolved before level/room/strict routing and AI rewriting.
  A single `text` allows AI to create distinct TTS-safe and visual variants
  without changing the selected output channels or adding new devices.
- Existing channel-only YAML automations continue to work unchanged.
  Empty override values fall back to `text`, while entirely empty messages
  remain invalid.
- Updated service forms, Greek/German/English translations, documentation
  and regression tests for new and legacy message combinations.

## 0.9.25 - 2026-10-17

- Fixed Critical announcements ignoring an explicit `service` integration or
  entity target and expanding to every configured output (including TTS).
- `service` and explicit `output` rooms are now **strict routing constraints**
  at every severity: only selected physical targets are frozen into the job,
  whether immediately available or not, with no level/channel substitution or
  fallback to other rooms/devices.
- Unavailable explicitly selected targets use the existing
  output-availability timeout and then skip silently. No TTS or Companion App
  speech is activated when only visual notifications were selected.
- Explicit areas now exclude general/unassigned outputs. When
  `occupied_only: true`, the existing occupancy intersection is preserved.
- Added `strict_targets` to the send action response and persisted job/status
  for transparent verification; legacy queued jobs remain readable.
- Explicitly empty `service: []` or `output: []` fails validation instead of
  silently becoming an unrestricted Critical broadcast; omit the field to
  request automatic routing.
- Preserved the previous automatic Critical broadcast and level/fallback
  behavior when no explicit selectors are supplied. Updated action help in
  English, German and Greek and added executable routing regression tests.

## 0.9.24 - 2026-10-17

- Added optional `click_action` to `notify.announcement_hub` and its legacy
  `announcement_hub.send` alias. The URL/deep link is stored with each queued
  announcement and applied only to compatible Companion App visual outputs.
- Map Companion App Android taps to `data.clickAction` and iOS/macOS taps to
  `data.url`, preserving other provider-specific `notify_data` and allowing
  the explicit top-level click_action to override those keys.
- Avoid passing unsupported click-action metadata to Android TV/Fire TV,
  generic notification providers, and all audible TTS paths.
- Clarified existing `service` integration/entity selector (including its
  critical-alert broadcast exception), updated EN/DE/EL action descriptions,
  and added routing/provider/persistence regression tests.

## 0.9.23 - 2026-10-17

- Fixed AI "Home Assistant default" incorrectly calling `conversation.process`
  without an `agent_id`, which always selected the built-in intent-only
  agent and caused `no_intent_match`.
- The default AI option now resolves the conversation engine from the
  **preferred Assist pipeline** at announcement time and passes its actual
  `agent_id` and preferred language to Home Assistant's conversation action.
- Default and backup agent selectors now follow the current preferred pipeline.
  The selected pipeline's agent appears in the dropdown and AI diagnostics.
- If the preferred Assist pipeline is unavailable or points to the built-in
  intent-only agent, retry the configured backup agent if available; otherwise
  deliver the original message unchanged without invoking the intent agent.
- Added regression tests for dynamic preferred pipeline selection, explicit
  overrides, missing/default built-in agents, backup deduplication and Greek
  language selection. Preserved EN/DE/EL translations and routing behavior.

## 0.9.22 - 2026-10-17

- Fixed AI response parsing for Home Assistant conversation agents that return
  `action_done` for a text-only response with no affected devices, while
  continuing to reject responses reporting actual device actions or errors.
- Kept `use_ai` a true three-way action setting: omitted inherits the saved
  integration default; explicit true/false overrides that default.
- Added `ai` metadata to queued announcements and the send action response,
  including effective enablement/source, attempted agents, accepted/unchanged
  rewrites, and safe error/fallback categories without leaking message content.
- Hardened AI failure handling so malformed provider/parser responses fall
  back to the original text and do not block a queued announcement.
- Expanded tests for the user's templated automation, backup agents, the HA
  default intent-only agent, response migration, and EN/DE/EL setup help.

## 0.9.21 - 2026-10-17

- Added direct step-selection menus for both Reconfigure and Configure, so
  users can jump to notification outputs, TTS, provider profiles or general/AI
  settings and save without traversing the rest of the setup wizard.
- Existing device selections and configuration sections are preserved when
  editing another section, including previous data/options overrides.
- First-time setup remains a guided sequence; the full edit wizard is still
  available as an explicit menu choice. EN/DE/EL menu translations added.

## 0.9.20 - 2026-10-17

- AI now produces two independent output variants in one request: plain,
  speech-ready text for TTS and expressive visual text for notifications.
- Speech results are normalized to remove emoji/emoticons, simple Markdown
  decoration and line breaks; unsafe HTML/SSML/links trigger the existing
  backup-agent and unchanged-original fallback.
- AI now receives the actual resolved delivery-plan texts, including speech
  synthesized from visual-only Critical alerts and level/room fallback paths.
  This does not enable new channels or modify announcement routing.
- Preserve signed numerical readings during AI validation, preventing a
  negative temperature from silently becoming positive (or vice versa).
- Added tests for multilingual-friendly channel separation, speech hygiene,
  decorated visual messages, numeric signs and fail-open recovery.

## 0.9.19 - 2026-10-17

- Added **Rewrite announcements with AI** in integration setup/options, with a
  selectable Home Assistant conversation agent (HA default preselected). AI is
  disabled by default for backwards compatibility.
- Added per-announcement overrides `use_ai: true/false` and `ai_agent` to
  `notify.announcement_hub` and legacy `announcement_hub.send` actions.
- Added a configurable backup conversation agent: primary AI, optional backup
  AI, and guaranteed original-message fallback when AI is unavailable, fails,
  times out, or returns faulty or malformed text. Without a backup agent,
  the original message is delivered directly after a failed primary attempt.
- Hardened AI reply validation to reject failed/refused replies, changed
  numerical readings, empty or oversized responses, and malformed JSON.
- Original spoken/visual messages, output selections, severity, queue routing
  and notification metadata are preserved when AI rewriting is skipped.
- AI rewriting is performed once before an announcement is persisted in the
  queue; already queued jobs are not reprocessed after a restart.
- Translated new configuration/action fields into English, German and Greek.
- Added AI success/failure, timeout, validation, backup and cancellation tests.

## 0.9.18 - 2026-10-11

- Fixed NFAndroidTV power association when the same physical TV is exposed by
  multiple Home Assistant media-player integrations on the same exact host/IP.
- Exact-host media players are now treated as an observer set for one physical
  notification endpoint instead of making the association fail as ambiguous.
- Existing shared-device-registry identity remains the strongest association;
  exact host/IP remains the fallback identity, with area used only to narrow
  already-exact host matches.
- Visual delivery stays eligible when any reliable observer positively reports
  the TV active. TTS fallback is selected only when every observer is off,
  standby, unavailable, unknown, or missing state.
- Added `standby` to the power-off states.
- The association remains vendor-agnostic: entity names, friendly names, models,
  Sony-specific identifiers, and fuzzy text matching are not used.

## 0.9.17 - 2026-10-11

- Added automatic association between room-bound NFAndroidTV notification
  outputs and the physical TV media_player when Home Assistant exposes a
  reliable identity link.
- Association first uses a shared Home Assistant device-registry device, then
  falls back to an exact configured host/IP match between the NFAndroidTV config
  entry and media-player config entries.
- If multiple exact host matches exist, Home Assistant area is used only to
  disambiguate those already-exact matches.
- Entity IDs, friendly names, and other text similarity are never used to infer
  an association.
- When the associated media player is off, unavailable, or unknown, the
  NFAndroidTV room notification is treated as unavailable even if the notify
  entity/service itself remains registered.
- This lets the existing room-routing logic correctly promote the room's TTS
  tier when the TV is actually off.
- If no unique strong association can be established, Announcement Hub keeps the
  existing notify-transport availability behavior instead of guessing.

## 0.9.16 - 2026-10-11

- Fixed the case where a target room's normal-level visual output is configured
  but currently off/unavailable while the room also has a TTS route.
- General/movable notifications no longer leave the room without a fixed
  delivery path in that situation.
- If no fixed-room output is currently available and the room has a TTS route,
  Announcement Hub selects that room TTS path as the delivery fallback tier.
- If the selected room TTS path is unavailable/unknown, it remains frozen in
  the job and is waited for until the configured availability timeout.
- If the room has no TTS path at all, the unavailable normal-level visual output
  remains the wait target.
- Cross-room fallback behavior is unchanged and still requires zero fixed-room
  candidates in the target room set.

## 0.9.15 - 2026-10-11

- Fixed a level-routing regression where TTS could be relaxed independently from
  an already valid same-room visual output.
- Fixed-room candidates are now filtered by announcement level first. If a
  normal-level fixed-room candidate exists, it is used and below-threshold TTS
  remains suppressed.
- Only when no fixed-room candidate survives the level filter does Announcement
  Hub relax to the nearest fixed-room tier.
- General/movable notifications do not satisfy the fixed-room delivery
  requirement and therefore cannot suppress the room fallback tier.
- Once TTS is legitimately selected, unavailable/unknown TTS targets remain
  frozen in the job and wait for the configured availability timeout.
- Fallback room routing now requires zero fixed-room candidates in the target
  room set, not merely zero fixed TTS candidates.
- Explicit room routing and occupancy routing now use the same fixed-room level
  selection semantics.
- Updated README and English, German, and Greek fallback help.

## 0.9.14 - 2026-10-07

- Fixed a regression where `occupied_only: true` was ignored whenever an
  explicit `output:` room list was also supplied.
- `occupied_only: true` + explicit `output:` now uses the intersection of
  the explicit room list and the currently occupied rooms.
- `occupied_only: true` without `output:` continues to target the currently
  occupied rooms.
- `occupied_only: false` + explicit `output:` keeps the explicit room list
  authoritative.
- General/movable output behavior, TTS fallback candidate rules, and
  unavailable/unknown TTS timeout handling are unchanged.
- Updated README and English, German, and Greek action help.

## 0.9.13 - 2026-10-07

- Fixed a planner bug where supplying both `text_tts` and `text_notify` could
  suppress the TTS path even though the same `text_tts`-only announcement
  selected and played TTS correctly.
- TTS candidate selection is now resolved independently from visual notification
  candidate selection. An available notify output can no longer prevent requested
  TTS from selecting its own level/fallback path.
- Preserved nearest-level relaxation for TTS while keeping `never` as the hard
  TTS disable except for Critical announcements.
- Kept unavailable/unknown TTS targets frozen into the job so they still receive
  the full configured availability-timeout window.
- Fallback-room TTS can now be used when the TTS level was relaxed, instead of
  being blocked solely by the original threshold.

## 0.9.12 - 2026-10-06

- Made explicit `output:` rooms authoritative for `notify.announcement_hub`.
  When rooms are supplied by the action, occupancy no longer intersects,
  replaces, or modifies those room targets.
- Occupancy routing still applies normally when `output:` is omitted and
  `occupied_only` is enabled.
- General/movable outputs remain eligible according to their configured policy.
- Changed TTS fallback to use fixed TTS candidate existence instead of current
  availability. A configured fixed TTS candidate that is unavailable or unknown
  blocks fallback and is waited for until the configured availability timeout.
- The fallback TTS room is used only when the current target room set contains
  zero fixed TTS candidates at all. Fallback remains TTS-only.
- Selected TTS outputs are now retained in the frozen job even when currently
  unavailable/unknown, so direct TTS, Snapcast and Companion App TTS get their
  full availability-timeout window.
- Snapcast no longer drops unavailable clients when some selected clients are
  already ready; ready clients play first and remaining selected clients wait
  until timeout.
- Fallback door checks now refer to the current target rooms regardless of
  whether those rooms came from occupancy or an explicit action `output:`.
- Updated English, German and Greek help text plus routing regression coverage.

## 0.9.11 - 2026-10-06

- Added `notify.announcement_hub` as the canonical Announcement Hub action.
- The new notify-domain action keeps the full Announcement Hub payload, routing
  selectors, queue behavior, and optional service response.
- Registered a rich Home Assistant service description for
  `notify.announcement_hub` so the action remains usable from the action UI.
- Made the Home Assistant `notify` integration a setup dependency so the notify
  domain is ready before Announcement Hub registers its action.
- Kept `announcement_hub.send` as a backward-compatible legacy alias so existing
  automations continue to work; new automations should use
  `notify.announcement_hub`.
- Queue management remains under `announcement_hub.cancel` and
  `announcement_hub.clear_queue`.
- Updated README examples and English, German, and Greek service labels.

## 0.9.10 - 2026-10-04

- Fixed Snapcast TTS tail clipping. Announcement Hub now keeps the active
  Snapcast route open for a short drain window after Home Assistant reports the
  source/client path idle, so buffered speech can finish before mute states are
  restored.
- Preserved gapless same-route handoff: when the next queued announcement is
  already prepared and uses the exact same Snapcast route, the drain/restore
  cycle is skipped and the route is handed directly to the next utterance.
- Fixed explicit area routing without an occupancy sensor. Areas supplied in the
  action's `output:` field now constrain the candidate/level planner itself,
  not only the later delivery stage.
- General/movable outputs intentionally remain eligible when occupancy is
  unavailable or resolves to no occupied room; only room-bound outputs lack a
  room target in that situation.
- Prevented one media player from being used simultaneously as a Direct TTS
  target and the shared Snapcast source player. Setup now rejects that overlap,
  and runtime also filters it for older stored configurations.
- Added regression coverage for explicit-area planning, General-output behavior,
  TTS player role separation, and Snapcast route drain/handoff behavior.

## 0.9.9 - 2026-10-04

- Changed TTS engine selection from a multi-select to exactly one active engine.
  Existing multi-engine configurations remain readable, but setup, new jobs,
  restored queue jobs and runtime delivery use only the first configured engine.
- Home Assistant's default TTS engine remains automatically preselected when no
  engine is already configured.
- Fixed Wyoming/Piper voice discovery when the selected language is generic but
  the installed voice is advertised under a locale variant, e.g. `el` with
  `el_GR` or `el-GR`.
- Voice support is detected from the TTS entity's Home Assistant capabilities.
  When voices can be enumerated, the setup shows a dropdown; if the provider
  accepts a voice option but cannot enumerate values, a manual voice-ID field is
  still shown instead of hiding voice configuration.
- Changing the engine or language refreshes the same TTS setup page once so the
  language and voice controls are rebuilt for the exact provider before saving.
- Updated English, German and Greek setup wording to use the singular TTS engine
  model and added runtime regression coverage.

## 0.9.8 - 2026-10-04

- Simplified the TTS setup page by removing the separate generic direct-player
  selector. There is now one direct TTS player selector and every selected
  player is automatically room-scoped.
- Direct TTS discovery now offers only media players that have a Home Assistant
  area, matching the occupied/fallback room routing model.
- Home Assistant's default TTS engine is preselected whenever no engine is
  already configured.
- Moved the selected engine's language and additional TTS options directly
  underneath the engine selector.
- Added a TTS voice selector when the selected engine and language expose
  supported voices through Home Assistant. Existing/provider default voice
  selection is preserved when possible and stored through the existing TTS
  options payload.
- Updated English, German and Greek setup labels/help and README documentation.
- Added regression coverage for the single direct-player selector, default
  engine preselection, engine language/voice discovery and field ordering.

## 0.9.7 - 2026-10-04

- Reworked TTS delivery into a continuous producer/consumer pipeline. Every
  queued server/direct-player utterance starts rendering immediately in the
  background while the current announcement is still playing, even when file
  caching is disabled.
- Playback now waits only for the preferred engine render needed for the current
  attempt instead of waiting for every configured fallback engine to finish
  rendering.
- Visual and audible channels now run concurrently for the same announcement
  while preserving the configured launch order.
- Direct room TTS, shared server/Snapcast TTS, and opted-in Companion App TTS
  launch as independent parallel audio paths. Multiple direct room players and
  Companion App TTS outputs also start in parallel.
- Final visual reading timers no longer delay the next spoken announcement when
  the same job already has audible delivery.
- The intentional post-play cushion is skipped whenever another audible job is
  queued.
- Consecutive already-rendered announcements using the exact same verified
  Snapcast route can hand that route directly to the next item, avoiding the
  restore/reapply settle gap. The original mute state is restored immediately
  when the route changes, the queue drains, or the chain ends.
- Partial Snapcast rounds are never held warm while waiting for late clients.
- Added continuous-pipeline regression coverage; the full suite passes.

## 0.9.6 - 2026-10-03

- Fixed occupied-room candidate classification so movable outputs do not count
  as room candidates. Mobile App notification outputs and Companion App TTS can
  still be used normally, but they cannot suppress fixed-room routing.
- Fixed room-level selection so the occupied room first uses outputs matching
  the announcement level and relaxes to the nearest usable room threshold when
  the normal level filter leaves no room delivery path.
- Made default-room fallback TTS-only. Visual/general notifications stay on
  their original outputs instead of being rerouted to the fallback room.
- When no fixed-room candidate is currently available, the configured fallback
  room is used only when the occupied-room door policy allows it; otherwise the
  normal availability timeout remains responsible for waiting on room outputs.
- Added regression coverage for movable-output exclusion, fixed-room waiting,
  level relaxation, and TTS-only fallback behavior.

## 0.9.5 - 2026-10-03

- Fixed the actual room-output selection bug: occupied-room routing now requires
  an independent room-local delivery choice in addition to any General/movable
  notifications.
- General outputs such as laptops, phones, watches, and tablets can still receive
  the announcement, but they can no longer suppress the best available output
  in the occupied room.
- If no room output normally matches the level, the occupied room now uses its
  nearest available room-output level immediately, exactly like the fallback-room
  pass. Example: Info + Wohnzimmer TTS at Warning -> Wohnzimmer TTS is still
  selected while General Info/Debug notifications may also be sent.
- If the occupied room has zero room candidates, fallback-room behavior remains:
  the fallback room independently chooses its own best room-local output.
- Reverted the speculative v0.9.4 behavior that bypassed Snapcast source matching
  for explicitly selected clients. Snapcast source filtering remains strict.

## 0.9.4 - 2026-10-03

- Corrected Snapcast TTS-source semantics.
- The Snapcast entry/entities selected in Announcement Hub configuration are now
  authoritative membership of the TTS Snapcast path.
- Room routing first filters those selected clients by Home Assistant area, then
  checks whether the resulting room client is connected and mute-controllable.
- Explicitly selected TTS clients are no longer rejected merely because their
  current Snapcast group stream/source label differs from the configured source
  text.
- The optional source restriction is still applied to unselected Snapcast
  clients included in the mute snapshot, preventing unrelated Music clients from
  being muted by announcement routing.
- This fixes occupied rooms such as Wohnzimmer and fallback rooms such as Flur
  returning zero snapcast_clients even though the selected TTS Snapcast entry
  contains a client assigned to that area.

## 0.9.3 - 2026-10-03

- Fixed Snapcast TTS-room detection when Home Assistant exposes the client's
  current source as a Snapcast stream identifier instead of the friendly stream
  name configured in Announcement Hub.
- Room routing remains area-first: only Snapcast clients in the occupied or
  fallback area are considered.
- The configured TTS source name is now resolved through the live Snapcast
  entity's stream map and compared to the current stream identifier.
- The same source-resolution logic is used both when deciding whether a room
  output is currently available and later when building the mute/routing
  snapshot, preventing inconsistent selection.
- Source filtering remains strict; a Music client in the correct room is not
  accepted as a TTS client merely because its area matches.

## 0.9.2 - 2026-10-03

- Fixed a false-positive fallback route where General/movable outputs made the
  fallback plan non-empty even though no fallback-room output was actually
  selected.
- Fallback is now committed only when a room-bound output from the configured
  fallback area is really present in the selected delivery plan.
- This prevents responses from claiming Flur fallback while the job contains
  only general phone/laptop/watch notifications.
- Removed Home Assistant internal area IDs from the normal send-action response;
  "outputs" now exposes only friendly area names.

## 0.9.1 - 2026-10-03

- Fixed room fallback being blocked by General/movable notification outputs.
- Occupancy fallback now asks whether the occupied room has any room-bound
  candidate, instead of using DeliveryPlan.has_output across general and room
  outputs together.
- When the occupied room has zero room-bound candidates, the configured fallback
  room is evaluated even if phones, laptops, watches, or other General outputs
  remain available.
- The fallback-room pass explicitly requires room-local delivery. If a fallback
  room output is available, its normal matching level is preferred; otherwise
  the nearest available level is used immediately. This allows an Info
  announcement to use Warning-level Flur TTS when Küche has no room output.
- General/movable outputs remain in the same job and may still receive the
  announcement; they no longer suppress room fallback.
- An available General output does not make the queue wait for an unavailable
  fallback-room output. Waiting for the fallback room occurs only when no output
  class is currently available.
- Service responses now show friendly Home Assistant area names in "outputs"
  and expose the internal stable IDs separately as "output_area_ids".

## 0.9.0 - 2026-10-03

- Added immediate availability-aware fallback across notification and TTS output
  classes without changing the announcement's actual severity.
- If currently available outputs normally match the level, all such matching
  outputs are used.
- If no available output normally matches, Announcement Hub immediately selects
  the currently available output tier whose configured minimum level is nearest
  to the announcement level.
- If only one usable output path is available, it is used immediately regardless
  of its normal minimum level; an unavailable preferred path does not make it
  wait.
- Cross-channel fallback reuses the available message text: notification text can
  be spoken by TTS, and TTS text can be shown visually when that is the selected
  fallback path.
- When shared TTS/Snapcast is selected as an immediate fallback, only currently
  available matching Snapcast clients are frozen into the job so unavailable
  clients do not delay delivery.
- When no output of any class is currently available, the existing availability
  timeout behavior remains: the preferred configured tier waits and other queued
  runnable jobs may pass it.
- TTS level "never" remains a hard disable for non-critical announcements.

## 0.8.3 - 2026-10-02

- Replaced free-text TTS language entry with a dropdown populated from the
  languages currently advertised by available TTS engines.
- Automatically chooses a compatible preferred/default TTS language when one
  exists.
- Reworked labels and per-field help text across all four setup stages in
  English, German, and Greek.
- Every visible setup field now explains separately what it controls and how
  Announcement Hub uses it at runtime.
- Renamed the integration-options page so Snapcast is no longer presented as
  visual/optical behavior.
- Added regression tests that reject raw field keys, missing help text, and a
  free-text TTS language selector.

## 0.8.2 - 2026-10-02

- Fixed the TTS setup crash when Snapcast is installed.
- Snapcast discovery now filters SelectOption objects through their value
  attribute before serializing them to Home Assistant selector dictionaries.
- Added a regression test for the exact object/dict mismatch that produced
  "TypeError: 'SelectOption' object is not subscriptable".

## 0.8.1 - 2026-10-02

- Notification setup now preselects every currently recognised supported notify
  entity whenever the page opens; users deselect outputs they do not want.
- Added resource contracts requiring translated labels for every notification
  grouping field in English, German, and Greek.
- Removed the obsolete per-output notification-routing config-flow methods left
  behind by the four-step setup redesign.
- No notification delivery or queue semantics changed.

## 0.8.0 - 2026-10-02

- Reworked setup into four conceptual stages: Notification outputs, TTS outputs,
  per-integration options, and General options.
- Notification discovery now lists concrete supported entities as
  Integration · Device · Entity and selects all recognised outputs by default on
  first setup. Room/movable scope and minimum notification level are configured
  on the same page through grouped multi-selects.
- TTS discovery now lists concrete TTS engines with advertised languages and
  automatically selects Home Assistant's default engine when available.
- When Snapcast clients are discovered, the TTS page offers those room clients
  plus the shared media player that drives their synchronized stream.
- Non-Snapcast media players with play-media support are offered as direct TTS
  outputs. Area-bound players default to Room scope; area-less players default
  to General scope.
- TTS keeps one global minimum level.
- Integration-specific visual options and Snapcast routing behavior are grouped
  under the third setup stage.
- General options now combine queue/timeouts, room-presence entity and
  state/attribute source, fallback room, door checking, and an optional Home
  Assistant label that restricts which door entities may authorize fallback.
- General direct TTS outputs bypass occupancy filtering; Room outputs continue
  to follow occupied/fallback areas.

## 0.7.0 - 2026-10-02

- Added per-device visual notification routing policies in setup.
- Every concrete notify output now has an explicit Room-based or General/movable
  scope plus its own minimum announcement level.
- Room-based outputs follow occupied-area and fallback-room routing.
- General/movable outputs bypass occupancy area filtering and can notify
  regardless of the currently occupied room.
- Notification level thresholds are debug, info/success, warning, error, and
  critical; success shares info priority.
- Policies are applied before a job is frozen so queued jobs keep deterministic
  output membership even if settings change later.
- Existing outputs default to Room-based when they have an HA area and General
  when they do not, with debug as the backward-compatible minimum level.

## 0.6.0 - 2026-10-02

- Split server/direct TTS setup into three explicit roles.
- Added area-bound direct room TTS media players for voice assistants and
  speakers that should receive generated TTS directly.
- Renamed the existing TTS media-player concept in the UI to the shared TTS
  server media player. It is global infrastructure (for example MPD feeding a
  Snapserver stream) and is never area-filtered.
- Moved Snapcast client selection into the TTS routing page and labelled those
  clients as synchronized room-routing players. They remain physical room
  candidates, but Announcement Hub sends no TTS/play-media command to them;
  it manages only mute/routing while the shared player feeds the stream.
- Direct room TTS players are frozen with their Home Assistant areas in each
  queued job and participate in occupancy/readiness scheduling.
- Existing MPD + Snapcast configurations remain compatible.
- No new long-lived tasks were introduced.

## 0.5.4 - 2026-10-02

- Fixed first-use server-TTS readiness deadlock.
- TTS engines are now treated as global infrastructure and no longer require a
  pre-existing TTS entity state before the first utterance.
- A TTS engine is considered attemptable from its enabled entity registration
  and loaded owning config entry; an explicit unavailable state is still
  respected.
- The shared server-TTS media player remains global infrastructure and is never
  area-filtered.
- Only Snapcast clients are physical server-TTS room outputs and participate in
  occupied-area routing.
- No queue worker or Home Assistant startup-task lifecycle behavior changed.

## 0.5.3 - 2026-10-02

- Replaced strict FIFO dequeueing with a readiness scheduler.
- A pending job whose outputs are unavailable stays pending until its availability
  timeout, but no longer blocks newer jobs that can run immediately.
- The scheduler always picks the oldest currently runnable job, preserving order
  among runnable work while allowing unavailable waiters to be overtaken.
- Timed-out jobs with no runnable output complete as silent no-ops.
- Actual announcement execution remains strictly serialized: only one job is
  processing at a time, so announcements do not interrupt each other.
- Readiness checks cover visual notify outputs, server TTS/Snapcast, and
  Companion App TTS.
- No new long-lived tasks were added; the startup-safe ConfigEntry worker
  lifecycle remains unchanged.

## 0.5.2 - 2026-10-02

- Added supervision for the permanent serialized queue worker.
- Every accepted announcement now verifies that a live worker exists before the
  wake event is signalled.
- An unexpectedly stopped worker is logged with its real exception and restarted
  automatically on the next event-loop turn.
- Options updates also verify worker health and wake pending work.
- Exposed worker_alive in diagnostics/status data.
- The worker remains a ConfigEntry background task; no normal Home Assistant
  startup-blocking task was introduced.

## 0.5.1 - 2026-10-02

- Moved occupancy and fallback settings out of the generic Outputs page into a
  dedicated translated Occupancy routing step.
- Replaced the free-text occupancy attribute field with a live dropdown built
  from the selected entity's current attributes.
- Added State as an explicit translated dropdown choice; internally it keeps the
  existing empty-attribute representation, so routing behavior is unchanged.
- The occupancy entity is selected first, then the source dropdown is generated
  from that exact entity.
- No queue, routing, availability-timeout, or background-task lifecycle behavior
  changed.

## 0.5.0 - 2026-10-02

- Added an optional fallback room for occupancy-aware routing.
- Fallback is considered only when the occupancy-filtered announcement has zero
  configured candidates; temporarily unavailable devices remain normal
  candidates and continue to use the availability timeout.
- Added an optional door gate, enabled by default. When enabled, fallback occurs
  only if at least one occupied target area has an open binary sensor with
  `device_class: door`.
- Closed, unavailable, unknown, or missing door sensors block fallback.
- Fallback uses only outputs assigned to the fallback room and preserves service
  restrictions, TTS level policy, Companion App TTS opt-in, and availability
  timeout behavior.
- No new long-lived tasks were introduced; the config-entry background-task
  lifecycle remains unchanged.

## 0.4.0 - 2026-10-02

- Added an optional occupied-areas sensor with an optional attribute containing
  Home Assistant area names/IDs.
- Added `occupied_only` to `announcement_hub.send`, enabled by default.
  Explicit output areas are intersected with occupancy; an omitted output targets
  the currently occupied areas.
- Occupancy filtering is capability-neutral: each occupied area receives only
  the configured output types actually present in that area.
- Outputs without an area are excluded while occupied-only filtering is active.
- An unavailable occupancy sensor or an empty occupied-area list is a silent
  no-op, never a broadcast fallback.
- Existing unavailable-output retry/timeout behavior and config-entry background
  task lifecycle remain unchanged.

## 0.3.4 - 2026-10-02

- Treat outputs that remain unavailable after the configured wait window as
  skipped outputs instead of delivery errors.
- Stop emitting warning logs, channel-failed events, and
  `completed_with_errors` solely because a TV, phone, Snapcast client, media
  player, or TTS engine is offline.
- Let an announcement complete as a successful no-op when every matching output
  stays unavailable; actual configuration and processing errors still fail.
- Preserve the config-entry background-task lifecycle fix so this behavior does
  not participate in Home Assistant startup.

## 0.3.3 - 2026-10-02

- Fixed Notifications for Android TV / Fire TV disappearing entirely when the
  advanced legacy `notify.<name>` action is absent or registered under another
  name.
- Added an executor-safe fallback through the integration config entry's live
  `Notifications` runtime client, preserving position, duration, font, colour,
  transparency, and interrupt.
- Kept the provider action as the first choice where available so image/icon
  loading remains supported.

## 0.3.2 - 2026-10-02

- Fixed Notifications for Android TV / Fire TV placement and styling being
  silently dropped when the modern notify entity ID differed from the legacy
  notify action name.
- Resolve the advanced Android TV notify action from the owning config-entry
  title, matching Home Assistant's own legacy-service registration.
- Retry while the advanced action is unavailable instead of falling back to
  `notify.send_message`, which cannot carry position or style options.
- Preserve integration and area discovery when a legacy notify service is
  selected directly.

## 0.3.1 - 2026-10-02

- Fixed the permanent queue worker being registered as a normal Home Assistant
  task, which made it participate in the startup barrier and survive into final
  shutdown writes.
- Registered the worker and TTS prefetch jobs as config-entry background tasks,
  so they do not block startup and are automatically cancelled with the entry.
- Added an awaited Home Assistant shutdown job plus serialized, idempotent
  manager cleanup to cancel all tasks and persist the queue before shutdown.
- Added lifecycle regression tests preventing normal `hass.async_create_task`
  use from returning to the integration.

## 0.3.0

- Added one visual delivery profile per configured notify integration.
- Added natural multipart splitting with sentence, clause, and whitespace
  boundaries before any hard cut.
- Added word-count reading-time calculation with minimum, maximum, and buffer
  controls; the queue holds each part long enough before advancing.
- Added Notifications for Android TV / Fire TV placement, font size, color,
  transparency, interaction, and calculated duration options.
- Added Companion App multipart replacement so consecutive parts do not stack.
- Added provider-specific data and froze resolved profiles into persistent jobs.
- Visual outputs for the same announcement now run concurrently while each
  individual output's parts remain strictly ordered.

## 0.2.0 - 2026-10-02

- Replaced allowed/default provider lists with output-centric integration,
  config-entry, entity, and legacy-service selections.
- Added automatic Home Assistant area discovery for visual, Snapcast, and
  Companion App TTS outputs.
- Preserved omitted-`output` broadcast behavior across every configured output.
- Added immediate delivery to available outputs and a configurable retry window
  for unavailable outputs and transient delivery failures.
- Added a minimum TTS level; below the threshold, speech stays muted and text is
  preferentially delivered through visual notifications.
- Kept critical announcements audible and expanded them to all configured
  matching physical outputs.
- Added optional Android Companion App push TTS with per-action opt-in defaulting
  to off, stream selection, and serialized estimated playback duration.
- Prevented same-stream leakage by muting and restoring all current Snapcast
  clients on the managed announcement source, not only eligible targets.
- Froze output entities, area bindings, media player, and Companion TTS settings
  inside each queued job.
- Added automatic v0.1 config-entry and stored-queue migration.
- Updated English, German, and Greek UI translations.

## 0.1.0 - 2026-10-01

- Initial Home Assistant-native persistent announcement queue.
- Separate spoken and written content with optional area targeting.
- Configurable TTS entities, notify entities, and legacy notify services.
- Critical delivery through every allowed provider.
- Early TTS rendering while earlier announcements are playing.
- Verified Snapcast mute routing with exact state restoration.
- Queue diagnostics, cancellation, clearing, and lifecycle events.
- English, German, and Greek UI translations.
