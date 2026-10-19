<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-Announcement-Hub/main/.github/assets/announcement-hub-banner.svg" alt="Announcement Hub for Home Assistant" width="100%">
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
- Accepts a primary `text` with optional spoken `text_tts` and visual
  `text_notify` overrides. Legacy channel-only actions remain supported.
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

## Direct navigation when reconfiguring

The integration's **Reconfigure** action opens a menu rather than restarting
the four-step first-time setup. **Configure** opens the same menu:

- **Notification outputs & rooms** — devices, room scope and levels.
- **TTS engines & devices** — engines, language, voices and physical players.
- **Provider-specific profiles** — notification timing, appearance and Snapcast.
- **General, presence & AI** — AI/backup agents, room fallback and queue settings.
- **Edit all settings** — keep the full original editor when you need it.

Choosing one section jumps directly to its form and **saves immediately after
that section is completed**, without forcing the remaining pages. Previously
saved choices and settings outside that section are preserved. First-time
installation still uses the guided setup wizard.
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

Without an explicit `service` or `output` selector, `critical` tries
every configured matching output and remains audible when a TTS path exists.
With explicit targets, Critical preserves only those targets, even if that
means visual notifications with **no TTS**.

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

## Occupancy-aware routing and durable room fallback

Announcement Hub is responsible for routing announcements from integrations
such as Air Quality Advisor. The caller passes the original message and the
actual Home Assistant room name (for example \`output: ["Küche"]\`). Announcement
Hub resolves the name into an area ID; the caller must not work out fallback
targets or override output settings.

When the action requests a room or uses the configured occupancy sensor,
Announcement Hub tries the following priority tiers **one at a time**:

1. **Explicit rooms first:** physical notification/TTS/Snapcast outputs
   belonging to the named rooms, whether or not occupancy currently detects
   someone there. Only outputs that accept this severity are eligible.
2. **Occupied rooms next:** if \`occupied_only\` is enabled and an occupancy
   source is configured, try other currently occupied rooms.
3. **Door-gated fallback room:** use the configured fallback area only if
   the original requested/occupied room has an eligible door sensor in state
   \`on\` (open), or the door check has been explicitly disabled.
4. **General visual and other non-room outputs:** after room routes are
   exhausted, try only outputs configured with General scope. Never target a
   room-bound device in an unrelated room.

Each tier is checked against the actual configured outputs and its severity
thresholds. If there is no matching device, move immediately to the next tier.
If matching devices are registered but \`unavailable\`, \`unknown\`, or otherwise
unready, retain that tier for **Output availability timeout** before advancing.
If some selected devices succeed, the announcement is delivered there; there
is no need to broadcast it to later tiers.

**Info-level window-opening alerts:** when Piper/TTS starts at Warning, it
remains muted for Info. Announcement Hub first seeks a visual notification
configured for Info in the requested room; otherwise it considers occupied
rooms, the permitted fallback room, and General notifications. It never turns
an Info announcement into unrequested TTS or bypasses the configured minimum
notification severity.

**No silent expiry:** if all eligible outputs are unavailable (or none are
configured yet), the announcement stays queued and persisted. A newer
runnable announcement can proceed without waiting behind it. The pending
announcement retries permitted room tiers and General outputs as availability
or configuration changes, including after Home Assistant restarts. It will
finish only after delivery, explicit cancellation, or an explicit queue clear.
Normal queue capacity limits still apply to new submissions.

An explicit \`service\` restriction (provider, entity or config entry) remains
a hard allowlist through every fallback tier. For example, \`service:
[mobile_app]\` never turns into Piper/Snapcast or a different notify provider.
With **\`occupied_only: false\`**, the preferred room is still attempted but
the occupancy tier is skipped. Without a room preference or occupancy routing,
the existing automatic level policy remains in use.

The send action and the queue diagnostic sensor expose \`routing_mode\`,
\`routing_stage\`, \`preferred_areas\` and recent \`routing_history\`, allowing
the real output choice and each grace-period escalation to be inspected.

## Main action

```yaml
action: notify.announcement_hub
data:
  text: "Το πλυντήριο ολοκλήρωσε το πρόγραμμα."
  text_notify: "Το πλυντήριο τελείωσε."  # optional visual override
  output:
    - living_room
    - kitchen
  level: info
```

The call returns as soon as the job has been accepted. It does not wait for the
queued playback to finish.

### Primary text and optional channel-specific variants

Use **`text`** as the main message when creating a new announcement. It is
the required primary field in the action editor; the two overrides are optional.
Announcement Hub resolves the inputs **before** applying AI, severity thresholds,
output restrictions, room selection, and queue persistence:

| Supplied fields | Spoken (TTS) source | Visual notification source |
| --- | --- | --- |
| `text` only | `text` | `text` |
| `text` + `text_tts` | `text_tts` | `text` |
| `text` + `text_notify` | `text` | `text_notify` |
| All three | `text_tts` | `text_notify` |

Leave an override empty to inherit the common `text` value. Actual channels
still depend on your routing, level, TTS threshold and explicit `service` or
`output` targets. For example, `service: [mobile_app]` at Critical remains
**visual-only**, even with a common `text`.

For backwards compatibility, existing YAML automations using only
`text_tts`, only `text_notify`, or both **continue to work unchanged**.
If `text` is omitted, the old channel-specific behavior is preserved. A call
with no non-empty text in any field is rejected.

```yaml
action: notify.announcement_hub
data:
  text: "Η πόρτα της εισόδου είναι ανοιχτή."
  text_tts: "Η εξώπορτα παραμένει ανοιχτή."
  text_notify: "🚪 **Η πόρτα της εισόδου είναι ανοιχτή.**"
  level: warning
```

### Optional AI rewriting

Under **General options**, configure **Rewrite announcements with AI** and
**Default AI conversation agent**, and **Backup AI conversation agent**.
Rewriting defaults to off for backward compatibility. The preselected
**Home Assistant default** option now follows the **conversation agent configured
in Home Assistant's preferred Assist pipeline**, not the intent-only agent
used by a bare `conversation.process` call. The dropdown shows the preferred
agent and resolves it fresh for every announcement, so changing the preferred
Assist pipeline automatically updates the AI used. You can select a specific
conversation agent instead. The backup dropdown defaults to **Original
announcement (no backup AI)** and can also choose the preferred Assist
pipeline or a specific alternative agent.

If the preferred Assist pipeline is unavailable or still uses
`conversation.home_assistant` (the built-in intent-only agent), Announcement Hub
does **not** send a rewriting prompt to it. Instead it tries the configured
backup AI, if any, then delivers the original announcement unchanged. This is
reported as `preferred_assist_pipeline_unavailable` or
`preferred_assist_agent_not_generative` in
`announcement_hub_result.ai.failure_reason`.

When enabled, the agent produces **two channel-specific versions** from the
resolved delivery plan in **one AI request**: 

- **Spoken (`text_tts`)** is short, natural speech with no emoji, emoticons,
  headings, Markdown, HTML, SSML, symbols or visual decoration. A final
  speech-cleaning pass removes harmless formatting and rejects complex markup.
- **Visual (`text_notify`)** is separately composed for readability, with
  optional appropriate emoji, brief emphasis, line breaks and simple styling.
  Rich formatting varies by notification provider; HTML/SSML is not requested.

Only planned output channels are rewritten. For example, a Critical alert
with only visual input still has a planned TTS channel, so AI returns a
speech-ready variant as well; an ordinary visual-only alert does not suddenly
start speaking. Both versions use the same source facts but are formatted
independently. The prompt asks it to preserve the original information and not
to control devices or execute actions; the integration checks the response
format, but cannot guarantee that every paraphrase is factually equivalent.
AI cannot change the announcement level, recipients,
room routing, title or notification metadata. If an agent is offline, times
out, rejects the request, or returns an invalid response, Announcement Hub
tries the optional backup agent once. If that fails too (or if no backup agent
is selected), the original text is delivered unchanged. Unsafe-looking responses,
including changed numerical readings and obvious AI refusals, are also rejected.
Announcement Hub first queues and persists the **original message** and
returns an acknowledgement immediately. AI rewriting then runs in a
separate, integration-owned background task while other ready announcements
continue through the delivery queue. A queued job is not dispatched until
its own AI processing completes; on a provider error, the original text is
used. If Home Assistant restarts during AI loading, the persisted original is
processed again rather than silently lost. Announcement Hub does not cancel
an in-flight Home Assistant conversation request after an arbitrary timeout. Cold-started local models and slower cloud
agents are allowed to finish; after 60 seconds the Hub logs that it is still
waiting, rather than treating the delay as a failure. This works with every
conversation agent because it awaits `conversation.process`, not a
provider-specific status endpoint. The standard Conversation API does not
expose universal model-loading, generation-progress or health details.
A real provider exception (including a timeout raised by the provider itself)
or invalid/unsafe AI result triggers the configured backup, then the original
announcement if necessary. Waiting for an unresponsive provider can delay
enqueueing indefinitely; disable AI per action for time-critical alerts.
The action response reports immediate queue acceptance and AI status
`pending` for requests that need rewriting. The queue diagnostic sensor
later exposes the final AI outcome and elapsed processing time; the initial
service response cannot contain the result of asynchronous rewriting.

To override AI for an individual announcement:

```yaml
action: notify.announcement_hub
data:
  text: "The washing machine has finished."
  text_notify: "🧺 Washing machine finished"  # optional
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
rewriting prompts; use an agent with only the capabilities you intend. If all
AI attempts fail, the previously established original-text fallback is kept
unchanged (rather than silently stripping the sender's input formatting).

### Verifying AI inheritance in an announcement

An omitted `use_ai` always inherits **Rewrite announcements with AI** from
the saved integration configuration. `use_ai: true` forces AI for that call;
`use_ai: false` disables it only for that call. An omitted `ai_agent` uses the
configured default agent.

The `notify.announcement_hub` response now includes an `ai` object when the
action requests a response. For example, keep your existing call and add
`response_variable: announcement_hub_result`. Inspect the
`announcement_hub_result.ai` object in the automation/script trace:

- `enabled` — whether AI was effectively enabled for this announcement.
- `source` — `integration` (inherited default) or `action` (explicit override).
- `status` — `rewritten`, `accepted_unchanged`, `fallback_original`,
  `disabled`, or `not_applicable` (no eligible message channel).
- `agent` / `agent_used` — requested and successful conversation agents.
- `attempted` / `attempts` — whether AI was called and each safe outcome.
- `failure_reason` — an error category such as `no_intent_match`, `timeout`,
  `invalid_response`, or `action_response_not_allowed`.

These diagnostics do not include the announcement content, AI prompt,
provider error messages, or secrets. They are also available in queue status
for the corresponding job.

**Important:** Home Assistant has two distinct defaults. Without an
`agent_id`, `conversation.process` uses the built-in intent-only agent;
Announcement Hub's **Home Assistant default** means the agent from the
preferred Assist pipeline. The resolved agent ID is included in the action's
`ai.agent`, `ai.agent_used` and attempt diagnostics, while
`ai.agent_selection` indicates `preferred_assist` or `explicit`.
If your preferred pipeline is still set to Home Assistant's built-in Assist,
configure it to use an LLM agent or select an explicit LLM agent in
Announcement Hub. A Home Assistant `action_done` conversation response is
accepted as a rewrite only when no home-control actions are reported; actual
action results are still rejected.
### Output behavior

When `output` is omitted:

```text
all configured matching outputs enabled for that call are candidates
→ currently available outputs are used immediately
→ unavailable or failed outputs are retried for the configured timeout
→ remaining outputs are recorded with their final timeout/error
```

When one or more `output` areas are supplied, those areas are the **first
priority**, not a permanent hard restriction. Other occupied rooms (when
`occupied_only` is enabled), the door-gated fallback room, and finally
general/non-room outputs are considered after the grace period. No unrelated
room is selected, and no unrequested service or TTS channel is added.

For TTS, selected targets are never dropped merely because they are currently
`unavailable` or `unknown`. They remain pending and are retried until the
configured output-availability timeout expires.

### Provider-targeted notifications and tap actions

The existing `service` action field restricts **which configured integrations
or devices** may be used at **every severity**, including Critical. That
allowlist stays strict; `output` gives a **preferred room** whose delivery
grace period is followed by controlled room/general fallback. Device selection
does not broaden to other providers. For example, target only Companion App visual
notifications with a tap-through dashboard link:

```yaml
action: notify.announcement_hub
data:
  text_notify: "Movement detected at the front door."
  title: "Doorbell"
  service:
    - mobile_app                 # or integration:mobile_app
  click_action: /lovelace/cameras
```

Or target only Notifications for Android TV/Fire TV:

```yaml
action: notify.announcement_hub
data:
  text_notify: "The washing machine has finished."
  service:
    - nfandroidtv
```

The optional `click_action` field is understood by **Companion App visual
notifications**. Announcement Hub maps the same value to the documented
`data.clickAction` key for Android and `data.url` for iOS/macOS. Supported
targets include a Home Assistant dashboard path (e.g. `/lovelace/cameras`),
a full HTTPS URL, `app://<package>`, and `entityId:<entity_id>`. On individual
Companion App devices, tapping the notification opens the target; it does
not add buttons or run Home Assistant actions.

The value is sent only to known Companion App notification routes, including
their advanced legacy notify actions and the `notify.mobile_app` group.
Unsupported integrations, direct/Companion TTS and the Android TV/Fire TV
overlay do not receive it. NFAndroidTV's `interrupt` option makes the
overlay interactive, but it does not support opening arbitrary URLs.
Existing `notify_data` remains available for more provider-specific options;
an explicitly supplied `click_action` takes precedence over
`notify_data.clickAction` and `notify_data.url` for Companion App outputs.
Notifications routed through generic `notify.send_message` cannot carry
provider-specific click metadata if no advanced mobile_app action is present.

**Provider restrictions stay strict:** A Critical notification directed only
to `mobile_app` cannot activate Piper, Snapcast or another notify provider.
`service` is a hard device/integration restriction; `output` is a preferred
room and may advance through the configured routing stages. Click actions
do not affect routing. Unrestricted Critical messages retain their original
automatic broadcast behavior.

The response includes `strict_targets: true` when a `service` restriction is
supplied. Preferred-room escalation instead reports
`routing_mode: room_fallback` and the current `routing_stage`. An explicitly
empty `service: []` or `output: []` remains invalid; omit the field to use
automatic routing.

### Specific outputs or integrations

The optional `service` field narrows every job, including Critical, to
only the configured integration/device types listed, even during area
fallback. Both `notify.announcement_hub` and `announcement_hub.send`
support this field:

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
When `service` is absent, Companion App TTS can be enabled with
`companion_tts: true` or an unrestricted Critical announcement. When
`service` is explicit, include `companion_tts` or `all` in that list to
allow push TTS. For example, `service: [mobile_app]` is **visual only** at
every level, even if `companion_tts: true` was supplied.

### Companion App TTS

First select eligible Android Companion App entries/entities under
**Companion App TTS outputs**. Ordinary calls do not use them unless the action
opts in; an unrestricted `critical` uses every configured matching output.
An explicitly targeted Critical announcement never enables unselected TTS.

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

If only one text field exists, it can supply the other channel **only when
that channel has been selected**. For example, a Critical announcement with
`service: [mobile_app]` remains visual-only even if `text_tts` is supplied.
A failed explicitly selected output does not trigger another provider or
room; it is retried only up to the configured availability timeout.

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
