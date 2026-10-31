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

## Languages and translations

Announcement Hub follows the selected **Home Assistant interface language**.
The dashboard announcement composer, its visual card editor, severity,
recipients, send/queue messages, and the integration's setup, options,
selectors and service-action names now have internationalized labels.

The shipped language files cover **Arabic, Chinese (Simplified/Traditional),
Czech, Dutch, English, French, German, Greek, Italian, Japanese, Korean,
Polish, Portuguese (Portugal/Brazil), Russian, Spanish, Swedish, Turkish,
and Ukrainian**. Every localized dashboard card now has the same complete
set of translated UI phrases, including prompts, validation errors, routing
help and queue feedback. Greek and German native integration menus have
comprehensive translations, including selectors. **All shipped languages now
translate the complete People and personal-destination setup, help text,
translation preferences, errors, and action field descriptions.** French and
Spanish also have expanded, reviewed labels for TTS, notification profiles,
queue and configuration errors. **Some older native configuration and service
descriptions in other languages still fall back to English** pending review. We do not
automatically replace these with unverified machine-translated text.

To switch the card language, change the language under your Home Assistant
user profile and refresh the dashboard; the card follows your selected
frontend language. Arabic layout uses right-to-left direction, and
language-specific entity IDs, exact service names, YAML keys and automation
payloads are never translated.

## Dashboard card

Announcement Hub includes its own modern **Lovelace Announcement Composer**
card. It is bundled with the HACS integration: no extra custom-card repository,
CDN, Node installation or separate JavaScript download is required.

### Add the card

1. Install Announcement Hub through HACS and restart Home Assistant. Confirm
   the integration is configured under **Settings → Devices & services**.
2. Edit any dashboard → **Add card** → search for **Announcement Hub**.
   The integration automatically registers its bundled JavaScript module in
   Lovelace's standard **storage-mode** resource list after Home Assistant
   finishes starting. No separate card installation or manual resource entry
   is necessary.
3. Select **Announcement Hub** to open the graphical editor. Alternatively,
   use this YAML:

```yaml
type: custom:announcement-hub-card
title: Household announcements
default_level: info
show_queue: true
show_ai: true
clear_after_send: false
```

If the card is not shown after refreshing the browser, check **Settings →
Dashboards → ⋮ → Resources**. For dashboards with YAML-managed resources or
installations where automatic registration is unavailable, add
`/announcement_hub/announcement-hub-card.js` as a **JavaScript module** and
refresh the browser. The integration serves the JS, CSS, and HTML files itself.
The card's exact type is `custom:announcement-hub-card`; its picker name is
**Announcement Hub**.

The visual editor controls the card heading, initial importance, queue
counter, AI controls and whether the message fields clear after a successful
send. **Message text, target selections and credentials are not stored in the
dashboard configuration.** Dashboard permissions continue to be enforced by
Home Assistant's authenticated service call.

### Using the composer

The card supports a primary announcement; optional `title`, `text_tts`
(spoken only), and `text_notify` (written only); Info, Success, Warning,
Error, Critical and Debug importance; optional AI rewriting or generation;
and an optional conversation-agent override. When AI generation is selected
with a blank title, Hub can produce a title of up to three words.

**Automatic routing** leaves recipient choice to the integration's configured
occupancy/fallback rules and selected default output lists. **Choose recipients**
uses live Home Assistant endpoints **independently of those output lists**:
areas, integrations, exact devices, and notify/media-player entities. The optional channel selector filters the
authorized deliveries to Written, Speech, Both, Snapcast or Companion App TTS.
A channel cannot be selected by itself: choose an area or explicit recipient
first. Device/integration selections do not authorize unrelated room speakers.
Automatic mode continues to obey the configured output allow-list. In manual
mode, a room selector authorizes the physical devices in that room; it never
implicitly selects other rooms or general mobile notifications.

The card discovers area and recipient names from Home Assistant registries
when allowed. Manual comma-separated IDs remain available if registry access
is restricted. In **Choose recipients**, the card passes `manual_targets: true`
and the integration discovers real eligible Home Assistant entities, including
those not selected in the Hub's automatic-output configuration. The selected
areas are kept to their physical outputs; their room leg cannot accidentally
escalate to a general-phone broadcast. Selected integrations intentionally
target **all their eligible devices**, and exact device/entity selections remain
strict. Unknown, disabled, unavailable or incompatible outputs are not
invented. Server TTS still needs an available TTS engine; shared Snapcast
playback still needs its safely configured central audio path and verified
client isolation. The integration enforces those infrastructure and safety
requirements even in manual mode.

The Send button uses the native `notify.announcement_hub` action and requests
the queue response. It displays the accepted job ID, or an error without an
automatic retry that could submit a duplicate. Critical messages require an
additional confirmation. The optional counter reads
`sensor.announcement_hub_queue`. **A queued acknowledgement is not proof
that a device displayed or spoke the message.**

The card uses Home Assistant's light/dark theme variables, adapts to mobile
screen widths, and respects reduced-motion preferences. Home Assistant's
normal authenticated dashboard and service permissions control who may send.

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
| Sleep rooms entity | A Home Assistant entity reporting rooms where people are **currently sleeping**; select it from a dropdown |
| Sleep rooms value | Choose **State** or a live attribute that contains a list of sleeping room area IDs, names or aliases |
| Mute TTS while everyone is sleeping | Toggle automatic speech/chime suppression when every occupied room is sleeping |
| Written fallback while sleeping | Toggle written-only replacement for automatic room announcements while sleep mute is active |
| Sleep-time written notification recipients | Multiselect: **Integration — all configured devices** first, followed by **individual devices**, limited to configured Announcement Hub notification outputs |
| Fallback room | Alternate area only if the target room contains an awake person, local delivery failed and the door rule permits |
| Require an open occupied-room door for fallback | Door rule that must pass before using the configured alternate room |
| Door sensor label filter | Optional label to restrict which door sensors count |
| Visual/TTS fallback preference | Visual first → TTS if it fails, TTS first → Visual if it fails, or Both eligible channels; applies only when both channel texts **and** both permitted output types exist |
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

**Sleeping rooms are not permanently designated bedrooms.** Configure a
separate **Sleep rooms entity** whose current state or an attribute contains
the areas with people currently asleep. For example:

```yaml
entity_id: sensor.sleeping_rooms
state: "2"
attributes:
  rooms:
    - Schlafzimmer
    - Kinderzimmer
```

Select `sensor.sleeping_rooms`, then choose the `rooms` attribute from the
**Sleep rooms value** dropdown on the next page. If your entity's state itself
contains the room names (e.g. `Schlafzimmer, Kinderzimmer` or
`["Schlafzimmer", "Kinderzimmer"]`), select **State** instead. Empty
lists mean nobody is currently sleeping. Home Assistant area IDs, names and
aliases are accepted; unrecognized names are ignored. The value is read again
for every queued announcement and immediately before TTS delivery: no HA
restart is needed when a person starts or stops sleeping.

An unavailable/missing sleeping-room source (or selected attribute) cannot
prove a person is awake; if **Mute TTS while everyone is sleeping** is enabled,
audio is suppressed while room occupancy is known.

The three sleep-policy controls under **General options** are independent
settings:

- **Mute TTS while everyone is sleeping** (default **On**): prevents all
  speech and pre-announcement chimes, including Critical and Companion App
  audio. Turn Off to use ordinary speech routing even if everyone sleeps.
- **Written fallback while sleeping** (default **On**): only when TTS sleep
  mute is active, redirect automatic room announcements to the explicitly
  selected written outputs. A TTS-only message uses its original text. Turn
  Off to keep these automatic announcements queued until the rooms are awake;
  it has no effect when sleep mute is Off.
- **Sleep-time written notification recipients**: first choose
  **Integration · [name] — all devices** or choose **Device · [name]** for
  individual outputs. Multiple choices are allowed. Integration-wide choices
  include **only notification outputs already enabled in Announcement Hub**,
  not every device that happens to exist in Home Assistant. An empty selection
  disables automatic sleep-time written delivery even with the fallback
  toggle On. Existing installations default to all already-configured
  **Companion App** notification devices.

For example, selecting the **mobile_app integration** plus an individual
**NFAndroidTV** display sends the sleep fallback to the configured mobile
phones and only that chosen display. Selecting **NFAndroidTV — all devices**
instead includes every configured NFAndroidTV notification device. Exact
integration/device/entity recipient restrictions supplied by an action
are never broadened by the sleep-time fallback.

An existing pre-v0.10.0b23 fixed-area selection is honored **only until**
a new live sleep-room entity is configured.

### Bursts when arriving home or moving between rooms

For a door/welcome automation, always give `wait_template` a finite
`timeout` when using `continue_on_timeout`: without one, waiting for
both a closed entrance door and a non-zero entrance people-counter can block
forever when the person has already walked to another room. Use a door-closed
wait with a reasonable timeout instead.

A routine that calls `notify.announcement_hub` several times with
`use_ai: true` and `ai_mode: generate` creates **one AI provider request per
announcement**. Announcement Hub serializes calls to the same model to protect
the provider, and does not cancel a cold-starting model on a fixed Hub timeout;
a large routine therefore cannot finish speaking instantly. Prefer concise
combined prompts for non-critical morning summaries, and a plain, already
formatted TTS text for a welcome requiring minimal latency. Room movement
rerouting fixes stale destinations, not slow external AI generation.

Scripts using Home Assistant's `mode: single` do not queue a second invocation
while the first is still running. For genuinely independent invocations that
must all run, consider `mode: queued` with an explicit `max`, after checking
that repeated routine announcements are desirable.

### Read-only diagnostics for an installed Home Assistant container

The repository includes two complementary scripts under `tools/`:

- `announcement_hub_onhost_scenarios.py` runs **14 simulated routing
  transitions using the installed integration code**. It never issues HA
  service calls, changes presence, or plays audio. It summarizes version,
  config, saved queue/AI state and recent Docker log signals without exporting
  announcement text or API credentials.
- `announcement_hub_container_evidence.py` runs read-only inside the existing
  HA Docker container. It distinguishes a genuinely empty private queue from
  an unreadable Store and optionally analyzes the latest **historical SQLite
  Recorder** observations for selected occupied/sleeping room entities and
  configured output states. Recorder values are *not* live states, and no
  Home Assistant token is required. MariaDB users may have no SQLite data.

For a host-side run, place both scripts in the same directory, then execute
`python3 announcement_hub_onhost_scenarios.py` on the **host**, not inside
Home Assistant. The host runner invokes the second script via a read-only
`docker exec -i homeassistant python3 -` call and writes a timestamped
sanitized JSON/TXT/TAR bundle under `~/projects/announcement_hub/logs`.
A local `HASS_TOKEN` can optionally enable a true live API state check;
never put access tokens into support archives or chat messages.

For a large AI backlog, set `AH_OBSERVE_SECONDS=70` for a second read-only
snapshot 70 seconds after the first. The report compares queue sizes, the
number awaiting AI, and a non-reversible marker for the most recent completed
AI job (without exporting its ID). It summarizes **all** queued jobs,
including AI-request age buckets, provider-level counts, exact duplicate
prompt group sizes, the oldest AI-ready head job and maximum per-room FIFO
concentration. No queued content, prompts or provider tokens are exported.
If the two snapshots do not differ, that indicates no observed progress in
the sample window; it does not by itself prove a provider deadlock.

## Person-targeted announcements and personal destinations

In **Configure → People and personal voices**, select Home Assistant people.
For each person you can set a room-tracking sensor, language, TTS voice,
**Translate announcements to this person's language**, and four named output
assignments: **Mobile**, **Watch**, **Tablet**, and **Other**. Each assignment
references your *existing* HA `notify` or supported `media_player` entities.
It does **not** create a second mobile/watch messaging subsystem.

### Room tracking: Bermuda, ESPresense and other sensors

In **Configure → People and personal voices → [person] → Room tracker**, choose
the **specific sensor or device tracker for that person**. A Bermuda area
sensor can report the actual room in its state, such as `Küche` or
`living_room`. ESPresense or another tracker can report `home` as its
state with the real room in an `area` or `room` attribute. Room values in
`area_id` and `room_name` are supported too.

Only a valid Home Assistant area ID, name or alias is accepted. A tracker
whose sole value is `home` does not identify a room. A configured tracker
takes precedence over the person entity's own location and is never replaced
by a stale fallback if it becomes unavailable. A `person.*` entity must
normally be `home` for **Room** announcements, unless **Allow when away**
is selected. Mobile and Watch deliveries do not require the room tracker.

The integration **reads these sensor states**; it does not install Bermuda,
ESPresense or perform beacon detection itself. You must configure room
tracking separately in Home Assistant.

### Send by person and destination name

```yaml
action: notify.announcement_hub
data:
  text: "Die Waschmaschine ist fertig."
  target_person:
    - person.alex
  person_destination:
    - mobile
    - watch
  person_translate: true
```

The action and Lovelace card display named choices (Room, Mobile, Watch,
Tablet, Other), **not entity names**. The entity IDs are mapped in setup.
The card offers only destinations assigned to all selected people and an
optional per-send translation preference (Person setting, Translate,
Original language). An unassigned or disabled output is rejected, not
substituted with another person's device or an entire integration.

**Room** (default when `person_destination` is omitted) resolves the
person's current room using Bermuda/ESPresense or another configured tracker,
then sends only to suitable physical outputs in that room. Room delivery
requires a current valid location and ordinarily requires the person home.
An unavailable tracker cannot redirect to other occupied rooms or General
outputs. **Mobile, Watch, Tablet and Other** use only the outputs assigned
to that person and **do not require home status or room tracking**.

You can select several destination names and several persons together.
If selected people share a room, the Room leg sends **one** group announcement
using the configured group language, voice and translation preference.
Each person's Mobile/Watch/Tablet/Other leg uses their **own** language,
voice and translation setting. Different rooms remain independently queued;
the Hub deduplicates overlapping physical outputs within one combined send.

### Language translation and speech

If **Translate** is enabled for a person (or group), AI translates the
requested spoken and written channels **independently** into that person's
configured language. `text_tts` remains plain speech and `text_notify`
remains a readable visual notification. Only supplied channels are permitted,
and the selected TTS engine receives the translated speech, language and
voice preferences. A per-action `language` or `tts_options.voice` overrides
the profile; `person_translate` overrides automatic translation.

Translation works even if global AI rewriting is off; selecting
`use_ai: false` explicitly disables AI including translation for that call.
The selected primary AI agent, optional backup agent, and original-text
fallback continue to apply if translation fails. The original message is
stored before AI processing and never silently dropped because an AI
provider is offline. The translation must preserve numbers and facts; a
provider might still make linguistic mistakes, so sensitive alerts should
be tested on real hardware.

**Safety:** `target_person` cannot be combined with the ordinary
`area`, `integration`, `device`, or `entity` selectors. A requested
person destination only uses its assigned outputs, never everyone else's
Mobile App devices. For explicit device targeting without a person, use
the existing manual recipient controls.


## Person and room controls, AI personalization, and safe audio (beta)

**Configure → People and personal voices** now supports optional person
enable/disable, per-person presence verification, individual AI provider
(Conversation or AI Task), AI rewriting, a TTS engine, language and voice, and
optional greetings. The group settings offer their own AI/TTS provider,
rewrite preference, greeting name and speech/translation settings. The provider
drop-downs use discovered Home Assistant providers, with global defaults
when no override is selected. These settings change generation and speech
infrastructure, **never the physical recipient list**.

For example, using a literal person name placeholder without automatically
adding a greeting:

```yaml
action: notify.announcement_hub
data:
  text: "{{ name }}, your package arrived."
  target_person: [person.alex]
  person_destination: [room, mobile]
```

Alternatively, in the dashboard's **People** mode, set Personal greeting to
**Yes** to prepend the person's preferred salutation automatically. Its
default follows the individual/group configuration. No new person or room is
added as a recipient by greeting substitution.

**Enable switches:** the integration creates one enable switch for each
configured person and each Home Assistant area, default on. Switching one off
persists the preference across Home Assistant restarts and blocks the next
delivery to that person or room. Queued person jobs are rechecked before
the physical service call. A disabled Room does not get substituted by a
General phone or unrelated speaker.

**Presence verification:** select a person's binary presence sensor (and
enable Require presence verification), or open **Configure → Room presence
verification** to assign an optional room occupancy sensor. Only an explicit
positive `on` reading permits that Room announcement. Missing, stale,
unavailable and off readings are not evidence of presence. This safety check
does not apply to that person's explicitly assigned Mobile/Watch/Tablet
destinations.

**AI style preferences:** **Configure → Advanced AI prompts** offers optional
rewrite, translate and combined style instructions. Only literal
`{message}` and `{language}` placeholders are accepted. The Hub's immutable
rules for strict JSON, factual integrity, no device/tool actions and no new
channels remain mandatory. AI fallback continues to preserve the original.

**Direct-room audio:** **Configure → Audio, chime and ducking** adds optional
pre-announcement audio from a local `/local/*.mp3`/WAV/OGG/FLAC file, and
optional volume ducking for selected **direct room media players**. Both
default off. Ducking stores the original volume before lowering it, restores
it in `finally`, and attempts guarded recovery after a Home Assistant
restart if interrupted. It does not duck or play chimes on the shared
Snapcast source; its isolation rules are unchanged. Native announce support
and actual restore/playback behavior depend on the media player and should
be tested in beta.

```yaml
action: notify.announcement_hub
data:
  text: "Dinner is ready."
  target_person: [person.alex]
  person_destination: [room]
  person_greeting: true
  pre_announce_sound: true
```

A targeted Room still requires a valid area and a suitable output;
Mobile/Watch continue to use only the devices assigned under that person's
profile. Disabling a person or room never authorizes unrelated recipients.

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

- With a configured occupancy source, an **unoccupied requested room** is
  skipped in favor of other occupied rooms with authorized room devices.
  With no occupancy source configured, the requested room is retained, but
  the alternate fallback room still requires confirmed target-room presence.
  If the configured source is unavailable, unconfirmed room presence is not
  assumed, and the alternate fallback room remains ineligible.
- The **sleeping-room entity** lists rooms with sleeping people **right now**.
  With **Mute TTS while everyone is sleeping** enabled, if the configured
  occupied-room list is contained in the sleep list, no TTS starts (including
  Critical, Snapcast and companion speech). When **Written fallback while
  sleeping** is also enabled, only the explicitly selected configured
  integration/device notification outputs receive written text; TTS-only
  messages use their spoken text as written text. If the sleep source is
  unavailable and occupancy is known, the same enabled mute/fallback policy
  applies. Without enabled/eligible recipients, the job remains queued.
  Switching mute Off restores ordinary speech routing.
- The **occupied-room stage** uses the configured occupancy sensor; it does
  not guess where people are. A queued automatic/area announcement remembers
  the previous occupancy only to detect moves. When people move, the worker
  immediately revisits current rooms (including a job already waiting at the
  final General tier) and rechecks room occupancy before using a room-bound
  screen, direct speaker or Snapcast output. If the selected room becomes
  empty before the physical service call, the undelivered announcement is
  requeued against live occupied rooms, without re-running its AI generation
  or marking the old speaker as successful. An announcement already playing
  is not interrupted mid-sentence; the guard applies **before playback**.
- **Persistent Companion App text notifications** do not artificially hold
  an occupied-room lane for the screen reading duration after the push
  service acknowledges. NFAndroidTV and other short-lived visual overlays
  continue to respect their reading-time settings, so a succeeding overlay
  does not overwrite text too early.
- The **alternate-room stage** is allowed only for a targeted, non-sleep room
  with a confirmed occupant, after the original room and other occupied-room
  delivery paths did not succeed. It is never used when the targeted room
  is unoccupied. The stage also observes the configured open-door condition.
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

**Choose a delivery preference** in **Configure → 4. General settings, presence & AI → Notification channel fallback**:

| Configuration choice | With two eligible channels |
| --- | --- |
| **Visual first → TTS on failure** | Try the written notification first; use TTS only if the visual provider cannot deliver |
| **TTS first → Visual on failure** | Try spoken TTS first; use the written notification only if speech cannot be delivered |
| **Both eligible channels** | Attempt both written notification and speech, subject to their eligibility and severity settings |

**This rule is active only if both channel texts (`text_tts` and
`text_notify`) are present AND a permitted visual output and a permitted
audio output are candidates at the current route.** The shared `text`
field fills both variants unless overridden. If only one channel or only
one eligible output type exists, that channel is used as usual. No text
is copied between channels, and no additional device, room, integration
or service is authorized.

For an area-targeted announcement, provider failure retries the other
eligible channel **inside the same room** before advancing through occupied
rooms, the door-checked fallback area or General notifications. An already
successful Home Assistant send does not trigger a second-channel fallback;
it does not guarantee the receiving device visibly displayed the message.
The normal TTS severity threshold, hard **Never** setting (except Critical),
and configured notification minimums still apply. The **Both** choice
preserves the existing room-first low-severity preference and simultaneous
delivery where both channels are eligible.

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

**Audio isolation safeguards:** the shared TTS player is infrastructure, not
an announcement recipient. Playback is refused if there are no explicitly
selected physical Snapcast clients or if the selected clients cannot be
isolated from the other clients on the stream. It is never safe to play
through the shared MPD source without a verified mute route: every client
already listening to that stream could hear it. Older stored queue jobs
without a physical route are not expanded into a whole-house broadcast.

While shared TTS plays and its buffered audio tail drains, Hub checks that
only the intended Snapcast clients are unmuted. If a second automation
changes these mute states, Hub stops shared playback and re-mutes other
managed clients before it restores their previous states. The channel error
records the unexpected unmuted client so the conflicting controller can be
identified.

**When a bell is heard:** Hub does not generate a pre-announcement bell
file. Home Assistant's `media_player.play_media` announcement flag can
trigger provider-specific behaviors such as a chime. The dedicated shared
Snapcast/MPD route does not use this announcement flag. Under **Configure →
2. TTS engines & devices**, you can disable **Direct-speaker announcement
mode** if a selected standalone media player/voice assistant plays an
unwanted notification sound. Doing so may interrupt existing media instead
of temporarily announcing and resuming.

If you have a separate automation that changes Snapcast `volume_mute`,
`source`, or a voice assistant's mute/volume during TTS, coordinate it with
Hub's current queue job. For example, before that automation changes audio
routing, check the **`current`** attribute of
`sensor.announcement_hub_queue`:

```yaml
- condition: template
  value_template: >-
    {% set current = state_attr('sensor.announcement_hub_queue', 'current') %}
    {{ current is none or not current.get('snapcast_clients') }}
```

Put the guard **immediately before** the competing mute/source actions;
a trigger-level condition alone cannot prevent an automation that was
already running from changing a route during playback. You should still
check that this does not suppress another necessary audio-volume action.
The Hub's own isolation monitor is a final safety net, not a replacement
for coordinating two competing volume controllers.

If an old `script.text_to_speech` builds its `area` target from the complete
list of `input_select.rooms` options, it is itself explicitly requesting
all those rooms. Remove any rule that substitutes every room when a people
counter is `1`, unavailable, or a client name does not match. Prefer the
actual supplied room(s), or omit `area` and let Hub use occupancy routing.

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

## AI rewriting and announcement generation

Announcement Hub supports two AI modes: `rewrite` (the default, for
copyediting already-complete factual messages) and `generate` (for
producing an announcement from instructions such as "summarize today's
calendar" or "tell the household the laundry has finished"). Generation
happens **after the original instructions are persisted in the queue**, so
a burst of calls never depends on an out-of-queue AI response before Hub
can acknowledge them.

```yaml
action: notify.announcement_hub
data:
  text: "Tell the household in Greek that the washing machine has finished."
  area:
    - Kitchen
  ai_mode: generate
  use_ai: true
```

When `ai_mode: generate` is enabled and the action **omits `title`**,
the same AI request also creates a descriptive notification title (one to
three words, in the announcement's language). Hub removes formatting and
enforces the three-word limit before using it, without another AI request.
An explicitly supplied title is never overwritten, including on Critical
announcements. If AI fails or returns no acceptable title, the configured
**Default notification title** remains in use.

The generated title is stored with the queued job and appears on its visual
notifications; it is not spoken as part of `text_tts`. To enable this,
provide `ai_mode: generate` and `use_ai: true` (or enable AI by default)
while leaving `title` out of the action:

```yaml
action: notify.announcement_hub
data:
  text: "Tell the household in Greek that the washing machine has finished."
  ai_mode: generate
  use_ai: true
```

Generated speech and visual output remain separate. This is a *content
generation* feature only, not permission for the agent to execute actions.
If both AI agents fail, the original instructions remain the final text
fallback; for urgent safety alerts, use direct factual content instead.

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

  # Alternatively select an AI Task entity:
  # ai_agent: ai_task.my_model
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


### AI Task providers

Announcement Hub supports Home Assistant **AI Task** entities alongside conversation agents. In the integration's general AI settings, choose an `ai_task.*` entity as the primary or backup provider. For a specific announcement, set `ai_agent: ai_task.your_entity` with `use_ai: true`. The Hub calls `ai_task.generate_data` with the announcement instructions and validates its JSON response using the same factual, speech and visual safeguards as conversation agents. If the AI Task fails or returns invalid content, the configured backup provider is tried; otherwise the original announcement is delivered. AI preprocessing continues within the existing durable announcement queue.


### Concurrent delivery and queue ordering

Announcement Hub preserves **FIFO delivery within each room**, including
announcements still waiting for AI rewriting or generation, TTS rendering,
output availability, or retry. An older message cannot be overtaken by a
newer message for the same room. When several room announcements are queued,
a slow or unavailable announcement for one room **does not block an unrelated
room**: the Hub runs up to four disjoint room deliveries concurrently.

The scheduler also reserves shared physical notification targets, direct
speakers and the common Snapcast source, so overlapping device routes are
serialized even across different rooms. For burst traffic, at most two AI
requests and two TTS prefetched renders run at once, with fair selection
across rooms. Service acknowledgement remains durable and prompt;
undelivered jobs retain their original order through retries and restart.

### Diagnosing unchanged announcements when AI is online

Announcement Hub **never treats being online as proof of a valid rewritten result**.
Open the `sensor.announcement_hub_queue` entity in Developer Tools → States
and inspect `recent_ai` for the last 20 AI outcomes, including failed,
successful, and explicitly AI-disabled announcements. The `last.ai` field
only describes the latest finished announcement and can be overwritten by
a later success. These diagnostics retain safe status information only,
not the original message, model prompt or generated content:

- `rewritten`: the model's response passed checks and changed the text.
- `accepted_unchanged`: AI responded and passed validation, but did not change the text.
- `fallback_original`: AI processing failed or produced an unsafe/invalid response.
  Inspect `failure_reason` and `attempts` to distinguish `agent_error`,
  `provider_timeout`, `invalid_json`, `unexpected_response_fields`,
  `number_mismatch`, `action_response_not_allowed` and unavailable
  preferred Assist agents.
- `disabled` or `not_applicable`: AI was not requested for this job or
  there was no eligible text channel. Check the integration's AI default
  and any per-announcement `use_ai` override.

When selecting `ai_task.*`, the Hub requests **native structured output**
from Home Assistant and checks both the speech and visual results. A provider
that explicitly rejects structured schemas gets one compatibility attempt
with an ordinary JSON-in-text task instead. Identical AI providers are not
called concurrently for different rooms; independent rooms still keep their
separate delivery queues. A genuine provider failure still uses the configured
backup AI agent, then the original message—never a potentially altered
measurement or an unintended new output channel.

If unchanged announcements persist, the most useful evidence is the
`last.ai` diagnostics and the relevant Announcement Hub warning from the
Home Assistant log at the time. Do not share private announcement text,
authentication tokens or provider secrets.


When the AI is reachable but returns invalid JSON or omits a required
channel, the Hub accepts one unambiguous JSON object even if the agent adds
a brief preamble. It also accepts missing **null** channels and ignores an
unused generated title without enabling new outputs. If a reply is still
invalid or changes measured numbers, and no backup provider is available,
Hub makes **one short, safe formatting retry** with the same provider.
Numeric integrity, strict recipient routing and no-tool-execution checks
remain in force; an unsafe second response still falls back to the original.
The `recent_ai` sensor history includes the safe retry count and failure
classification, so a previous failed announcement remains inspectable after
other announcements succeed.
