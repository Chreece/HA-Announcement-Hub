# Changelog

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
