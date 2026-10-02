from pathlib import Path
import json

ROOT=Path(".")
C=ROOT/"custom_components"/"announcement_hub"

def rep(path, old, new):
    text=path.read_text(encoding="utf-8")
    count=text.count(old)
    if count!=1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:140]!r}")
    path.write_text(text.replace(old,new,1),encoding="utf-8")

# const.py
p=C/"const.py"
rep(p,'VERSION: Final = "0.5.4"','VERSION: Final = "0.6.0"')
rep(p,
'CONF_TTS_MEDIA_PLAYER: Final = "tts_media_player"\n',
'CONF_TTS_MEDIA_PLAYER: Final = "tts_media_player"\nCONF_TTS_ROOM_PLAYERS: Final = "tts_room_players"\n'
)

# outputs.py: expose generic media-player expansion.
p=C/"outputs.py"
anchor='''def expand_snapcast_output_tokens(
    hass: HomeAssistant, tokens: Sequence[str]
) -> tuple[str, ...]:
'''
text=p.read_text(encoding="utf-8")
if anchor not in text:
    raise SystemExit("outputs.py snapcast anchor missing")
helper='''def expand_media_player_tokens(
    hass: HomeAssistant, tokens: Sequence[str]
) -> tuple[str, ...]:
    """Expand integration/entry/entity selectors to media-player entities."""
    return _expand_entity_tokens(hass, tokens, entity_domain="media_player")


'''
p.write_text(text.replace(anchor,helper+anchor,1),encoding="utf-8")

# config_flow.py
p=C/"config_flow.py"
rep(p,
'    CONF_TTS_LANGUAGE,\n    CONF_TTS_MEDIA_PLAYER,\n    CONF_TTS_MIN_LEVEL,\n',
'    CONF_TTS_LANGUAGE,\n    CONF_TTS_MEDIA_PLAYER,\n    CONF_TTS_ROOM_PLAYERS,\n    CONF_TTS_MIN_LEVEL,\n'
)

# Move Snapcast output selection out of generic Outputs page.
rep(p,
'''                    CONF_NOTIFY_OUTPUTS: [],
                    CONF_SNAPCAST_OUTPUTS: [],
                    CONF_COMPANION_TTS_OUTPUTS: [],
''',
'''                    CONF_NOTIFY_OUTPUTS: [],
                    CONF_COMPANION_TTS_OUTPUTS: [],
''')
rep(p,
'''                probatio.Optional(
                    CONF_SNAPCAST_OUTPUTS,
                    default=self._value(CONF_SNAPCAST_OUTPUTS, []),
                ): _multi_select(snapcast_output_options(self.hass)),
''',
"")

old='''        if user_input is not None:
            engines = list(user_input.get(CONF_TTS_ENGINES, []))
            player = user_input.get(CONF_TTS_MEDIA_PLAYER)
            snapcast = list(self._working.get(CONF_SNAPCAST_OUTPUTS, []))
            if engines and not player:
                errors["base"] = "tts_player_required"
            elif player and not engines:
                errors["base"] = "tts_engine_required"
            elif snapcast and (not engines or not player):
                errors["base"] = "snapcast_tts_path_required"
            else:
                self._store_step(
                    user_input,
                    {
                        CONF_TTS_ENGINES: [],
                        CONF_TTS_MEDIA_PLAYER: None,
                        CONF_TTS_MIN_LEVEL: DEFAULT_TTS_MIN_LEVEL,
'''
new='''        if user_input is not None:
            engines = list(user_input.get(CONF_TTS_ENGINES, []))
            room_players = list(user_input.get(CONF_TTS_ROOM_PLAYERS, []))
            player = user_input.get(CONF_TTS_MEDIA_PLAYER)
            snapcast = list(user_input.get(CONF_SNAPCAST_OUTPUTS, []))
            if engines and not (room_players or player):
                errors["base"] = "tts_player_required"
            elif (room_players or player or snapcast) and not engines:
                errors["base"] = "tts_engine_required"
            elif snapcast and not player:
                errors["base"] = "snapcast_tts_path_required"
            else:
                self._store_step(
                    user_input,
                    {
                        CONF_TTS_ENGINES: [],
                        CONF_TTS_ROOM_PLAYERS: [],
                        CONF_TTS_MEDIA_PLAYER: None,
                        CONF_SNAPCAST_OUTPUTS: [],
                        CONF_TTS_MIN_LEVEL: DEFAULT_TTS_MIN_LEVEL,
'''
rep(p,old,new)

marker='''                _optional_marker(
                    CONF_TTS_MEDIA_PLAYER,
                    self._value(CONF_TTS_MEDIA_PLAYER, None),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="media_player")
                ),
'''
insert='''                probatio.Optional(
                    CONF_TTS_ROOM_PLAYERS,
                    default=self._value(CONF_TTS_ROOM_PLAYERS, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="media_player",
                        multiple=True,
                    )
                ),
''' + marker + '''                probatio.Optional(
                    CONF_SNAPCAST_OUTPUTS,
                    default=self._value(CONF_SNAPCAST_OUTPUTS, []),
                ): _multi_select(snapcast_output_options(self.hass)),
'''
rep(p,marker,insert)

# models.py
p=C/"models.py"
rep(p,
'''    snapcast_clients: tuple[str, ...] = ()
    companion_tts_entries: tuple[str, ...] = ()
''',
'''    room_tts_players: tuple[str, ...] = ()
    snapcast_clients: tuple[str, ...] = ()
    companion_tts_entries: tuple[str, ...] = ()
''')
rep(p,
'''            (self.server_tts_enabled and self.tts_engines)
            or self.companion_tts_entries
''',
'''            self.room_tts_players
            or (self.server_tts_enabled and self.tts_engines)
            or self.companion_tts_entries
''')
rep(p,
'''    notify_outputs: Sequence[str],
    snapcast_clients: Sequence[str],
''',
'''    notify_outputs: Sequence[str],
    room_tts_players: Sequence[str],
    snapcast_clients: Sequence[str],
''')
rep(p,
'''        notify_outputs=_unique(tuple(notify_outputs)),
        snapcast_clients=_unique(tuple(snapcast_clients)),
''',
'''        notify_outputs=_unique(tuple(notify_outputs)),
        room_tts_players=_unique(tuple(room_tts_players)),
        snapcast_clients=_unique(tuple(snapcast_clients)),
''')
rep(p,
'''    notify_outputs: tuple[str, ...]
    snapcast_clients: tuple[str, ...]
''',
'''    notify_outputs: tuple[str, ...]
    room_tts_players: tuple[str, ...]
    snapcast_clients: tuple[str, ...]
''')
rep(p,
'''    tts_player_area: str | None = None
    notify_output_areas: dict[str, str | None] = field(default_factory=dict)
''',
'''    tts_player_area: str | None = None
    room_tts_player_areas: dict[str, str | None] = field(default_factory=dict)
    notify_output_areas: dict[str, str | None] = field(default_factory=dict)
''')
rep(p,
'''        tts_player_area: str | None = None,
        notify_output_areas: Mapping[str, str | None] | None = None,
''',
'''        tts_player_area: str | None = None,
        room_tts_player_areas: Mapping[str, str | None] | None = None,
        notify_output_areas: Mapping[str, str | None] | None = None,
''')
rep(p,
'''            notify_outputs=plan.notify_outputs,
            snapcast_clients=plan.snapcast_clients,
''',
'''            notify_outputs=plan.notify_outputs,
            room_tts_players=plan.room_tts_players,
            snapcast_clients=plan.snapcast_clients,
''')
rep(p,
'''            tts_player_area=tts_player_area or None,
            notify_output_areas=dict(notify_output_areas or {}),
''',
'''            tts_player_area=tts_player_area or None,
            room_tts_player_areas=dict(room_tts_player_areas or {}),
            notify_output_areas=dict(notify_output_areas or {}),
''')
rep(p,
'''        for key in (
            "outputs",
            "requested_services",
            "tts_engines",
            "notify_outputs",
            "snapcast_clients",
            "companion_tts_entries",
        ):
            data[key] = list(data[key])
''',
'''        for key in (
            "outputs",
            "requested_services",
            "tts_engines",
            "notify_outputs",
            "room_tts_players",
            "snapcast_clients",
            "companion_tts_entries",
        ):
            data[key] = list(data[key])
''')
rep(p,
'''        payload.setdefault("snapcast_clients", [])
        payload.setdefault("companion_tts_entries", [])
''',
'''        payload.setdefault("room_tts_players", [])
        payload.setdefault("snapcast_clients", [])
        payload.setdefault("companion_tts_entries", [])
''')
rep(p,
'''        payload.setdefault("tts_player_area", None)
        payload.setdefault("notify_output_areas", {})
''',
'''        payload.setdefault("tts_player_area", None)
        payload.setdefault("room_tts_player_areas", {})
        payload.setdefault("notify_output_areas", {})
''')
# second tuple conversion block
rep(p,
'''            "notify_outputs",
            "snapcast_clients",
            "companion_tts_entries",
        ):
            payload[key] = tuple(payload.get(key, ()))
''',
'''            "notify_outputs",
            "room_tts_players",
            "snapcast_clients",
            "companion_tts_entries",
        ):
            payload[key] = tuple(payload.get(key, ()))
''')
rep(p,
'''            "notify_outputs": list(self.notify_outputs),
            "snapcast_clients": list(self.snapcast_clients),
''',
'''            "notify_outputs": list(self.notify_outputs),
            "room_tts_players": list(self.room_tts_players),
            "snapcast_clients": list(self.snapcast_clients),
''')
rep(p,
'''            "output_area_bindings": {
                "notify": dict(self.notify_output_areas),
''',
'''            "output_area_bindings": {
                "room_tts": dict(self.room_tts_player_areas),
                "notify": dict(self.notify_output_areas),
''')

# manager.py imports and generic media player expansion
p=C/"manager.py"
rep(p,
'    CONF_TTS_MEDIA_PLAYER,\n',
'    CONF_TTS_MEDIA_PLAYER,\n    CONF_TTS_ROOM_PLAYERS,\n'
)
rep(p,
'''    expand_notify_output_tokens,
    expand_snapcast_output_tokens,
''',
'''    expand_notify_output_tokens,
    expand_media_player_tokens,
    expand_snapcast_output_tokens,
''')

# Restore area mappings for queued jobs.
rep(p,
'''            if not job.notify_output_areas:
                job.notify_output_areas = {
''',
'''            if not job.room_tts_player_areas:
                job.room_tts_player_areas = {
                    entity_id: entity_area_id(self.hass, entity_id)
                    for entity_id in job.room_tts_players
                }
            if not job.notify_output_areas:
                job.notify_output_areas = {
''')

# Configured outputs now include direct room TTS players.
old='''    def _configured_outputs(
        self,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        return (
            expand_tts_engine_tokens(
                self.hass,
                self._ensure_list(self.settings.get(CONF_TTS_ENGINES, [])),
            ),
            expand_notify_output_tokens(
                self.hass,
                self._ensure_list(self.settings.get(CONF_NOTIFY_OUTPUTS, [])),
            ),
            expand_snapcast_output_tokens(
                self.hass,
                self._ensure_list(self.settings.get(CONF_SNAPCAST_OUTPUTS, [])),
            ),
            expand_companion_tts_tokens(
'''
new='''    def _configured_outputs(
        self,
    ) -> tuple[
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
    ]:
        return (
            expand_tts_engine_tokens(
                self.hass,
                self._ensure_list(self.settings.get(CONF_TTS_ENGINES, [])),
            ),
            expand_notify_output_tokens(
                self.hass,
                self._ensure_list(self.settings.get(CONF_NOTIFY_OUTPUTS, [])),
            ),
            expand_media_player_tokens(
                self.hass,
                self._ensure_list(self.settings.get(CONF_TTS_ROOM_PLAYERS, [])),
            ),
            expand_snapcast_output_tokens(
                self.hass,
                self._ensure_list(self.settings.get(CONF_SNAPCAST_OUTPUTS, [])),
            ),
            expand_companion_tts_tokens(
'''
rep(p,old,new)

# Selection signature and defaults.
rep(p,
'''        notify_outputs: Sequence[str],
        snapcast_clients: Sequence[str],
        companion_entries: Sequence[str],
''',
'''        notify_outputs: Sequence[str],
        room_tts_players: Sequence[str],
        snapcast_clients: Sequence[str],
        companion_entries: Sequence[str],
''')
rep(p,
'''    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
''',
'''    ) -> tuple[
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
    ]:
''',)
rep(p,
'''                tuple(notify_outputs),
                tuple(snapcast_clients),
                tuple(companion_entries),
''',
'''                tuple(notify_outputs),
                tuple(room_tts_players),
                tuple(snapcast_clients),
                tuple(companion_entries),
''')
# There are two same return blocks critical/no-request; replace second occurrence separately by remaining exact text.
rep(p,
'''                tuple(notify_outputs),
                tuple(snapcast_clients),
                tuple(companion_entries) if companion_tts else (),
''',
'''                tuple(notify_outputs),
                tuple(room_tts_players),
                tuple(snapcast_clients),
                tuple(companion_entries) if companion_tts else (),
''')
rep(p,
'''        configured_notify = set(notify_outputs)
        configured_snapcast = set(snapcast_clients)
''',
'''        configured_notify = set(notify_outputs)
        configured_room_tts = set(room_tts_players)
        configured_snapcast = set(snapcast_clients)
''')
rep(p,
'''        selected_notify: list[str] = []
        selected_snapcast: list[str] = []
''',
'''        selected_notify: list[str] = []
        selected_room_tts: list[str] = []
        selected_snapcast: list[str] = []
''')
rep(p,
'''        def select_server_tts() -> None:
            selected_tts.extend(tts_engines)
            selected_snapcast.extend(snapcast_clients)
''',
'''        def select_tts_outputs() -> None:
            selected_tts.extend(tts_engines)
            selected_room_tts.extend(room_tts_players)
            selected_snapcast.extend(snapcast_clients)
''')
text=p.read_text(encoding="utf-8")
if text.count('                select_server_tts()\n') != 2:
    raise SystemExit(
        f"{p}: expected two select_server_tts calls, found "
        f"{text.count('                select_server_tts()\\n')}"
    )
p.write_text(
    text.replace(
        '                select_server_tts()\n',
        '                select_tts_outputs()\n',
        2,
    ),
    encoding="utf-8",
)
rep(p,
'''            if canonical_entity in configured_notify:
                selected_notify.append(canonical_entity)
                matched = True
''',
'''            if canonical_entity in configured_notify:
                selected_notify.append(canonical_entity)
                matched = True
            if raw_entity in configured_room_tts:
                selected_room_tts.append(raw_entity)
                selected_tts.extend(tts_engines)
                matched = True
''')
rep(p,
'''            expanded_notify = set(
                expand_notify_output_tokens(self.hass, [selector_token])
            ) & configured_notify
            expanded_snapcast = set(
''',
'''            expanded_notify = set(
                expand_notify_output_tokens(self.hass, [selector_token])
            ) & configured_notify
            expanded_room_tts = set(
                expand_media_player_tokens(self.hass, [selector_token])
            ) & configured_room_tts
            expanded_snapcast = set(
''')
rep(p,
'''            if expanded_notify:
                selected_notify.extend(sorted(expanded_notify))
                matched = True
            if expanded_snapcast:
''',
'''            if expanded_notify:
                selected_notify.extend(sorted(expanded_notify))
                matched = True
            if expanded_room_tts:
                selected_room_tts.extend(sorted(expanded_room_tts))
                selected_tts.extend(tts_engines)
                matched = True
            if expanded_snapcast:
''')
rep(p,
'''        if selected_tts and not selected_snapcast:
            selected_snapcast.extend(snapcast_clients)

        return (
            tuple(dict.fromkeys(selected_tts)),
            tuple(dict.fromkeys(selected_notify)),
            tuple(dict.fromkeys(selected_snapcast)),
            tuple(dict.fromkeys(selected_companion)),
        )
''',
'''        if selected_tts and not selected_room_tts and not selected_snapcast:
            selected_room_tts.extend(room_tts_players)
            selected_snapcast.extend(snapcast_clients)

        return (
            tuple(dict.fromkeys(selected_tts)),
            tuple(dict.fromkeys(selected_notify)),
            tuple(dict.fromkeys(selected_room_tts)),
            tuple(dict.fromkeys(selected_snapcast)),
            tuple(dict.fromkeys(selected_companion)),
        )
''')

# Pass configured direct players into selector.
rep(p,
'''            tts_engines=configured[0],
            notify_outputs=configured[1],
            snapcast_clients=configured[2],
            companion_entries=configured[3],
''',
'''            tts_engines=configured[0],
            notify_outputs=configured[1],
            room_tts_players=configured[2],
            snapcast_clients=configured[3],
            companion_entries=configured[4],
''')

# Threshold visual fallback indexing.
rep(p,
'''            selected = (selected[0], configured[1], selected[2], selected[3])
''',
'''            selected = (
                selected[0],
                configured[1],
                selected[2],
                selected[3],
                selected[4],
            )
''')

# Resolve/filter direct players and update routed tuple indexes.
rep(p,
'''        all_notify_records = resolve_notify_outputs(self.hass, base_selected[1])
        all_companion_records = resolve_companion_tts_outputs(
            self.hass, base_selected[3]
        )
''',
'''        all_notify_records = resolve_notify_outputs(self.hass, base_selected[1])
        all_room_tts_players = tuple(base_selected[2])
        all_companion_records = resolve_companion_tts_outputs(
            self.hass, base_selected[4]
        )
''')
rep(p,
'''            tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]],
            tuple[NotifyOutput, ...],
''',
'''            tuple[
                tuple[str, ...],
                tuple[str, ...],
                tuple[str, ...],
                tuple[str, ...],
                tuple[str, ...],
            ],
            tuple[NotifyOutput, ...],
''')
rep(p,
'''                routed_snapcast = tuple(
                    entity_id
                    for entity_id in base_selected[2]
''',
'''                routed_room_tts = tuple(
                    entity_id
                    for entity_id in all_room_tts_players
                    if (
                        area_id := entity_area_id(self.hass, entity_id)
                    ) is not None
                    and area_id in effective_areas
                )
                routed_snapcast = tuple(
                    entity_id
                    for entity_id in base_selected[3]
''')
rep(p,
'''                    for output in all_companion_records
                    if output.area_id is not None
                    and output.area_id in effective_areas
                )
                routed_selected = (
                    base_selected[0],
                    tuple(output.ref for output in routed_notify),
                    routed_snapcast,
                    tuple(output.entry_id for output in routed_companion),
                )
            else:
                routed_notify = all_notify_records
                routed_companion = all_companion_records
                routed_selected = base_selected
''',
'''                    for output in all_companion_records
                    if output.area_id is not None
                    and output.area_id in effective_areas
                )
                routed_selected = (
                    base_selected[0],
                    tuple(output.ref for output in routed_notify),
                    routed_room_tts,
                    routed_snapcast,
                    tuple(output.entry_id for output in routed_companion),
                )
            else:
                routed_notify = all_notify_records
                routed_companion = all_companion_records
                routed_selected = base_selected
''')
rep(p,
'''            server_tts_enabled = bool(player and routed_selected[0])
            if filter_by_area and server_tts_enabled:
                if configured[2]:
                    server_tts_enabled = bool(routed_selected[2])
                else:
                    player_area = (
                        entity_area_id(self.hass, player) if player else None
                    )
                    server_tts_enabled = (
                        player_area is not None
                        and player_area in set(area_ids)
                    )
''',
'''            # The shared server player is global infrastructure. In
            # occupancy-aware mode its physical room candidates are the routing
            # clients, never the shared player itself.
            server_tts_enabled = bool(player and routed_selected[0])
            if filter_by_area and server_tts_enabled:
                server_tts_enabled = bool(routed_selected[3])
''')
rep(p,
'''                notify_outputs=routed_selected[1],
                snapcast_clients=routed_selected[2],
                companion_tts_entries=routed_selected[3],
''',
'''                notify_outputs=routed_selected[1],
                room_tts_players=routed_selected[2],
                snapcast_clients=routed_selected[3],
                companion_tts_entries=routed_selected[4],
''')

# Mapping indexes after routing.
rep(p,
'''        snapcast_client_areas = {
            entity_id: entity_area_id(self.hass, entity_id)
            for entity_id in selected[2]
        }
        companion_tts_entry_areas = {
            output.entry_id: output.area_id for output in companion_records
        }
''',
'''        room_tts_player_areas = {
            entity_id: entity_area_id(self.hass, entity_id)
            for entity_id in selected[2]
        }
        snapcast_client_areas = {
            entity_id: entity_area_id(self.hass, entity_id)
            for entity_id in selected[3]
        }
        companion_tts_entry_areas = {
            output.entry_id: output.area_id for output in companion_records
        }
''')

rep(p,
'''            tts_player_area=(
                entity_area_id(self.hass, player) if player else None
            ),
            notify_output_areas=notify_output_areas,
''',
'''            tts_player_area=None,
            room_tts_player_areas=room_tts_player_areas,
            notify_output_areas=notify_output_areas,
''')

# Direct TTS readiness + inclusion in runnable scheduler.
anchor='''    def _job_has_ready_server_tts(self, job: AnnouncementJob) -> bool:
'''
text=p.read_text(encoding="utf-8")
if anchor not in text:
    raise SystemExit("manager readiness anchor missing")
helper='''    def _job_has_ready_room_tts(self, job: AnnouncementJob) -> bool:
        """Return whether an area-bound direct TTS player can run now."""
        if not job.tts_text or not job.room_tts_players:
            return False
        if not any(
            tts_engine_available(self.hass, engine)
            for engine in job.tts_engines
        ):
            return False
        for player in job.room_tts_players:
            area_id = job.room_tts_player_areas.get(
                player, entity_area_id(self.hass, player)
            )
            if job.outputs and area_id not in set(job.outputs):
                continue
            state = self.hass.states.get(player)
            if state is not None and state.state not in {
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            }:
                return True
        return False

'''
p.write_text(text.replace(anchor,helper+anchor,1),encoding="utf-8")
rep(p,
'''            self._job_has_ready_visual_output(job)
            or self._job_has_ready_server_tts(job)
''',
'''            self._job_has_ready_visual_output(job)
            or self._job_has_ready_room_tts(job)
            or self._job_has_ready_server_tts(job)
''')

# Send direct room TTS separately from shared-server path.
rep(p,
'''    async def _async_send_tts(self, job: AnnouncementJob) -> None:
        if not job.tts_text:
            return

        if job.server_tts_enabled and job.tts_engines:
''',
'''    async def _async_send_tts(self, job: AnnouncementJob) -> None:
        if not job.tts_text:
            return

        if job.room_tts_players and job.tts_engines:
            await self._async_send_room_tts(job)

        if job.server_tts_enabled and job.tts_engines:
''')

anchor='''    async def _async_send_server_tts(self, job: AnnouncementJob) -> None:
'''
text=p.read_text(encoding="utf-8")
if anchor not in text:
    raise SystemExit("server tts anchor missing")
direct='''    async def _async_send_room_tts(self, job: AnnouncementJob) -> None:
        """Speak directly on area-bound media players using the TTS engine chain."""
        players = [
            player
            for player in job.room_tts_players
            if not job.outputs
            or job.room_tts_player_areas.get(
                player, entity_area_id(self.hass, player)
            )
            in set(job.outputs)
        ]
        if not players:
            return

        async def available(player: str) -> bool:
            state = self.hass.states.get(player)
            return state is not None and state.state not in {
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            }

        async def deliver(player: str) -> None:
            self._active_tts_player = player
            await self._await_prefetch(job)
            idle_timeout = float(
                self.settings.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT)
            )
            await self._wait_audio_path_idle(player, idle_timeout, job)
            engines = await self._async_available_tts_engines(job)
            if not engines:
                return
            errors: list[str] = []
            for engine in engines:
                channel = f"room_tts:{player}:{engine}"
                self._fire_channel_event(EVENT_CHANNEL_STARTED, job, channel)
                try:
                    media_source_id = job.media_source_ids.get(engine)
                    if not media_source_id:
                        media_source_id = self._build_media_source_id(job, engine)
                        job.media_source_ids[engine] = media_source_id
                    await self._async_play_media_source(
                        job, player, media_source_id, ()
                    )
                except JobCancelled:
                    raise
                except asyncio.CancelledError:
                    raise
                except Exception as err:  # noqa: BLE001
                    errors.append(f"{engine}: {err}")
                    await self._async_stop_player(player)
                    self._record_channel_failure(job, channel, err)
                    continue
                self._record_channel_success(job, channel)
                return
            raise HomeAssistantError(
                f"Every selected TTS engine failed on {player}: "
                + "; ".join(errors)
            )

        pending = list(players)
        timeout = self._availability_timeout
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while pending:
            self._raise_if_cancelled(job)
            ready = [
                player
                for player in pending
                if (
                    (state := self.hass.states.get(player)) is not None
                    and state.state not in {STATE_UNAVAILABLE, STATE_UNKNOWN}
                )
            ]
            for player in ready:
                try:
                    await deliver(player)
                except JobCancelled:
                    raise
                except asyncio.CancelledError:
                    raise
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug(
                        "Direct room TTS output %s failed during availability window: %s",
                        player,
                        err,
                    )
                    continue
                pending.remove(player)
            if not pending or timeout <= 0 or loop.time() >= deadline:
                break
            await asyncio.sleep(min(0.1, max(0.0, deadline - loop.time())))

        if pending:
            _LOGGER.debug(
                "Announcement %s skipped unavailable direct TTS player(s) after %ss: %s",
                job.job_id,
                f"{timeout:g}",
                pending,
            )

'''
p.write_text(text.replace(anchor,direct+anchor,1),encoding="utf-8")

# Shared server player is always global; remove old area rejection branch when no snapcast.
rep(p,
'''        if not job.snapcast_clients:
            player_area = job.tts_player_area
            if job.outputs and player_area is not None and player_area not in set(
                job.outputs
            ):
                self._record_channel_failure(
                    job,
                    f"player:{player}",
                    "The TTS media player does not belong to the requested area",
                )
                return
            if not await self._async_wait_player_available(player, job):
''',
'''        if not job.snapcast_clients:
            if not await self._async_wait_player_available(player, job):
''')

# Prefetch direct room TTS too.
rep(p,
'''        if not job.tts_text or not job.server_tts_enabled or not job.tts_engines:
            return
''',
'''        if (
            not job.tts_text
            or not job.tts_engines
            or not (job.server_tts_enabled or job.room_tts_players)
        ):
            return
''')

# __init__.py response
p=C/"__init__.py"
rep(p,
'    CONF_TTS_MIN_LEVEL,\n',
'    CONF_TTS_MIN_LEVEL,\n    CONF_TTS_ROOM_PLAYERS,\n'
)
rep(p,
'''    migrated.setdefault(CONF_COMPANION_TTS_OUTPUTS, [])
    migrated.setdefault(CONF_NOTIFY_PROFILES, {})
''',
'''    migrated.setdefault(CONF_COMPANION_TTS_OUTPUTS, [])
    migrated.setdefault(CONF_TTS_ROOM_PLAYERS, [])
    migrated.setdefault(CONF_NOTIFY_PROFILES, {})
''')
rep(p,
'''            "notify_outputs": list(job.notify_outputs),
            "snapcast_clients": list(job.snapcast_clients),
''',
'''            "notify_outputs": list(job.notify_outputs),
            "room_tts_players": list(job.room_tts_players),
            "snapcast_clients": list(job.snapcast_clients),
''')

# translations/resources
locales={
"strings.json":{
"title":"Text-to-speech routing",
"desc":"Choose the TTS engine and keep direct room playback separate from the shared synchronized-server path.",
"eng":"TTS engines",
"room":"Direct room TTS media players",
"roomd":"Area-bound media players (for example voice assistants/speakers) that receive the generated TTS directly. Occupancy filters these players by their Home Assistant area.",
"shared":"Shared TTS server media player",
"sharedd":"Global transport player such as MPD. It feeds the synchronized audio server and is never area-filtered.",
"route":"Synchronized room routing players (Snapcast)",
"routed":"Area-bound Snapcast clients fed by the shared server player. Announcement Hub does not play TTS directly on them; it only manages their mute/routing state.",
},
"translations/en.json":{
"title":"Text-to-speech routing","desc":"Choose the TTS engine and keep direct room playback separate from the shared synchronized-server path.","eng":"TTS engines","room":"Direct room TTS media players","roomd":"Area-bound media players (for example voice assistants/speakers) that receive the generated TTS directly. Occupancy filters these players by their Home Assistant area.","shared":"Shared TTS server media player","sharedd":"Global transport player such as MPD. It feeds the synchronized audio server and is never area-filtered.","route":"Synchronized room routing players (Snapcast)","routed":"Area-bound Snapcast clients fed by the shared server player. Announcement Hub does not play TTS directly on them; it only manages their mute/routing state."},
"translations/de.json":{
"title":"Text-zu-Sprache-Routing","desc":"Wähle die TTS-Engine und trenne direkte Raumausgabe vom gemeinsamen synchronisierten Serverpfad.","eng":"TTS-Engines","room":"Direkte TTS-Mediaplayer pro Raum","roomd":"Bereichsgebundene Mediaplayer (z. B. Sprachassistenten/Lautsprecher), die das erzeugte TTS direkt wiedergeben. Die Belegung filtert diese Player nach ihrem Home-Assistant-Bereich.","shared":"Gemeinsamer TTS-Server-Mediaplayer","sharedd":"Globaler Transport-Player wie MPD. Er speist den synchronisierten Audioserver und wird niemals nach Bereich gefiltert.","route":"Synchronisierte Raum-Routing-Player (Snapcast)","routed":"Bereichsgebundene Snapcast-Clients, die vom gemeinsamen Server-Player gespeist werden. Announcement Hub spielt TTS nicht direkt auf ihnen ab, sondern verwaltet nur Mute/Routing."},
"translations/el.json":{
"title":"Δρομολόγηση μετατροπής κειμένου σε ομιλία","desc":"Επίλεξε τη μηχανή TTS και κράτησε ξεχωριστή την άμεση αναπαραγωγή ανά δωμάτιο από την κοινή συγχρονισμένη διαδρομή server.","eng":"Μηχανές TTS","room":"Άμεσοι media players TTS ανά δωμάτιο","roomd":"Media players δεμένοι σε περιοχή (π.χ. voice assistants/ηχεία) που λαμβάνουν απευθείας το παραγόμενο TTS. Η παρουσία τους φιλτράρει σύμφωνα με την περιοχή Home Assistant.","shared":"Κοινός media player server για TTS","sharedd":"Καθολικός transport player όπως το MPD. Τροφοδοτεί τον συγχρονισμένο audio server και δεν φιλτράρεται ποτέ ανά περιοχή.","route":"Συγχρονισμένοι room routing players (Snapcast)","routed":"Snapcast clients δεμένοι σε περιοχή και τροφοδοτούμενοι από τον κοινό server player. Το Announcement Hub δεν στέλνει TTS απευθείας σε αυτούς· διαχειρίζεται μόνο mute/routing."},
}
for rel,L in locales.items():
    q=C/rel
    data=json.loads(q.read_text(encoding="utf-8"))
    for sec in ("config","options"):
        outputs=data[sec]["step"]["outputs"]
        outputs["data"].pop("snapcast_outputs",None)
        outputs["data_description"].pop("snapcast_outputs",None)
        tts=data[sec]["step"]["tts"]
        tts["title"]=L["title"]
        tts["description"]=L["desc"]
        tts["data"]["tts_engines"]=L["eng"]
        # Rebuild insertion order for the three playback roles.
        new_data={}
        for key,val in tts["data"].items():
            new_data[key]=val
            if key=="tts_engines":
                new_data["tts_room_players"]=L["room"]
                new_data["tts_media_player"]=L["shared"]
                new_data["snapcast_outputs"]=L["route"]
        # old tts_media_player was already added later; remove duplicate by rebuild.
        seen={}
        for key,val in new_data.items():
            seen[key]=val
        tts["data"]=seen
        desc=tts["data_description"]
        desc["tts_room_players"]=L["roomd"]
        desc["tts_media_player"]=L["sharedd"]
        desc["snapcast_outputs"]=L["routed"]
    q.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

# Manifest.
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.5.4":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.6.0"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# Tests.
res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8")
text=text.replace('assert manifest["version"] == "0.5.4"','assert manifest["version"] == "0.6.0"')
text=text.replace('"tts_engines",\n        "tts_min_level",','"tts_engines",\n        "tts_room_players",\n        "tts_min_level",')
res.write_text(text,encoding="utf-8")

(ROOT/"tests"/"test_tts_routing_roles.py").write_text('''"""Contracts for the three distinct server/direct TTS routing roles."""

from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_setup_distinguishes_direct_shared_and_routing_players() -> None:
    strings=json.loads((C/"strings.json").read_text())
    for section in ("config","options"):
        outputs=strings[section]["step"]["outputs"]["data"]
        tts=strings[section]["step"]["tts"]["data"]
        assert "snapcast_outputs" not in outputs
        assert "tts_room_players" in tts
        assert "tts_media_player" in tts
        assert "snapcast_outputs" in tts


def test_direct_room_players_are_area_bound_but_shared_player_is_global() -> None:
    manager=(C/"manager.py").read_text()
    assert "room_tts_player_areas" in manager
    assert "def _job_has_ready_room_tts(" in manager
    assert "entity_area_id(self.hass, job.tts_media_player)" not in manager[
        manager.index("def _job_has_ready_server_tts"):
        manager.index("def _job_runnable_now")
    ]
    assert "server_tts_enabled = bool(routed_selected[3])" in manager


def test_snapcast_clients_remain_routing_only() -> None:
    manager=(C/"manager.py").read_text()
    server=manager[
        manager.index("async def _async_send_server_tts"):
        manager.index("async def _async_play_server_round")
    ]
    assert "_snapcast_output_available" in server
    assert "_async_play_server_round" in server
    direct=manager[
        manager.index("async def _async_send_room_tts"):
        manager.index("async def _async_send_server_tts")
    ]
    assert "_async_play_media_source" in direct
    assert "job.room_tts_players" in direct


def test_new_role_model_keeps_startup_safe_tasks() -> None:
    manager=(C/"manager.py").read_text()
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(")==2
''',encoding="utf-8")

# Changelog.
ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.6.0 - 2026-10-02

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

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied Announcement Hub 0.6.0 three-role TTS routing")
