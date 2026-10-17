<p align="center">
  <img src=".github/assets/announcement-hub-banner.svg" alt="Announcement Hub for Home Assistant" width="100%">
</p>

<p align="center">
  <a href="https://github.com/Chreece/HA-Announcement-Hub/releases"><img alt="GitHub release" src="https://img.shields.io/github/v/release/Chreece/HA-Announcement-Hub?display_name=tag&sort=semver"></a>
  <a href="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/validate.yml"><img alt="Tests" src="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/validate.yml/badge.svg"></a>
  <a href="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/hacs.yml"><img alt="HACS" src="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/hacs.yml/badge.svg"></a>
  <a href="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/hassfest.yml"><img alt="Hassfest" src="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/hassfest.yml/badge.svg"></a>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=Chreece&repository=HA-Announcement-Hub&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open Announcement Hub in HACS">
  </a>
</p>

<!-- ko-fi-support -->
<p align="center">
  <a href="https://ko-fi.com/chreece">
    <img src="https://raw.githubusercontent.com/Chreece/pir2ha/main/.github/ko-fi-banner.svg" alt="Support Chreece on Ko-fi" width="600">
  </a>
</p>

# Announcement Hub for Home Assistant

Announcement Hub is a Home Assistant-native, persistent queue for spoken
announcements and visible notifications. It selects outputs by integration,
config entry, entity, service, and Home Assistant area, then executes every job
without overlapping the next one.

It does **not** run an external daemon, request a Home Assistant token, create
helpers, edit automations, or change MPD/Snapserver configuration.

## Main behavior

- Adds the primary announcement action `notify.announcement_hub`, plus
  `announcement_hub.cancel` and `announcement_hub.clear_queue`.
- Keeps `announcement_hub.send` as a backward-compatible legacy alias for
  existing automations; new automations should use `notify.announcement_hub`.
- Accepts `text_tts`, `text_notify`, or both; at least one is required.
- Persists waiting jobs across Home Assistant restarts.
- Freezes each job's selected outputs, area bindings, player, TTS settings, and
  notification data when the job enters the queue.
- Treats TTS as a continuous producer/consumer pipeline: every queued server or
  direct-player utterance starts rendering immediately in the background, even
  when file caching is disabled, while the current announcement is still playing.
- Keeps announcement order on shared audio paths, but starts independent audible
  output classes (direct room players, shared server/Snapcast, and opted-in
  Companion App TTS) together for the same announcement.
- Runs visual delivery alongside spoken delivery instead of making one channel
  finish before the other can begin.
- Resolves fixed-room delivery by announcement level first. If a normal-level
  fixed room output exists, it is used; only when none survives the level filter
  does Announcement Hub relax to the nearest fixed-room tier.
- Uses available outputs immediately and gives unavailable or transiently
  failing outputs one configurable retry window before recording a timeout.
- Supports visible notifications through modern `notify.*` entities and legacy
  `notify.<service>` actions.
- Supports Android Companion App push TTS as an optional audible output. Eligible
  devices are selected in setup, while ordinary action calls opt in with
  `companion_tts: true`; the action option defaults to `false`.
- Routes selected Snapcast clients by Home Assistant area and verifies the mute
  state before speech. For consecutive already-rendered announcements using the
  exact same route, the verified route is handed directly to the next item to
  avoid restore/reapply settle gaps; the original mute state is restored as soon
  as that chain ends or the route changes.
- Provides a diagnostic queue sensor and lifecycle events.

## Installation

Copy:

```text
custom_components/announcement_hub
```

to:

```text
/config/custom_components/announcement_hub
```

For the Docker configuration used on this homeserver:

```text
/home/chreece/homeassistant/config/custom_components/announcement_hub
```

Or run the included installer from the extracted project directory:

```bash
./install.sh
```

The installer validates the component, backs up any existing copy under
`~/.local/state/ha-integration-backups/announcement_hub/`, and atomically
replaces only the custom-component directory. It does not restart Home
Assistant.

Restart Home Assistant manually, then add **Announcement Hub** from
**Settings → Devices & services → Add integration**.

## Setup: outputs instead of allowed/default providers

Version 0.2 removes the former **Allowed** and **Default** provider lists. Every
item selected in setup is a configured output. An output may be selected at one
of three scopes:

```text
Integration → all matching output entities
Config entry → every matching entity belonging to that entry
Entity → one exact output
```

Legacy notification actions can also be entered as `service:notify.name` and
are treated as global because Home Assistant does not expose an area for an
arbitrary service.

### Outputs page

Select any combination of:

- **Visual notification outputs** — Notifications for Android TV, Companion App
  notifications, and other `notify` entities/services.
- **Snapcast audio outputs** — Snapcast clients eligible to receive an
  announcement. Selecting these enables automatic mute/unmute room routing.
  Other clients currently attached to the managed announcement source are also
  temporarily muted and restored so the message cannot leak to them.
- **Companion App TTS outputs** — Android Companion App devices that may speak.
  Selecting them only makes them eligible; ordinary action calls still opt in.

Output entries inherit their area from the entity or device registry. Assign
TV, phone, and Snapcast devices to their correct Home Assistant areas.

### Text-to-speech page

Configure:

- exactly one active TTS engine, such as the Piper/Wyoming TTS entity. Home
  Assistant's default TTS engine is preselected when one is available;
- the active engine's language and voice directly underneath it. Voice discovery
  accepts locale-compatible variants, so a generic language such as `el` can
  use voices advertised as `el_GR`/ `el-GR`. If an engine accepts a voice
  option but cannot enumerate values, the voice field remains available for a
  manual voice ID;
- any remaining provider-specific TTS options;
- direct TTS media players **per room**. There is no second generic direct-player
  selector: every direct player selected here is automatically room-scoped;
- when Snapcast is present, the synchronized room clients plus the shared server
  TTS media player, normally `media_player.mpd`;
- the minimum level that is allowed to use audible TTS and cache/prefetch
  behavior;
- Companion App audio stream and estimated words per minute.

The stored configuration keeps the historical `tts_engines` list shape for
backward compatibility, but setup, queued jobs, and runtime delivery always use
at most one engine.

### TTS level threshold

Levels are ordered as:

```text
debug < info/success < warning < error < critical
```

When a job is below **Use TTS from level**:

- server TTS and Companion App TTS are not used;
- `text_notify` is sent to visual outputs;
- when only `text_tts` was supplied, that text becomes the visual notification
  instead of disappearing.

`critical` always remains audible and attempts every configured matching
physical output.

### Snapcast page

Configure the expected announcement source, normally `TTS`, routing settle and
verification timeouts, and whether previous mute states are restored.

For each spoken server-TTS round, Announcement Hub:

1. waits for the shared audio path to become idle;
2. snapshots every currently routable Snapcast client on the managed source;
3. unmutes only the selected requested clients and mutes the others;
4. verifies the real mute states;
5. plays one prepared TTS item through the shared media player;
6. waits for the player and routed clients to finish;
7. restores the exact previous mute states.

If a selected Snapcast output is unavailable, currently available clients hear
the message immediately. The unavailable client is watched during the configured
availability window; if it comes online in time, the message is replayed only to
that late output. Otherwise its timeout is recorded and the queue continues.

### Queue page

Configure:

- visual-before-TTS or TTS-before-visual ordering;
- maximum queue length;
- unavailable-output wait;
- audio-path idle, playback-start, and playback-duration timeouts;
- the gap between audible outputs;
- optional AI message rewriting (off by default) and a conversation-agent
  selector, preselected to **Home Assistant default**.

## Per-integration visual profiles and multipart reading time

After selecting visual notification outputs, setup opens one profile page for
every concrete integration represented by those outputs. Profiles are frozen
into each queued job, so changing options later cannot alter an announcement
that is already waiting.

Every profile provides:

- maximum characters per displayed part (`0` disables splitting);
- reading speed in words per minute;
- minimum and maximum display duration;
- an extra reading-time buffer and a gap between parts;
- optional part numbering in the title;
- provider-specific data merged before per-call `notify_data`.

Splitting prefers a complete sentence (`.`, `!`, or `?`), then a comma or
other clause boundary, and finally whitespace. A word is hard-cut only when
that single word is longer than the configured maximum.

Display time is calculated for every part as:

```text
words / words-per-minute × 60 + buffer
```

and then clamped to the configured minimum and maximum. Parts for one output
remain sequential, while different visual outputs receive the same
announcement concurrently.

### Notifications for Android TV / Fire TV

Placement and styling are delivered through the provider's advanced legacy notify action when available. On modern config-entry installations where that action is absent or named differently, Announcement Hub uses the integration's live runtime client in an executor, preserving position, duration, font, colour, transparency, and interrupt without falling back to generic `notify.send_message`.

For room-routing availability, Announcement Hub automatically associates an
NFAndroidTV notification output with the physical TV's `media_player` observers
when Home Assistant exposes a reliable identity link. It first accepts media
players on the same device-registry device; otherwise it compares the
NFAndroidTV config entry's configured host/IP with media-player config entries.
An exact host may legitimately have several observers when the same TV is
exposed through Android TV, Android TV Remote, Bravia, or another integration.
Those observers are kept as one physical-endpoint group instead of being treated
as an ambiguous match. Home Assistant area is used only to narrow an already
exact host match when matching observers exist in the notification output's area.

Power state is evaluated conservatively across the whole observer group. Any
observer that positively reports an active state keeps visual delivery eligible.
The NFAndroidTV visual output is treated as unavailable only when every reliable
observer is `off`, `standby`, `unavailable`, `unknown`, or has no state. This
allows the room's TTS tier to be selected when the display cannot be shown,
without letting one stale/disconnected integration override another observer
that proves the TV is on. Entity IDs, friendly names, model strings, and fuzzy
text similarity are never used to infer an association. If no strong
device/host association exists, Announcement Hub keeps normal notify-transport
availability rather than guessing.

The native legacy notification action is used when available so each profile
can control:

- bottom-right, bottom-left, top-right, top-left, or center placement;
- small, medium, large, or maximum font;
- background color and transparency;
- interactive/interrupt behavior;
- a duration calculated from the words in the current part.

### Companion App visual notifications

Multipart Companion App notifications use one stable tag by default, causing
each new part to replace the previous part instead of building a stack. This
is independent from the optional Companion App **TTS** output.

## Occupancy-aware routing

Optionally configure an occupied-areas sensor. Its state can contain comma,
semicolon, or newline-separated Home Assistant area names/IDs, or a configured
attribute can contain a list of areas.

`notify.announcement_hub` defaults to `occupied_only: true`. When `output`
is omitted, a configured occupancy source chooses the target rooms. When the
action supplies one or more `output` rooms, **those rooms are authoritative**:
occupancy does not intersect, replace, or otherwise change them.

Filtering is capability-neutral, so a target room with only TTS receives speech
and a room with only visual notify outputs receives only those notifications.
General/movable outputs remain eligible according to their configured policy.

If the configured occupancy source is unavailable or currently resolves to no
occupied areas, room-bound outputs have no room target, but **General/movable
outputs remain eligible**. This is intentional: phones, watches, laptops and
other General outputs can still receive the announcement when nobody is detected
in a specific room.

Use `occupied_only: false` to ignore occupancy for one call. Without a
configured occupancy sensor, the option has no effect.

### Occupancy fallback room

Optionally configure a fallback Home Assistant area. Occupancy routing first
looks for **fixed room candidates** in the occupied room. Room-scoped Android
TV/Snapcast/direct TTS outputs count as fixed candidates. Mobile App notification
outputs and Companion App TTS outputs are moveable and never count as proof that
the occupied room itself has a delivery candidate.

Fixed room candidates are filtered by the announcement level and current
availability first. For example, if the room has an available Info-capable
NFAndroidTV output and TTS begins at Warning, an Info announcement uses the
NFAndroidTV output and TTS remains suppressed.

If that normal-level fixed room output is unavailable/off but the same room has a
configured TTS route, Announcement Hub selects the room TTS path as the fallback
delivery tier instead of letting a General/movable notification satisfy the
room. If the selected TTS path is itself unavailable or unknown, it is kept in
the job and waited for until the configured output-availability timeout. If the
room has no TTS path at all, the unavailable normal-level fixed visual output is
kept as the wait target instead.

Fallback **to another room** is still based on fixed room candidate existence,
not current availability. Any fixed room candidate in the target room prevents
cross-room fallback.

The configured fallback room is considered only when the target room set has
**zero fixed room candidates at all**. **Fallback is TTS-only**: the original
visual/general notifications remain on their original outputs while only the
spoken route is taken from the fallback room.

When **Check target-room door before fallback** is enabled, at least one current
target room must contain a `binary_sensor` with `device_class: door` whose
state is `on` (open). Closed (`off`), unknown, unavailable, or missing door
sensors block fallback. Disable the checkbox to permit the TTS-only fallback
regardless of door state.

## Main action

```yaml
action: notify.announcement_hub
data:
  text_tts: "Το πλυντήριο ολοκλήρωσε το πρόγραμμα."
  text_notify: "Το πλυντήριο τελείωσε."
  output:
    - living_room
    - kitchen
  level: info
```

The call returns as soon as the job has been accepted. It does not wait for the
queued playback to finish.

### Optional AI rewriting

Under **General options**, configure **Rewrite announcements with AI** and
**Default AI conversation agent**, and **Backup AI conversation agent**.
Rewriting defaults to off for backward compatibility. The preselected **Home Assistant default** option follows the
default conversation agent used by `conversation.process`. You can choose any
currently discovered conversation agent instead. The backup dropdown defaults
to **Original announcement (no backup AI)**, or can select Home Assistant's
default or another configured conversation agent.

When enabled, the agent rephrases spoken and visual text to sound more natural
and variable. The prompt asks it to preserve the original information and not
to control devices or execute actions; the integration checks the response
format, but cannot guarantee that every paraphrase is factually equivalent.
AI cannot change the announcement level, recipients,
room routing, title or notification metadata. If an agent is offline, times
out, rejects the request, or returns an invalid response, Announcement Hub
tries the optional backup agent once. If that fails too (or if no backup agent
is selected), the original text is delivered unchanged. Unsafe-looking responses,
including changed numerical readings and obvious AI refusals, are also rejected.
AI runs only before an announcement enters the persistent queue. Each enabled
AI agent has a 12-second timeout, so a primary plus backup can take up to
24 seconds before enqueueing. Disable AI per action for time-critical alerts.

To override AI for an individual announcement:

```yaml
action: notify.announcement_hub
data:
  text_tts: "The washing machine has finished."
  text_notify: "Washing machine finished"
  use_ai: true
  ai_agent: conversation.my_ai_assistant
```

- Omit `use_ai` to inherit the integration setting; set `use_ai: false` to
  bypass AI even when globally enabled.
- Omit `ai_agent` to inherit the integration agent. The action editor provides
  Home Assistant's conversation-agent selector.
- The backup agent is configured globally. If both agents are unavailable or
  return invalid text, announcements still use their exact original wording.
- Both `notify.announcement_hub` and the legacy `announcement_hub.send`
  support the per-announcement overrides.

**Note:** Home Assistant's built-in intent-only agent generally cannot
rewrite arbitrary text. For natural variation, select an LLM-backed
conversation agent. Its home-control permissions also apply when processing
rewriting prompts; use an agent with only the capabilities you intend.

### Output behavior

When `output` is omitted:

```text
all configured matching outputs enabled for that call are candidates
→ currently available outputs are used immediately
→ unavailable or failed outputs are retried for the configured timeout
→ remaining outputs are recorded with their final timeout/error
```

When one or more areas are supplied, area-bound outputs are filtered to those
rooms. With `occupied_only: true`, the final room targets are the intersection
of the explicit areas and the currently occupied areas. With
`occupied_only: false`, the explicit areas are authoritative. General/global
outputs continue to match according to their configured policy.

For TTS, selected targets are never dropped merely because they are currently
`unavailable` or `unknown`. They remain pending and are retried until the
configured output-availability timeout expires.

### Specific outputs or integrations

The optional `service` field narrows a non-critical job. It accepts:

```text
mobile_app                    # selected outputs from an integration
nfandroidtv                   # selected outputs from an integration
entry:<config_entry_id>       # selected outputs from one entry
entity:notify.living_room_tv  # one visual output
entity:tts.piper              # one TTS engine
service:notify.some_service   # one legacy notification action
tts                           # configured server TTS path
notify                        # configured visual notification outputs
snapcast                      # server TTS through configured Snapcast outputs
companion_tts                 # configured Companion App TTS outputs
all                           # all configured outputs
```

Plain entity IDs such as `tts.piper` and `notify.some_entity` are also accepted.
Companion App TTS is enabled only by `companion_tts: true`, the dedicated
`companion_tts`/`all` service alias, or `critical`; selecting a normal
`mobile_app` visual output does not make the phone speak. For `critical`, an
explicit restriction is ignored and every configured output matching the
requested area is attempted.

### Companion App TTS

First select eligible Android Companion App entries/entities under
**Companion App TTS outputs**. Ordinary calls do not use them unless the action
opts in; `critical` always uses every configured matching output.

```yaml
action: notify.announcement_hub
data:
  text_tts: "The garage door is still open."
  companion_tts: true
  level: warning
```

The existing explicit restriction also opts in:

```yaml
service:
  - companion_tts
```

Companion App push TTS has no reliable playback-finished state in Home
Assistant. Announcement Hub therefore keeps the queue locked for an estimated
duration based on the configured words-per-minute value before it advances to
the next audible output.

### Critical example

```yaml
action: notify.announcement_hub
data:
  text_tts: "Smoke detected in the kitchen."
  output:
    - kitchen
    - living_room
  level: critical
```

If only one text field exists on a critical job, its text is copied to the
missing audible or visual channel. One failed output does not prevent the
remaining outputs from being attempted.

### Action response

```yaml
- action: notify.announcement_hub
  data:
    text_tts: "Test announcement"
  response_variable: announcement_job
```

The job ID is available as:

```jinja2
{{ announcement_job.job_id }}
```

Visual action calls are serialized, but the notification provider controls how
long an on-screen overlay remains visible.

The response also reports the frozen TTS engines, visible outputs, Snapcast
clients, Companion App TTS entries, and whether TTS was suppressed by the level
threshold.

## Queue management

Cancel one job:

```yaml
action: announcement_hub.cancel
data:
  job_id: "JOB_ID"
```

Clear waiting jobs:

```yaml
action: announcement_hub.clear_queue
data:
  include_current: false
```

## Status and events

`sensor.announcement_hub_queue` reports the number of waiting jobs. Its
attributes contain the active, pending, and most recent job without exposing the
message text.

Events:

```text
announcement_hub_queued
announcement_hub_started
announcement_hub_channel_started
announcement_hub_channel_finished
announcement_hub_channel_failed
announcement_hub_finished
announcement_hub_failed
announcement_hub_cancelled
announcement_hub_queue_cleared
```

## Upgrade from 0.1

The config entry migrates automatically:

- former allowed/default TTS values become selected TTS engines;
- former allowed/default notification values become selected visual outputs;
- enabled Snapcast clients become selected Snapcast outputs;
- Companion App TTS devices remain ineligible until selected in setup, and
  ordinary calls still require per-action opt-in;
- the new TTS threshold defaults to `debug`, preserving audible behavior;
- the new availability wait defaults to 5 seconds.

Existing waiting queue records are migrated best-effort and retain their text,
area request, provider selection, and prepared TTS media-source IDs.

## Validation performed for 0.2.0

- Python source compiles under Python 3.13.
- JSON and YAML resources parse.
- 16 queue-model and resource-contract tests pass.
- The installer is tested against a temporary Home Assistant config directory,
  including replacement and backup behavior.
- Live behavior still needs the first test against the actual Home Assistant,
  MPD, Snapcast, Android TV, and Companion App entities in this installation.
