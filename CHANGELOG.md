# Changelog

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
