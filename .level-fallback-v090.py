from pathlib import Path
import json

ROOT=Path(".")
C=ROOT/"custom_components"/"announcement_hub"

def rep(path,old,new,count=1):
    text=path.read_text(encoding="utf-8")
    found=text.count(old)
    if found!=count:
        raise SystemExit(f"{path}: expected {count}, found {found}: {old[:120]!r}")
    path.write_text(text.replace(old,new,count),encoding="utf-8")

# models: permit cross-channel fallback without changing announcement severity.
p=C/"models.py"
rep(p,
'''    companion_tts_entries: Sequence[str],
    server_tts_enabled: bool,
) -> DeliveryPlan:
''',
'''    companion_tts_entries: Sequence[str],
    server_tts_enabled: bool,
    force_tts: bool = False,
    force_notify: bool = False,
) -> DeliveryPlan:
''')
rep(p,
'''    if level == LEVEL_CRITICAL:
        tts_text = text_tts or text_notify
        notify_text = text_notify or text_tts
    elif audible:
        tts_text = text_tts
        notify_text = text_notify
    else:
        # Below the audible threshold, spoken-only messages become visual rather
        # than disappearing. Explicit written text still takes precedence.
        tts_text = None
        notify_text = text_notify or text_tts
''',
'''    if level == LEVEL_CRITICAL:
        tts_text = text_tts or text_notify
        notify_text = text_notify or text_tts
    else:
        tts_text = (
            text_tts or text_notify
            if force_tts
            else (text_tts if audible else None)
        )
        notify_text = (
            text_notify or text_tts
            if force_notify or not audible
            else text_notify
        )
''')
rep(p,
'''        tts_suppressed_by_level=bool(text_tts and not audible),
''',
'''        tts_suppressed_by_level=bool(
            text_tts and not audible and not force_tts
        ),
''')

# manager: availability-aware channel selection.
p=C/"manager.py"

# Keep every level-configured notify candidate until the availability selector runs.
rep(p,
'''        all_notify_records = tuple(
            output
            for output in resolve_notify_outputs(self.hass, base_selected[1])
            if self._notify_level_allowed(
                level,
                self._notify_policy(output)[1],
            )
        )
''',
'''        all_notify_records = tuple(
            resolve_notify_outputs(self.hass, base_selected[1])
        )
''')

# Add helper methods before async_enqueue.
anchor='''    async def async_enqueue(
'''
text=p.read_text(encoding="utf-8")
i=text.index(anchor)
helpers='''    @staticmethod
    def _level_distance(level: str, minimum: str) -> int:
        """Return severity-distance between an announcement and an output threshold."""
        return abs(
            LEVEL_PRIORITY.get(level, LEVEL_PRIORITY[LEVEL_INFO])
            - LEVEL_PRIORITY.get(minimum, LEVEL_PRIORITY[LEVEL_INFO])
        )

    def _server_tts_available_now(
        self,
        *,
        engines: Sequence[str],
        player: str | None,
        snapcast_clients: Sequence[str],
    ) -> bool:
        """Return whether the shared TTS path can run immediately."""
        if not player or not engines:
            return False
        state = self.hass.states.get(player)
        if state is None or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            return False
        if not any(tts_engine_available(self.hass, engine) for engine in engines):
            return False
        if not snapcast_clients:
            return True
        return any(
            self._snapcast_output_available(entity_id)
            for entity_id in snapcast_clients
        )

    def _direct_tts_available_now(
        self,
        entity_id: str,
        engines: Sequence[str],
    ) -> bool:
        """Return whether a direct TTS media player can run immediately."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            return False
        return any(tts_engine_available(self.hass, engine) for engine in engines)

'''
p.write_text(text[:i]+helpers+text[i:],encoding="utf-8")

# Replace routed plan core selection with availability-aware ranking.
old='''            # The shared server player is global infrastructure. In
            # occupancy-aware mode its physical room candidates are the routing
            # clients, never the shared player itself.
            server_tts_enabled = bool(player and routed_selected[0])
            if filter_by_area and server_tts_enabled:
                server_tts_enabled = bool(routed_selected[3])

            route_plan = build_delivery_plan(
                text_tts=text_tts,
                text_notify=text_notify,
                level=level,
                minimum_tts_level=minimum_tts_level,
                tts_engines=routed_selected[0],
                notify_outputs=routed_selected[1],
                room_tts_players=routed_selected[2],
                snapcast_clients=routed_selected[3],
                companion_tts_entries=routed_selected[4],
                server_tts_enabled=server_tts_enabled,
            )
'''
new='''            # Build all physical channel candidates first. Level policy chooses
            # among candidates that are available NOW. An unavailable preferred
            # channel never makes an immediately usable fallback wait.
            server_tts_enabled = bool(player and routed_selected[0])
            if filter_by_area and server_tts_enabled:
                server_tts_enabled = bool(routed_selected[3])

            notify_by_ref = {output.ref: output for output in routed_notify}
            companion_by_id = {
                output.entry_id: output for output in routed_companion
            }
            actual_priority = LEVEL_PRIORITY.get(
                level, LEVEL_PRIORITY[LEVEL_INFO]
            )
            tts_hard_disabled = (
                minimum_tts_level == TTS_LEVEL_NEVER
                and level != LEVEL_CRITICAL
            )

            candidates: list[dict[str, Any]] = []
            for ref in routed_selected[1]:
                output = notify_by_ref.get(ref)
                if output is None:
                    continue
                minimum = self._notify_policy(output)[1]
                candidates.append(
                    {
                        "kind": "notify",
                        "id": ref,
                        "minimum": minimum,
                        "available": notify_output_available(self.hass, output),
                        "native_text": bool(text_notify or level == LEVEL_CRITICAL),
                    }
                )

            if not tts_hard_disabled:
                for entity_id in routed_selected[2]:
                    candidates.append(
                        {
                            "kind": "room_tts",
                            "id": entity_id,
                            "minimum": minimum_tts_level,
                            "available": self._direct_tts_available_now(
                                entity_id, routed_selected[0]
                            ),
                            "native_text": bool(
                                text_tts or level == LEVEL_CRITICAL
                            ),
                        }
                    )

                if server_tts_enabled:
                    candidates.append(
                        {
                            "kind": "server_tts",
                            "id": "__server_tts__",
                            "minimum": minimum_tts_level,
                            "available": self._server_tts_available_now(
                                engines=routed_selected[0],
                                player=player,
                                snapcast_clients=routed_selected[3],
                            ),
                            "native_text": bool(
                                text_tts or level == LEVEL_CRITICAL
                            ),
                        }
                    )

                for entry_id in routed_selected[4]:
                    output = companion_by_id.get(entry_id)
                    if output is None:
                        continue
                    candidates.append(
                        {
                            "kind": "companion_tts",
                            "id": entry_id,
                            "minimum": minimum_tts_level,
                            "available": companion_output_available(
                                self.hass, output
                            ),
                            "native_text": bool(
                                text_tts or level == LEVEL_CRITICAL
                            ),
                        }
                    )

            available = [item for item in candidates if item["available"]]
            normal_available = [
                item
                for item in available
                if item["native_text"]
                and actual_priority
                >= LEVEL_PRIORITY.get(
                    item["minimum"], LEVEL_PRIORITY[LEVEL_INFO]
                )
            ]

            force_tts = False
            force_notify = False
            if normal_available:
                chosen = normal_available
            elif available:
                # No currently available normal-level path exists. Pick the
                # available threshold nearest to the actual announcement level.
                distance = min(
                    self._level_distance(level, item["minimum"])
                    for item in available
                )
                chosen = [
                    item
                    for item in available
                    if self._level_distance(level, item["minimum"]) == distance
                ]
                force_tts = any(
                    item["kind"] != "notify" for item in chosen
                )
                force_notify = any(
                    item["kind"] == "notify" for item in chosen
                )
            else:
                # Nothing can run right now. Preserve the normal configured
                # level candidates so the existing availability timeout can
                # wait for them. If no normal candidate exists at all, wait on
                # the nearest configured fallback tier.
                normal_configured = [
                    item
                    for item in candidates
                    if item["native_text"]
                    and actual_priority
                    >= LEVEL_PRIORITY.get(
                        item["minimum"], LEVEL_PRIORITY[LEVEL_INFO]
                    )
                ]
                if normal_configured:
                    chosen = normal_configured
                elif candidates:
                    distance = min(
                        self._level_distance(level, item["minimum"])
                        for item in candidates
                    )
                    chosen = [
                        item
                        for item in candidates
                        if self._level_distance(level, item["minimum"])
                        == distance
                    ]
                    force_tts = any(
                        item["kind"] != "notify" for item in chosen
                    )
                    force_notify = any(
                        item["kind"] == "notify" for item in chosen
                    )
                else:
                    chosen = []

            chosen_notify = {
                item["id"] for item in chosen if item["kind"] == "notify"
            }
            chosen_room_tts = {
                item["id"] for item in chosen if item["kind"] == "room_tts"
            }
            chosen_companion = {
                item["id"]
                for item in chosen
                if item["kind"] == "companion_tts"
            }
            choose_server_tts = any(
                item["kind"] == "server_tts" for item in chosen
            )

            # When a server-TTS path is immediately available, do not freeze
            # unavailable Snapcast clients into the job: use the clients that
            # can receive the shared stream right now.
            chosen_snapcast = tuple(routed_selected[3])
            if choose_server_tts and routed_selected[3]:
                ready_snapcast = tuple(
                    entity_id
                    for entity_id in routed_selected[3]
                    if self._snapcast_output_available(entity_id)
                )
                if ready_snapcast:
                    chosen_snapcast = ready_snapcast

            routed_notify = tuple(
                output for output in routed_notify
                if output.ref in chosen_notify
            )
            routed_companion = tuple(
                output for output in routed_companion
                if output.entry_id in chosen_companion
            )
            routed_selected = (
                routed_selected[0],
                tuple(ref for ref in routed_selected[1] if ref in chosen_notify),
                tuple(
                    entity_id for entity_id in routed_selected[2]
                    if entity_id in chosen_room_tts
                ),
                chosen_snapcast if choose_server_tts else (),
                tuple(
                    entry_id for entry_id in routed_selected[4]
                    if entry_id in chosen_companion
                ),
            )
            server_tts_enabled = bool(choose_server_tts)

            route_plan = build_delivery_plan(
                text_tts=text_tts,
                text_notify=text_notify,
                level=level,
                minimum_tts_level=minimum_tts_level,
                tts_engines=routed_selected[0],
                notify_outputs=routed_selected[1],
                room_tts_players=routed_selected[2],
                snapcast_clients=routed_selected[3],
                companion_tts_entries=routed_selected[4],
                server_tts_enabled=server_tts_enabled,
                force_tts=force_tts,
                force_notify=force_notify,
            )
'''
rep(p,old,new)

# Remove old special-case below-threshold visual fallback: new selector owns all fallback.
old='''        if (
            not tts_allowed_for_level(level, minimum_tts_level)
            and not selected[1]
            and configured[1]
        ):
            # A caller may explicitly request an audible path, but the configured
            # level policy wins. Fall back to the configured visual outputs rather
            # than rejecting or silently dropping the announcement.
            selected = (
                selected[0],
                configured[1],
                selected[2],
                selected[3],
                selected[4],
            )

'''
rep(p,old,"")

# Import TTS_LEVEL_NEVER.
rep(p,
'''    TARGET_SERVICE_PREFIX,
)
''',
'''    TARGET_SERVICE_PREFIX,
    TTS_LEVEL_NEVER,
)
''')

# version
rep(C/"const.py",'VERSION: Final = "0.8.3"','VERSION: Final = "0.9.0"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.8.3":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.9.0"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# tests
(ROOT/"tests"/"test_level_availability_fallback.py").write_text('''"""Contracts for immediate availability-aware level fallback."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_selector_prefers_currently_available_normal_level_outputs() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "normal_available" in manager
    assert 'if normal_available:' in manager
    assert "chosen = normal_available" in manager


def test_selector_uses_nearest_available_level_without_waiting() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "elif available:" in manager
    assert "self._level_distance(level, item" in manager
    assert "unavailable preferred" in manager


def test_cross_channel_fallback_can_reuse_other_text() -> None:
    models=(C/"models.py").read_text(encoding="utf-8")
    assert "force_tts: bool = False" in models
    assert "force_notify: bool = False" in models
    assert "text_tts or text_notify" in models
    assert "text_notify or text_tts" in models


def test_available_server_tts_drops_unavailable_snapclients() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "ready_snapcast" in manager
    assert "chosen_snapcast = ready_snapcast" in manager


def test_nothing_available_keeps_timeout_wait_path() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "normal_configured" in manager
    assert "Nothing can run right now" in manager
    assert "existing availability timeout" in manager


def test_never_remains_a_hard_tts_disable_except_critical() -> None:
    manager=(C/"manager.py").read_text(encoding="utf-8")
    assert "tts_hard_disabled" in manager
    assert "minimum_tts_level == TTS_LEVEL_NEVER" in manager
''',encoding="utf-8")

res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8").replace(
    'assert manifest["version"] == "0.8.3"',
    'assert manifest["version"] == "0.9.0"',
)
res.write_text(text,encoding="utf-8")

ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.9.0 - 2026-10-03

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

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied 0.9.0 availability-aware level fallback")
