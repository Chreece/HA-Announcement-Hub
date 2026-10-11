![Announcement Hub](https://raw.githubusercontent.com/Chreece/HA-Announcement-Hub/main/.github/assets/announcement-hub-banner.svg)

# Announcement Hub

A Home Assistant-native, persistent announcement queue that coordinates **TTS**, **Snapcast**, **room-aware media players**, **Companion App TTS**, and **visual notifications** without overlapping the next job.

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Chreece&repository=HA-Announcement-Hub&category=integration)

## Highlights

- Persistent queue survives Home Assistant restarts.
- Room-aware routing by Home Assistant area and occupancy.
- Visual notifications and spoken announcements can run concurrently.
- Continuous TTS pre-rendering reduces gaps between queued announcements.
- Snapcast mute/routing state is verified and restored.
- Optional Android Companion App push TTS.
- Per-integration visual notification profiles.
- NFAndroidTV power-aware fallback when the physical display is unavailable.
- Critical announcements can fan out to every configured matching output.

## Install with HACS

Add this repository as a **custom integration** in HACS, then download **Announcement Hub** and restart Home Assistant.

After restart, go to **Settings → Devices & services → Add integration → Announcement Hub**.

## Main action

```yaml
action: notify.announcement_hub
data:
  text_tts: "The washing machine has finished."
  text_notify: "Washing machine finished."
  output:
    - living_room
  level: info
```

For the complete configuration guide, routing semantics, queue behavior, examples, and troubleshooting, see the repository README.
