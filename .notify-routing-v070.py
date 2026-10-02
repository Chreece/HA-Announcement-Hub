from pathlib import Path
import json

ROOT=Path(".")
C=ROOT/"custom_components"/"announcement_hub"

def rep(path, old, new):
    text=path.read_text(encoding="utf-8")
    count=text.count(old)
    if count!=1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old,new,1),encoding="utf-8")

# const.py
p=C/"const.py"
rep(p,'VERSION: Final = "0.6.0"','VERSION: Final = "0.7.0"')
rep(p,
'CONF_NOTIFY_PROFILES: Final = "notify_profiles"\n',
'CONF_NOTIFY_PROFILES: Final = "notify_profiles"\n'
'CONF_NOTIFY_POLICIES: Final = "notify_policies"\n'
)
rep(p,
'DEFAULT_NOTIFY_REPLACE_PARTS: Final = True\n',
'DEFAULT_NOTIFY_REPLACE_PARTS: Final = True\n'
'NOTIFY_POLICY_SCOPE: Final = "scope"\n'
'NOTIFY_POLICY_MIN_LEVEL: Final = "min_level"\n'
'NOTIFY_SCOPE_ROOM: Final = "room"\n'
'NOTIFY_SCOPE_GENERAL: Final = "general"\n'
'NOTIFY_SCOPES: Final = (NOTIFY_SCOPE_ROOM, NOTIFY_SCOPE_GENERAL)\n'
'NOTIFY_MIN_LEVELS: Final = (\n'
'    LEVEL_DEBUG,\n'
'    LEVEL_INFO,\n'
'    LEVEL_WARNING,\n'
'    LEVEL_ERROR,\n'
'    LEVEL_CRITICAL,\n'
')\n'
'DEFAULT_NOTIFY_MIN_LEVEL: Final = LEVEL_DEBUG\n'
)

# config_flow.py imports
p=C/"config_flow.py"
rep(p,
'    CONF_NOTIFY_OUTPUTS,\n    CONF_NOTIFY_PROFILES,\n',
'    CONF_NOTIFY_OUTPUTS,\n'
'    CONF_NOTIFY_POLICIES,\n'
'    CONF_NOTIFY_PROFILES,\n'
)
rep(p,
'    DEFAULT_IDLE_TIMEOUT,\n',
'    DEFAULT_IDLE_TIMEOUT,\n'
'    DEFAULT_NOTIFY_MIN_LEVEL,\n'
)
rep(p,
'    NAME,\n    TTS_MIN_LEVELS,\n',
'    NAME,\n'
'    NOTIFY_MIN_LEVELS,\n'
'    NOTIFY_POLICY_MIN_LEVEL,\n'
'    NOTIFY_POLICY_SCOPE,\n'
'    NOTIFY_SCOPES,\n'
'    NOTIFY_SCOPE_GENERAL,\n'
'    NOTIFY_SCOPE_ROOM,\n'
'    TTS_MIN_LEVELS,\n'
)
rep(p,
'''    notify_output_options,
    resolve_notify_outputs,
''',
'''    notify_output_options,
    area_name,
    resolve_notify_outputs,
''')

# flow state declarations
rep(p,
'''    _notify_profile_domains: list[str]
    _notify_profile_index: int
''',
'''    _notify_route_outputs: list[Any]
    _notify_route_index: int
    _notify_profile_domains: list[str]
    _notify_profile_index: int
''')

# outputs transitions into per-device notification routing.
rep(p,
'''            self._prepare_notify_profile_steps()
            return await self.async_step_notification_profile()
''',
'''            self._prepare_notify_routing_steps()
            return await self.async_step_notification_routing()
''')

# Insert routing step before integration visual profile preparation.
anchor='''    def _prepare_notify_profile_steps(self) -> None:
'''
text=p.read_text(encoding="utf-8")
if anchor not in text:
    raise SystemExit("notification profile anchor missing")
routing='''    def _prepare_notify_routing_steps(self) -> None:
        refs = expand_notify_output_tokens(
            self.hass,
            list(self._working.get(CONF_NOTIFY_OUTPUTS, [])),
        )
        self._notify_route_outputs = sorted(
            resolve_notify_outputs(self.hass, refs),
            key=lambda output: (
                output.entity_id or output.service or output.ref
            ).casefold(),
        )
        configured = self._working.get(CONF_NOTIFY_POLICIES, {})
        if not isinstance(configured, dict):
            configured = {}
        active_refs = {output.ref for output in self._notify_route_outputs}
        self._working[CONF_NOTIFY_POLICIES] = {
            ref: dict(policy)
            for ref, policy in configured.items()
            if ref in active_refs and isinstance(policy, dict)
        }
        self._notify_route_index = 0

    async def async_step_notification_routing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure room/general scope and minimum level per notify device."""
        if self._notify_route_index >= len(self._notify_route_outputs):
            self._prepare_notify_profile_steps()
            return await self.async_step_notification_profile()

        output = self._notify_route_outputs[self._notify_route_index]
        policies = dict(self._working.get(CONF_NOTIFY_POLICIES, {}) or {})
        saved = policies.get(output.ref, {})
        if not isinstance(saved, dict):
            saved = {}

        default_scope = (
            NOTIFY_SCOPE_ROOM if output.area_id else NOTIFY_SCOPE_GENERAL
        )
        current_scope = str(
            saved.get(NOTIFY_POLICY_SCOPE, default_scope)
        )
        if current_scope not in NOTIFY_SCOPES:
            current_scope = default_scope
        current_level = str(
            saved.get(NOTIFY_POLICY_MIN_LEVEL, DEFAULT_NOTIFY_MIN_LEVEL)
        )
        if current_level not in NOTIFY_MIN_LEVELS:
            current_level = DEFAULT_NOTIFY_MIN_LEVEL

        errors: dict[str, str] = {}
        if user_input is not None:
            scope = str(user_input[NOTIFY_POLICY_SCOPE])
            minimum_level = str(user_input[NOTIFY_POLICY_MIN_LEVEL])
            if scope == NOTIFY_SCOPE_ROOM and output.area_id is None:
                errors["base"] = "room_notify_area_required"
            else:
                policies[output.ref] = {
                    NOTIFY_POLICY_SCOPE: scope,
                    NOTIFY_POLICY_MIN_LEVEL: minimum_level,
                }
                self._working[CONF_NOTIFY_POLICIES] = policies
                self._notify_route_index += 1
                return await self.async_step_notification_routing()

        label = output.entity_id or output.service or output.ref
        return self.async_show_form(
            step_id="notification_routing",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        NOTIFY_POLICY_SCOPE,
                        default=current_scope,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(NOTIFY_SCOPES),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="notify_scope",
                        )
                    ),
                    probatio.Required(
                        NOTIFY_POLICY_MIN_LEVEL,
                        default=current_level,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(NOTIFY_MIN_LEVELS),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="notify_level",
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "output": label,
                "area": area_name(self.hass, output.area_id),
            },
        )

'''
p.write_text(text.replace(anchor,routing+anchor,1),encoding="utf-8")

# init state in both config + options flows
text=p.read_text(encoding="utf-8")
old='''        self._working = {}
        self._notify_profile_domains = []
        self._notify_profile_index = 0
'''
new='''        self._working = {}
        self._notify_route_outputs = []
        self._notify_route_index = 0
        self._notify_profile_domains = []
        self._notify_profile_index = 0
'''
if text.count(old)!=2:
    raise SystemExit(f"config_flow init block expected 2, found {text.count(old)}")
p.write_text(text.replace(old,new,2),encoding="utf-8")

# Queue validation must recognize direct room TTS-only setups too.
rep(p,
'''            has_server_tts = bool(
                self._working.get(CONF_TTS_ENGINES)
                and self._working.get(CONF_TTS_MEDIA_PLAYER)
            )
            if not (
                self._working.get(CONF_NOTIFY_OUTPUTS)
                or self._working.get(CONF_COMPANION_TTS_OUTPUTS)
                or has_server_tts
            ):
''',
'''            has_tts = bool(
                self._working.get(CONF_TTS_ENGINES)
                and (
                    self._working.get(CONF_TTS_MEDIA_PLAYER)
                    or self._working.get(CONF_TTS_ROOM_PLAYERS)
                )
            )
            if not (
                self._working.get(CONF_NOTIFY_OUTPUTS)
                or self._working.get(CONF_COMPANION_TTS_OUTPUTS)
                or has_tts
            ):
''')

# manager.py imports
p=C/"manager.py"
rep(p,
'    CONF_NOTIFY_OUTPUTS,\n    CONF_NOTIFY_PROFILES,\n',
'    CONF_NOTIFY_OUTPUTS,\n'
'    CONF_NOTIFY_POLICIES,\n'
'    CONF_NOTIFY_PROFILES,\n'
)
rep(p,
'    DEFAULT_IDLE_TIMEOUT,\n',
'    DEFAULT_IDLE_TIMEOUT,\n'
'    DEFAULT_NOTIFY_MIN_LEVEL,\n'
)
rep(p,
'    LEVEL_CRITICAL,\n',
'    LEVEL_CRITICAL,\n'
'    LEVEL_INFO,\n'
'    LEVEL_PRIORITY,\n'
'    NOTIFY_MIN_LEVELS,\n'
'    NOTIFY_POLICY_MIN_LEVEL,\n'
'    NOTIFY_POLICY_SCOPE,\n'
'    NOTIFY_SCOPE_GENERAL,\n'
'    NOTIFY_SCOPE_ROOM,\n'
)

# Insert notification policy helpers before async_enqueue.
anchor='''    async def async_enqueue(
'''
text=p.read_text(encoding="utf-8")
if anchor not in text:
    raise SystemExit("async_enqueue anchor missing")
helper='''    def _notify_policy(
        self,
        output: NotifyOutput,
    ) -> tuple[str, str]:
        """Return normalized scope/minimum-level policy for one notify output."""
        configured = self.settings.get(CONF_NOTIFY_POLICIES, {})
        raw: Mapping[str, Any] = {}
        if isinstance(configured, Mapping):
            candidate = configured.get(output.ref, {})
            if isinstance(candidate, Mapping):
                raw = candidate

        default_scope = (
            NOTIFY_SCOPE_ROOM if output.area_id else NOTIFY_SCOPE_GENERAL
        )
        scope = str(raw.get(NOTIFY_POLICY_SCOPE, default_scope))
        if scope not in {NOTIFY_SCOPE_ROOM, NOTIFY_SCOPE_GENERAL}:
            scope = default_scope

        minimum = str(
            raw.get(NOTIFY_POLICY_MIN_LEVEL, DEFAULT_NOTIFY_MIN_LEVEL)
        )
        if minimum not in NOTIFY_MIN_LEVELS:
            minimum = DEFAULT_NOTIFY_MIN_LEVEL
        return scope, minimum

    @staticmethod
    def _notify_level_allowed(level: str, minimum: str) -> bool:
        """Return whether this announcement reaches a notification output."""
        return LEVEL_PRIORITY.get(level, LEVEL_PRIORITY[LEVEL_INFO]) >= (
            LEVEL_PRIORITY.get(minimum, LEVEL_PRIORITY[DEFAULT_NOTIFY_MIN_LEVEL])
        )

'''
p.write_text(text.replace(anchor,helper+anchor,1),encoding="utf-8")

# Filter notification records by their own minimum level immediately after resolving.
rep(p,
'''        all_notify_records = resolve_notify_outputs(self.hass, base_selected[1])
        all_room_tts_players = tuple(base_selected[2])
''',
'''        all_notify_records = tuple(
            output
            for output in resolve_notify_outputs(self.hass, base_selected[1])
            if self._notify_level_allowed(
                level,
                self._notify_policy(output)[1],
            )
        )
        all_room_tts_players = tuple(base_selected[2])
''')

# Occupancy filter only room-scoped notify outputs; general outputs bypass areas.
rep(p,
'''                routed_notify = tuple(
                    output
                    for output in all_notify_records
                    if output.area_id is not None
                    and output.area_id in effective_areas
                )
''',
'''                routed_notify = tuple(
                    output
                    for output in all_notify_records
                    if (
                        self._notify_policy(output)[0] == NOTIFY_SCOPE_GENERAL
                        or (
                            output.area_id is not None
                            and output.area_id in effective_areas
                        )
                    )
                )
''')

# Freeze general notification outputs with no area binding.
rep(p,
'''        notify_output_areas = {
            output.ref: output.area_id for output in notify_records
        }
''',
'''        notify_output_areas = {
            output.ref: (
                None
                if self._notify_policy(output)[0] == NOTIFY_SCOPE_GENERAL
                else output.area_id
            )
            for output in notify_records
        }
''')

# __init__.py migration/defaults.
p=C/"__init__.py"
rep(p,
'    CONF_NOTIFY_OUTPUTS,\n    CONF_NOTIFY_PROFILES,\n',
'    CONF_NOTIFY_OUTPUTS,\n'
'    CONF_NOTIFY_POLICIES,\n'
'    CONF_NOTIFY_PROFILES,\n'
)
text=p.read_text(encoding="utf-8")
if text.count('    migrated.setdefault(CONF_NOTIFY_PROFILES, {})\n') != 2:
    raise SystemExit(
        f"{p}: expected two notify profile migration defaults, found "
        f"{text.count('    migrated.setdefault(CONF_NOTIFY_PROFILES, {})\\n')}"
    )
p.write_text(
    text.replace(
        '    migrated.setdefault(CONF_NOTIFY_PROFILES, {})\n',
        '    migrated.setdefault(CONF_NOTIFY_POLICIES, {})\n'
        '    migrated.setdefault(CONF_NOTIFY_PROFILES, {})\n',
        2,
    ),
    encoding="utf-8",
)

# diagnostics: redact policy map with entity refs too.
p=C/"diagnostics.py"
rep(p,
'    CONF_CRITICAL_NOTIFY_DATA,\n    CONF_NOTIFY_PROFILES,\n',
'    CONF_CRITICAL_NOTIFY_DATA,\n'
'    CONF_NOTIFY_POLICIES,\n'
'    CONF_NOTIFY_PROFILES,\n'
)
rep(p,
'''    CONF_NOTIFY_PROFILES,
    CONF_TTS_OPTIONS,
''',
'''    CONF_NOTIFY_POLICIES,
    CONF_NOTIFY_PROFILES,
    CONF_TTS_OPTIONS,
''')

# translations
locales={
"strings.json":{
"title":"Notification routing: {output}",
"desc":"Choose whether {output} follows room occupancy ({area}) or is a general movable device, and set the minimum announcement level it should receive.",
"scope":"Device scope","level":"Minimum notification level",
"room":"Room-based","general":"General / movable",
"debug":"Debug","info":"Info / success","warning":"Warning","error":"Error","critical":"Critical",
"areaerr":"A room-based notification output must have a Home Assistant area. Assign an area to this device/entity or choose General / movable."
},
"translations/en.json":{
"title":"Notification routing: {output}","desc":"Choose whether {output} follows room occupancy ({area}) or is a general movable device, and set the minimum announcement level it should receive.","scope":"Device scope","level":"Minimum notification level","room":"Room-based","general":"General / movable","debug":"Debug","info":"Info / success","warning":"Warning","error":"Error","critical":"Critical","areaerr":"A room-based notification output must have a Home Assistant area. Assign an area to this device/entity or choose General / movable."
},
"translations/de.json":{
"title":"Benachrichtigungsrouting: {output}","desc":"Lege fest, ob {output} der Raumbelegung ({area}) folgt oder ein allgemeines mobiles Gerät ist, und ab welcher Meldungsstufe es Benachrichtigungen erhält.","scope":"Gerätebereich","level":"Minimale Benachrichtigungsstufe","room":"Raumgebunden","general":"Allgemein / mobil","debug":"Debug","info":"Info / Erfolg","warning":"Warnung","error":"Fehler","critical":"Kritisch","areaerr":"Ein raumgebundener Benachrichtigungsausgang benötigt einen Home-Assistant-Bereich. Weise dem Gerät/der Entität einen Bereich zu oder wähle Allgemein / mobil."
},
"translations/el.json":{
"title":"Δρομολόγηση ειδοποιήσεων: {output}","desc":"Επίλεξε αν το {output} ακολουθεί την παρουσία του δωματίου ({area}) ή είναι γενική/κινητή συσκευή και όρισε το ελάχιστο επίπεδο ανακοινώσεων που θα λαμβάνει.","scope":"Εμβέλεια συσκευής","level":"Ελάχιστο επίπεδο ειδοποίησης","room":"Ανά δωμάτιο","general":"Γενική / κινητή","debug":"Αποσφαλμάτωση","info":"Πληροφορία / επιτυχία","warning":"Προειδοποίηση","error":"Σφάλμα","critical":"Κρίσιμο","areaerr":"Μια ειδοποίηση ανά δωμάτιο πρέπει να έχει περιοχή στο Home Assistant. Ανάθεσε περιοχή στη συσκευή/οντότητα ή επίλεξε Γενική / κινητή."
},
}
for rel,L in locales.items():
    q=C/rel
    data=json.loads(q.read_text(encoding="utf-8"))
    for sec in ("config","options"):
        steps=data[sec]["step"]
        steps["notification_routing"]={
            "title":L["title"],
            "description":L["desc"],
            "data":{
                "scope":L["scope"],
                "min_level":L["level"],
            },
            "data_description":{
                "scope":L["scope"],
                "min_level":L["level"],
            },
        }
    for sec in ("config","options"):
        data[sec].setdefault("error",{})
        data[sec]["error"]["room_notify_area_required"]=L["areaerr"]
    selector_block=data.setdefault("selector",{})
    selector_block["notify_scope"]={
        "options":{
            "room":L["room"],
            "general":L["general"],
        }
    }
    selector_block["notify_level"]={
        "options":{
            "debug":L["debug"],
            "info":L["info"],
            "warning":L["warning"],
            "error":L["error"],
            "critical":L["critical"],
        }
    }
    q.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

# manifest
p=C/"manifest.json"
j=json.loads(p.read_text(encoding="utf-8"))
if j.get("version")!="0.6.0":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.7.0"
p.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# tests
p=ROOT/"tests"/"test_resources.py"
text=p.read_text(encoding="utf-8")
text=text.replace(
    'expected_steps = {"outputs", "notification_profile", "tts", "snapcast", "occupancy", "occupancy_source", "queue"}',
    'expected_steps = {"outputs", "notification_routing", "notification_profile", "tts", "snapcast", "occupancy", "occupancy_source", "queue"}',
)
text=text.replace(
    'assert manifest["version"] == "0.6.0"',
    'assert manifest["version"] == "0.7.0"',
)
p.write_text(text,encoding="utf-8")

(ROOT/"tests"/"test_notify_routing_policy.py").write_text('''"""Contracts for per-device notification scope and log-level routing."""

from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"custom_components"/"announcement_hub"


def test_setup_has_per_concrete_output_notification_routing_step() -> None:
    flow=(C/"config_flow.py").read_text()
    assert "def _prepare_notify_routing_steps(" in flow
    assert "async def async_step_notification_routing(" in flow
    assert "CONF_NOTIFY_POLICIES" in flow
    assert 'translation_key="notify_scope"' in flow
    assert 'translation_key="notify_level"' in flow


def test_runtime_filters_level_and_only_room_scope_by_occupancy() -> None:
    manager=(C/"manager.py").read_text()
    assert "def _notify_policy(" in manager
    assert "def _notify_level_allowed(" in manager
    assert "NOTIFY_SCOPE_GENERAL" in manager
    assert "LEVEL_PRIORITY.get(level" in manager
    assert "self._notify_policy(output)[0] == NOTIFY_SCOPE_GENERAL" in manager


def test_general_outputs_freeze_without_area_binding() -> None:
    manager=(C/"manager.py").read_text()
    assert "None" in manager[
        manager.index("notify_output_areas = {"):
        manager.index("configured_profiles =", manager.index("notify_output_areas = {"))
    ]


def test_existing_outputs_have_backward_compatible_policy_defaults() -> None:
    manager=(C/"manager.py").read_text()
    assert "NOTIFY_SCOPE_ROOM if output.area_id else NOTIFY_SCOPE_GENERAL" in manager
    assert "DEFAULT_NOTIFY_MIN_LEVEL" in manager


def test_translations_expose_scope_and_level_choices() -> None:
    strings=json.loads((C/"strings.json").read_text())
    for section in ("config","options"):
        assert "notification_routing" in strings[section]["step"]
    assert set(strings["selector"]["notify_scope"]["options"])=={"room","general"}
    assert set(strings["selector"]["notify_level"]["options"])=={
        "debug","info","warning","error","critical"
    }
''',encoding="utf-8")

# changelog
p=ROOT/"CHANGELOG.md"
text=p.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.7.0 - 2026-10-02

- Added per-device visual notification routing policies in setup.
- Every concrete notify output now has an explicit Room-based or General/movable
  scope plus its own minimum announcement level.
- Room-based outputs follow occupied-area and fallback-room routing.
- General/movable outputs bypass occupancy area filtering and can notify
  regardless of the currently occupied room.
- Notification level thresholds are debug, info/success, warning, error, and
  critical; success shares info priority.
- Policies are applied before a job is frozen so queued jobs keep deterministic
  output membership even if settings change later.
- Existing outputs default to Room-based when they have an HA area and General
  when they do not, with debug as the backward-compatible minimum level.

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
p.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied Announcement Hub 0.7.0 per-device notification routing")
