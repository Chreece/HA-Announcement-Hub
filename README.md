<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-Announcement-Hub/main/.github/assets/announcement-hub-banner.svg" alt="Announcement Hub for Home Assistant" width="100%">
</p>

<p align="center">
  <a href="https://github.com/Chreece/HA-Announcement-Hub/releases"><img alt="Latest version" src="https://img.shields.io/github/v/release/Chreece/HA-Announcement-Hub?display_name=tag&sort=semver"></a>
  <a href="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/validate.yml"><img alt="Python tests" src="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/validate.yml/badge.svg"></a>
  <a href="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/hacs.yml"><img alt="HACS validation" src="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/hacs.yml/badge.svg"></a>
  <a href="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/hassfest.yml"><img alt="Hassfest validation" src="https://github.com/Chreece/HA-Announcement-Hub/actions/workflows/hassfest.yml/badge.svg"></a>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=Chreece&repository=HA-Announcement-Hub&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open Announcement Hub in HACS">
  </a>
</p>

# Announcement Hub for Home Assistant

**One announcement service. The right room, the right device, and the right channel.**

Announcement Hub is a Home Assistant integration for audible TTS, room-aware
Snapcast playback, Android Companion App speech, TV overlays, visual notifications,
and optional AI-assisted wording. It owns message routing, prioritizes the
requested room, and maintains a persistent delivery queue so an unavailable
output does not silently discard a message.

It uses your configured Home Assistant entities and services; it does not
create an external daemon, separate credentials, an MPD installation, a
Snapserver installation, or new physical notification devices.

## What it can do

| Capability | Behavior |
| --- | --- |
| Unified announcement action | `notify.announcement_hub` with `text`, independent speech/visual variants, levels, areas, exact recipients and delivery-service filters |
| Room-first delivery | Requested area → other occupied areas → door-gated fallback area → General notification outputs |
| Smart visual/audio choice | Prefer visual delivery for low-severity messages in the requested room; use that room's speaker when visual delivery cannot work |
| Speech in alternate rooms | Prefer room-bound audio in occupied or permitted fallback rooms so a person can hear the announcement |
| Server TTS | One configured TTS engine with language, voice and provider-specific options |
| Snapcast | Route synchronized room clients, verify their mute states, isolate the chosen recipients and restore previous states |
| Direct room TTS | Speak on selected `media_player` entities assigned to Home Assistant areas |
| Android Companion App TTS | Opt-in push speech through `notify.mobile_app` using the Companion App's TTS payload |
| Visual notifications | Configured `notify` entities and legacy services, including mobile and Notifications for Android TV |
| TV-aware delivery | NFAndroidTV visual routing can check reliable media-player power observers instead of assuming an available notify service means the screen is on |
| Visual profiles | Long-message splitting, word-based display durations, title part numbering, TV overlay style and provider data |
| Tap navigation | Android Companion App `clickAction` or Apple Companion App `url`, from the shared `click_action` field |
| AI rewriting | Optional preferred Assist agent, another selected conversation agent, backup AI, independent speech/visual styles, and untouched-original fallback |
| Persistent queue | Original text is saved before AI starts; interrupted AI jobs survive Home Assistant restarts and do not block newer runnable announcements |
| Diagnostics | Queue sensor, per-job routing and AI results, channel outcomes and lifecycle events |

## Installation

### HACS

1. Open **HACS** in Home Assistant.
2. Add `https://github.com/Chreece/HA-Announcement-Hub` as a custom repository of type **Integration**, if it is not already listed.
3. Install **Announcement Hub**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration → Announcement Hub**.

The integration supports a single configuration entry. Ensure at least one
notification or speech output is configured during the setup wizard.

### Manual installation

Copy the repository's `custom_components/announcement_hub` directory into:

```text
/config/custom_components/announcement_hub
```

Restart Home Assistant and add the integration from **Devices & services**.
The repository also includes an optional `./install.sh` installer when working
from a local checkout. Home Assistant must still be restarted after installing
the component.

## Interface walkthrough

The following screen previews illustrate the integration's **English setup
fields and example selections**. They are documentation renderings, **not
captures from a live Home Assistant installation**. The exact theme, entities,
available fields and layout depend on your system.

### Choose a configuration section

The **Configure** and **Reconfigure** menus let you open just the section you
need. Saving a section preserves the other configured sections. **Edit all
settings (full wizard)** walks through the complete form.

![Illustrative Announcement Hub configuration menu](https://raw.githubusercontent.com/Chreece/HA-Announcement-Hub/main/.github/assets/screen-configure-menu.svg)

### Step 1 — Notification outputs and room scope

![Illustrative notification device selection and severity fields](https://raw.githubusercontent.com/Chreece/HA-Announcement-Hub/main/.github/assets/screen-notifications.svg)

On **1. Notification outputs**, choose:

1. **Notification devices** — the `notify` entities allowed to show messages.
   On first setup, discovered devices are selected automatically; deselect any
   device you do not want.
2. **Room-based notification devices** — devices physically located in a
   Home Assistant area, such as a television. Give these devices the correct
   area in Home Assistant first.
3. **Minimum Info / Success**, **Minimum Warning**, **Minimum Error** and
   **Critical only** — choose each device's minimum notification level.
   Devices not assigned to a higher minimum accept Debug and above.

A **Room** device participates only in permitted room stages. A **General**
device (for example, a phone or tablet not assigned to a fixed room) is
considered after the room stages. A General device must not be treated as a
speaker physically located in an unrelated room.

Home Assistant entity and device registry areas determine the location of a
notification device. A room-scoped device without a resolvable area cannot
correctly participate in room routing. An explicitly configured legacy
`service:notify.some_service` has no guaranteed room identity and is treated
as General.

### Step 2 — TTS engines and audible devices

![Illustrative TTS engine, Snapcast and Companion App configuration](https://raw.githubusercontent.com/Chreece/HA-Announcement-Hub/main/.github/assets/screen-tts.svg)

Under **2. TTS outputs**, configure the audio paths you actually use:

- **TTS engine**: one Home Assistant TTS engine, such as Piper. The default
  engine is offered when discoverable.
- **TTS language** and **TTS voice**: select values supported by that engine.
  A voice field is shown when the engine supports voice selection; engines
  that cannot enumerate voices may offer manual entry.
- **TTS engine options**: optional provider-specific values.
- **Direct TTS players per room**: enabled media players assigned to an area.
  The shared Snapcast player must not also be selected as a direct room player.
- **Snapcast room clients**: selected, area-assigned Snapcast output clients.
- **Shared media player driving Snapcast**: the central player that feeds the
  announcement source, for example `media_player.mpd`. An active engine and
  shared player are required when using Snapcast.
- **Use TTS from level**: the normal severity preference for speech.
  See [Room-first channel selection](#room-first-channel-selection).
- **Pre-generate and cache speech**: controls TTS caching. Speech prefetch
  and file-cache persistence are separate mechanisms.
- **Companion App TTS devices**: the eligible Android Companion App devices
  that may speak when explicitly requested by an action.
- **Companion App audio stream**: Default, music, alarm, or alarm-max stream.
- **Companion TTS speech estimate**: words per minute used for approximate
  queue timing because Android push TTS has no dependable playback-finished
  acknowledgement.

**Companion App TTS is independent of server TTS.** Android devices must be
registered in Home Assistant, able to receive mobile notifications, and
selected in this page. Selecting a device only makes it eligible; an ordinary
action must still opt in.

### Step 3 — Provider-specific output profiles

![Illustrative Android TV notification profile](https://raw.githubusercontent.com/Chreece/HA-Announcement-Hub/main/.github/assets/screen-profiles.svg)

A profile is offered for each selected notification integration; additional
Snapcast-specific controls are offered when appropriate.

Visual profiles can configure maximum characters per message part, reading
speed, minimum and maximum display time, reading-time buffer, spacing between
parts, title part numbering, and additional provider data. Text is divided at
natural sentence or word boundaries where possible.

Estimated reading time is:

```text
display seconds = clamp(words / reading_words_per_minute × 60 + buffer,
                        minimum_display_seconds, maximum_display_seconds)
```

For **Notifications for Android TV / Fire TV**, you can configure position,
font size, background color, transparency and interactive overlay behavior.
The integration uses the available advanced legacy notification action or
the provider's active runtime client to preserve the supported appearance
settings.

For **Companion App visual notifications**, multipart messages can use a
stable replacement tag so the next part replaces the previous one instead
of creating a notification stack.

For **Snapcast**, configure the announcement source, whether only clients
already on that source are managed, route-settle delay, route verification
timeout and restoration of original mute states. The shared TTS player and
source must already be working in Home Assistant and Snapserver.

### Step 4 — General settings, presence, queue and AI

![Illustrative room-presence, fallback and AI settings](https://raw.githubusercontent.com/Chreece/HA-Announcement-Hub/main/.github/assets/screen-general.svg)

The **4. General options** page includes:

| Setting | What it controls |
| --- | --- |
| Default notification title | Title used when the action supplies none |
| Rewrite announcements with AI | Optional AI processing for ordinary announcements |
| Default AI conversation agent | Preferred Assist pipeline or a specific conversation agent |
| Backup AI conversation agent | Alternate agent, or original message without a second AI attempt |
| Room-presence entity | A sensor reporting currently occupied Home Assistant rooms |
| Occupied rooms value | Sensor state or attribute containing room names / area IDs |
| Fallback room | An alternate area eligible after the requested and occupied areas |
| Require an open occupied-room door for fallback | Door rule that must pass before using the configured alternate room |
| Door sensor label filter | Optional label to restrict which door sensors count |
| Notification/TTS order | Which channel begins first; delivery can still overlap |
| Maximum queued announcements | Capacity limit for new jobs |
| Unavailable-output wait | Per-stage availability grace before trying another permitted route |
| Audio idle wait | Maximum wait for a busy shared playback path |
| Playback start timeout | Maximum wait for TTS playback to begin |
| Maximum TTS playback time | Upper bound for one audible playback |
| Post-playback gap | Optional delay between audible playback rounds |
| Critical notification data | Provider data merged for Critical visual messages |

For presence, a sensor may expose a list such as:

```yaml
state: "occupied"
attributes:
  rooms:
    - Kitchen
    - Living Room
```

Select the sensor and set **Occupied rooms value** to `rooms`. The integration
can also interpret area IDs and supported string/mapping representations.
Unknown or missing room values do not authorize a broadcast to unrelated
room devices.

## How delivery works

### Room routing order

For a call with `area` specifying a preferred room, Announcement Hub
considers the following stages **one at a time**:

```text
Requested room(s)
    ↓ if no usable authorized output
Other currently occupied rooms (when occupied_only is true)
    ↓ if no usable authorized output
Configured alternate room (only if the door rule permits)
    ↓ if no usable authorized output
General/non-room notification outputs
```

- The **requested room** is attempted even if it is not currently listed as
  occupied.
- The **occupied-room stage** uses the configured occupancy sensor; it does
  not guess where people are.
- The **alternate-room stage** observes the configured open-door condition.
  When enabled, the relevant door sensor must belong to the originally
  targeted area, have device class `door`, and have state `on`. An optional
  label filter narrows which doors qualify.
- The **General stage** can reach configured General outputs without treating
  them as physical endpoints in a specific room.
- Room-bound devices in other, unrelated areas are not silently selected.
- If a stage has no eligible candidates it is skipped immediately. A stage
  with candidates that are currently unavailable receives its configured
  availability grace before escalation.
- A successful output stops escalation to later stages. A failed provider
  can trigger another eligible channel in the same room first.

A `service` selector is **only a delivery-channel filter**. Use
`integration`, `device` and `entity` to choose exact recipients;
`area` chooses preferred room devices and permitted room fallback. A
service-only call with no recipient or room is rejected rather than
broadcasting to all configured devices.

### Room-first channel selection

The notification level and TTS minimum are **not the same policy**.

| Situation | Channel selected |
| --- | --- |
| Low-severity message; an eligible visual device works in requested room | Prefer the room's visual notification; keep soft-threshold TTS silent |
| Room visual output missing, unavailable or unsuitable | Try that room's authorized TTS/Snapcast output even at Info/Success |
| A selected visual provider fails | Try suitable audio in the same room before escalating |
| Announcement moves to an occupied room | Prefer that room's available audio so the person can hear it |
| Announcement moves to the configured alternate room | Prefer audio when the door rule allows the route |
| No permitted room route works | Consider the configured General outputs |
| TTS preference is `Never` | No non-Critical speech fallback; the explicit hard opt-out is respected |

Notification minimum levels still control which visual outputs may be used.
All speech fallback remains limited to **configured and authorized physical
outputs**, with the same strict service restrictions as the original action.

Severity order:

```text
debug < info / success < warning < error < critical
```

Critical never expands a selected integration, device, entity or channel
restriction. Without a room, it cannot invent a room speaker.

### Snapcast routing and playback

When server TTS is selected, Announcement Hub resolves the allowed physical
Snapcast clients from their Home Assistant areas. The shared media player
provides the audio; it is not itself permission to speak in every room.

For a spoken round, Hub waits for the managed playback path to become idle,
captures the relevant client mute states, unmutes the selected recipients,
mutes other managed clients as needed, verifies the actual route, plays the
prepared TTS item and restores the original states.

Unavailable selected clients receive the configured availability grace.
For consecutive announcements using the same verified route, Hub may reuse
that route to avoid audible gaps, then restore the original mute states when
the chain ends or the route changes. A short output-tail allowance prevents
the end of speech being cut off.

### Physical availability and delivery acknowledgement

For Notifications for Android TV, Hub can associate the notify endpoint
with reliable media-player observers through the same device-registry
device or an exact configured host identity. If **all** reliable observers
report off, standby or unavailable, the TV visual output is not considered
ready. Names and fuzzy matching are not used to invent an association.

**A successful Home Assistant notify action is not proof that a device
displayed, played, or was seen receiving the message.** Companion push,
external notification providers, device power policies and local notification
permissions can still prevent user-visible presentation.

## Send announcements

Open **Developer tools → Actions**, select `notify.announcement_hub` and
supply the message and optional targets. The examples below work equally well
in automations or scripts.

The legacy alias `announcement_hub.send` remains available for existing
automations.

### Send an ordinary announcement

```yaml
action: notify.announcement_hub
data:
  text: "The washing machine has finished."
  title: "Laundry"
  level: info
```

`text` fills both speech and written-notification channels unless
`text_tts` or `text_notify` overrides that channel. If `text` is omitted,
one or both optional channel texts can be supplied. A speech-only message
never becomes visual and a visual-only message never becomes speech.

### Prefer a specific room

```yaml
action: notify.announcement_hub
data:
  text: "Please check the window."
  level: info
  area:
    - Kitchen
  occupied_only: true
```

`area` accepts Home Assistant area names or IDs. It indicates a **preferred
room**, not a hard device allowlist. If you intentionally want to skip the
other occupied rooms, set `occupied_only: false`; the door-gated alternate
room and General outputs can still be considered.

### Write different visual and spoken texts

```yaml
action: notify.announcement_hub
data:
  text: "The entrance door is open."
  text_tts: "Please close the entrance door."
  text_notify: "🚪 Entrance door open"
  title: "Home"
  level: warning
```

A text channel with no authorized destination is not sent simply because
the text exists.

### Speak through an Android Companion App

![Illustrative Companion App TTS action example](https://raw.githubusercontent.com/Chreece/HA-Announcement-Hub/main/.github/assets/screen-companion-action.svg)

Select your Android device under **2. TTS outputs → Companion App TTS
devices**, then call:

```yaml
action: notify.announcement_hub
data:
  text_tts: "The garage door is still open."
  level: warning
  companion_tts: true
```

To restrict this announcement to Companion App **speech only**:

```yaml
action: notify.announcement_hub
data:
  text_tts: "Your timer has finished."
  integration:
    - mobile_app
  service:
    - companion_tts
```

The explicit `companion_tts` service selector chooses the speech channel,
while `integration: [mobile_app]` chooses the configured Android Companion
App recipients. The additional `companion_tts: true` boolean is not needed.
`service` alone is not a recipient and must be combined with an `area`,
`integration`, `device` or `entity` target.

**Important:** `integration: [mobile_app]` chooses the configured
mobile devices, while `service: [notification]` requests written delivery
and `service: [companion_tts]` requests spoken Companion App delivery.
Combining these selectors sends only the selected channel on the selected
mobile devices. `service` never accepts an integration name.

For a single selected Android Companion App entry, a configured entry may
also be targeted by its `entry:<config_entry_id>` selector together with
`companion_tts: true`, while normal visual entries remain distinct. The
Companion App must be able to receive notification pushes and play TTS.
Audio-stream and background behavior depend on Android permissions and
device settings.

Internally, Hub uses the Home Assistant `notify.mobile_app` action with a
Companion TTS payload (`message: TTS` and `data.tts_text`). It cannot
reliably determine when the phone has finished speaking, so it estimates
the hold time using the configured speaking rate.

### Send only a visual Companion App notification with a tap destination

```yaml
action: notify.announcement_hub
data:
  text_notify: "Movement detected at the front door."
  title: "Doorbell"
  integration:
    - mobile_app
  service:
    - notification
  click_action: /lovelace/cameras
  level: warning
```

For Companion App visual notifications, `click_action` maps to Android
`data.clickAction` or Apple `data.url`, and overrides conflicting values
in `notify_data`. Supported examples include dashboard paths, HTTPS URLs,
`app://` links and `entityId:light.some_light`. The user taps a notification
to navigate; Hub does not create action buttons.

### Send only to Notifications for Android TV

```yaml
action: notify.announcement_hub
data:
  text_notify: "The dryer is finished."
  title: "Laundry"
  level: info
  integration:
    - nfandroidtv
  service:
    - notification
```

Styling comes from the provider's saved output profile.

### Send only to configured Snapcast speakers

```yaml
action: notify.announcement_hub
data:
  text_tts: "Dinner is ready."
  level: warning
  area:
    - Kitchen
  service:
    - snapcast
```

The requested room must have a configured, eligible Snapcast client with a
working shared TTS player. The service restriction prevents fallback to an
unrequested provider.

### Critical announcement

```yaml
action: notify.announcement_hub
data:
  text: "Smoke detected. Check the kitchen."
  level: critical
```

Critical overrides the soft TTS minimum but never authorizes unrelated
recipients or unrequested services. Without an area or explicit physical
recipient, Hub does not infer a room's Snapcast speakers.

### Combine areas, integrations, exact devices and services

Announcement Hub distinguishes **recipients** from **delivery channels**:

| Field | Meaning | Automatic room fallback |
| --- | --- | --- |
| `area` | Preferred Home Assistant rooms. Hub selects configured room devices and uses occupied / permitted fallback areas when needed | Yes |
| `integration` | All configured output devices belonging to the named integration, such as `mobile_app` or `nfandroidtv` | No unrelated integration |
| `device` | Only configured outputs on those exact Home Assistant devices | No other devices |
| `entity` | Only the specified `notify.*` or `media_player.*` entities | No other entities |
| `service` | Channel filter: `notification` (written), `tts` (spoken), `snapcast`, `companion_tts`, or `all` | Never adds recipients |

`integration`, `device`, and `entity` form a **union** of explicitly
selected recipients. When combined with `area`, Hub creates two independently
tracked queue jobs: one for the preferred-room route and one for the exact
recipients. The action response includes `related_job_ids` for the second
job, and cancelling the returned group ID cancels its waiting related job.
When both legs choose the same physical endpoint, Hub records successful
receipts for the shared group and suppresses a second send to that endpoint,
without incorrectly treating the requested room as empty.

**Only one entity:**

```yaml
action: notify.announcement_hub
data:
  entity:
    - notify.living_room_tv
  service:
    - notification
  text_notify: "The dishwasher has finished."
```

This does not activate Snapcast, Companion App TTS, or other devices.

**All configured endpoints of one integration:**

```yaml
action: notify.announcement_hub
data:
  integration:
    - nfandroidtv
  service:
    - notification
  text: "The washing machine has finished."
```

**Both a room route and an additional exact recipient:**

```yaml
action: notify.announcement_hub
data:
  area:
    - Kitchen
  entity:
    - notify.mobile_phone
  service:
    - notification
  text_notify: "Please check the kitchen window."
```

The phone is notified as an explicit recipient, and the Kitchen route follows
its own configured room fallback. Neither leg silently substitutes an
unselected device for an exact recipient.

**TTS through the selected targets:**

```yaml
action: notify.announcement_hub
data:
  area:
    - Living Room
  device:
    - YOUR_HOME_ASSISTANT_DEVICE_ID
  service:
    - tts
  text_tts: "The timer has ended."
```

The `service` filter never creates a speaker on its own. A matching,
configured, authorized TTS-capable physical output must exist.

**Channel-specific text:** `text_tts` goes only to speech,
`text_notify` goes only to written notifications. Shared `text`
fills both channels unless individually overridden. A missing channel is
never manufactured, even at Critical level or after an output failure.

`output` remains recognized internally for existing YAML compatibility,
but the action editor exposes only `area`. New calls should use `area`.

## AI rewriting

In **4. General options**, switch on **Rewrite announcements with AI** and
select a default conversation agent. **Home Assistant default** resolves the
conversation engine from the current *preferred Assist pipeline*; the
built-in intent-only agent is not considered a generative rewrite model.
Alternatively, select a specific Home Assistant `conversation.*` agent.
A separate backup may be configured, or left at **Original announcement
(no backup AI)**.

When AI is enabled, Hub asks for channel-specific text in one structured
response: plain speech without markup or emoji and independently styled
visual text. The same facts, measurements, language, names and severity
must remain intact. Invalid, action-producing or unsafe output is rejected.

**The original announcement is persisted before any AI request starts.**
AI runs in an integration-owned task while the queue can process other
runnable jobs. The individual message waits for its rewrite to finish, then
uses the rewritten text or the original if AI fails. Interrupted
preprocessing can be retried from the saved original after Home Assistant
restarts.

Hub does **not** cancel an otherwise active AI request after a fixed
elapsed time. At 60 seconds it can log that the request is still pending.
The Home Assistant conversation service does not provide a universal
generation-progress endpoint. A provider may still time out or fail on
its own. A genuinely unresponsive provider can leave that individual job
pending; later ready jobs are not blocked.

Per-call AI override:

```yaml
action: notify.announcement_hub
data:
  text: "The robot vacuum has finished cleaning."
  use_ai: true
  ai_agent: conversation.my_assistant
```

Use `use_ai: false` for deterministic or time-critical announcements where
you do not want to wait for rewriting. Omitting `use_ai` inherits the
integration setting.

## Queue, jobs and diagnostics

### Request a job ID

```yaml
- action: notify.announcement_hub
  data:
    text: "The garden lights are on."
    level: info
  response_variable: announcement_job
```

Use `{{ announcement_job.job_id }}` in a script or automation. The
immediate action response means **accepted into the queue**, not
**played or visibly received**. For AI-enabled calls, the immediate
response usually shows `ai.status: pending`; the queue sensor later
exposes the final rewrite result.

`sensor.announcement_hub_queue` shows the number of waiting jobs. Its
attributes include `current`, `pending`, `last`, `worker_alive`,
`prefetching` and `ai_processing` where applicable. Each job includes
route stage/history, selected channels, timing, safe AI diagnostics,
provider errors and successful channel names without disclosing its
raw message text.

Route stages are `primary`, `occupied`, `fallback` and `general`.
An initial response at `primary` with no selected targets does **not**
mean routing failed: the worker may choose and record the next stage
after queue acceptance.

`successful_channels` means the underlying Home Assistant service call
returned successfully. It **does not guarantee device-side reception**.
If you need receipt guarantees, use a recipient/provider that exposes
acknowledgements beyond the Home Assistant notification action.

### Cancel or clear announcements

Cancel one waiting or active job:

```yaml
action: announcement_hub.cancel
data:
  job_id: "JOB_ID"
```

Clear the waiting queue:

```yaml
action: announcement_hub.clear_queue
data:
  include_current: false
```

Set `include_current: true` to request cancellation of the active job
as well.

An accepted announcement with no currently usable output remains
persisted and may be retried as availability, room occupancy and
configuration permit. Unavailable jobs do not prevent newer runnable
messages from progressing. An explicit integration/device/entity selection
is never widened to another recipient. A mixed area-plus-explicit call
tracks the area and explicit-recipient jobs independently.

### Home Assistant events

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

These events can be used in automations and diagnostics to observe
enqueueing, channel attempts, completed service calls, failures and
explicit cancellations.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No Companion App speech | Android device selected under Companion TTS outputs; use `companion_tts: true` or `service: [companion_tts]`; check notification and audio permissions |
| Mobile App notification does not speak | Use `integration: [mobile_app]` with `service: [tts]` or `service: [companion_tts]` and configure Android Companion TTS recipients |
| An Info announcement goes to a General device | Check the requested room's visual and audio eligibility, TTS engine, actual physical player state, area assignment, room grace and routing history |
| TV notify entity seems available but screen is off | Check the linked `media_player` observer and the TV's real power state |
| Snapcast produces no sound | Check the configured TTS engine, shared player, announcement source, area-assigned clients, client mute and playback readiness |
| Room fallback is skipped | Check the occupancy sensor values and whether the configured source-area door sensor is open and passes the optional label filter |
| AI returns the original message | Inspect the job's `ai.attempts` and `ai.failure_reason`; actual provider errors, invalid JSON or integrity checks can trigger fallback |
| AI takes a long time | Check the underlying conversation agent's load/generation time; Hub preserves the original job and does not impose an arbitrary generation cutoff |
| Job remains pending | Inspect the queue sensor, `routing_history`, availability grace, restrictions and `ai_processing` |
| A notification is marked successful but cannot be seen | The service call succeeded; check the recipient app, device connectivity, display rules, notification permissions, sound settings and any provider-side acknowledgement |

For debugging, use the **Announcement Hub queue sensor** and Home Assistant
logs for `custom_components.announcement_hub`. The action response is an
initial queue snapshot; the persisted job and its lifecycle events show
what happened during actual processing.

## Safety and interoperability

- Announcement Hub never broadens an explicit service or device allowlist.
- It respects configured severity thresholds, area scopes, occupancy, the
  alternate-room door rule, and the hard TTS `Never` preference (except
  Critical).
- Conversation agents may have Home Assistant tool permissions even though
  Hub asks only for text. Use an agent with the smallest permissions required
  and review any third-party provider's data handling.
- The integration runs through supported Home Assistant TTS, media-player,
  notify, conversation and Snapcast interfaces. Physical device readiness
  depends on each underlying provider and its integration.
- Provider-specific visual payloads and automatic source routing cannot
  guarantee that every device has displayed or audibly played a message.

<p align="center">
  <a href="https://ko-fi.com/chreece">
    <img src="https://raw.githubusercontent.com/Chreece/pir2ha/main/.github/ko-fi-banner.svg" alt="Support the project" width="600">
  </a>
</p>
