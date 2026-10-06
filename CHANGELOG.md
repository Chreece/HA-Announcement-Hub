# Changelog

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
