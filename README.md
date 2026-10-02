# Announcement Hub for Home Assistant

Announcement Hub is a Home Assistant-native, persistent queue for spoken
announcements and visible notifications. It selects outputs by integration,
config entry, entity, service, and Home Assistant area, then executes every job
without overlapping the next one.

It does **not** run an external daemon, request a Home Assistant token, create
helpers, edit automations, or change MPD/Snapserver configuration.

## Main behavior

- Adds `announcement_hub.send`, `announcement_hub.cancel`, and
  `announcement_hub.clear_queue`.
- Accepts `text_tts`, `text_notify`, or both; at least one is required.
- Persists waiting jobs across Home Assistant restarts.
- Freezes each job's selected outputs, area bindings, player, TTS settings, and
  notification data when the job enters the queue.
- Pre-generates later server TTS while an earlier announcement is playing.
- Serializes jobs and audible outputs so they do not overlap.
- Uses available outputs immediately and gives unavailable or transiently
  failing outputs one configurable retry window before recording a timeout.
- Supports visible notifications through modern `notify.*` entities and legacy
  `notify.<service>` actions.
- Supports Android Companion App push TTS as an optional audible output. Eligible
  devices are selected in setup, while ordinary action calls opt in with
  `companion_tts: true`; the action option defaults to `false`.
- Routes selected Snapcast clients by Home Assistant area, verifies the mute
  state before speech, and restores every previous mute state afterward.
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

- one or more TTS engines, such as the Piper integration or `tts.piper`;
- the shared server TTS media player, normally `media_player.mpd`;
- the minimum level that is allowed to use audible TTS;
- cache/prefetch, language, and engine options;
- Companion App audio stream and estimated words per minute.

Multiple server TTS engines are a fallback chain. The first engine that
successfully starts playback is used; the same message is not intentionally
spoken once per voice.

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
- the gap between audible outputs.

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

## Main action

```yaml
action: announcement_hub.send
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

### Output behavior

When `output` is omitted:

```text
all configured matching outputs enabled for that call are candidates
→ currently available outputs are used immediately
→ unavailable or failed outputs are retried for the configured timeout
→ remaining outputs are recorded with their final timeout/error
```

When one or more areas are supplied, area-bound outputs are filtered to those
areas. Global outputs, such as a manually entered legacy notification service,
continue to match because Home Assistant provides no room binding for them.

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
action: announcement_hub.send
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
action: announcement_hub.send
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
- action: announcement_hub.send
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
