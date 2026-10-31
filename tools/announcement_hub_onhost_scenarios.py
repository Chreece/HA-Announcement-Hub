#!/usr/bin/env python3
"""Read-only Home Assistant host check for Announcement Hub.

Uses the installed manager.py for synthetic routing tests; never invokes an
HA service or modifies device states. Does not export secrets, prompts,
notification text, or raw logs. Optional HASS_TOKEN adds live API state reads.
"""
from __future__ import annotations

import ast
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from types import SimpleNamespace
from urllib.request import Request, urlopen

UTC = timezone.utc
STAMP = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
SIGNALS = {
    "slow_ai": "has not responded after",
    "failed_delivery": "had no successful output",
    "stuck_audio": "remained busy for",
    "tts_start_failure": "TTS playback did not start",
    "failed_worker": "Room delivery task failed",
    "snapcast_drift": "route drift",
    "queue_full": "queue is full",
}
SAFE_KEYS = (
    "occupancy_sensor", "occupancy_attribute", "sleep_rooms_entity",
    "sleep_rooms_attribute", "sleep_mute_tts", "sleep_fallback_written",
    "fallback_room", "fallback_check_door", "output_availability_timeout",
    "idle_timeout", "start_timeout", "playback_timeout", "post_play_delay",
    "tts_min_level", "channel_fallback_mode",
)

def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}

def config_path():
    override = os.environ.get("AH_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    try:
        x = subprocess.run(["docker", "inspect", "homeassistant"], capture_output=True,
                           text=True, timeout=6, check=False)
        if x.returncode == 0:
            for mount in json.loads(x.stdout)[0].get("Mounts", []):
                if mount.get("Destination") == "/config":
                    path = Path(mount["Source"])
                    if path.is_dir():
                        return path
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        pass
    for candidate in (Path.home() / "homeassistant/config",
                      Path("/home/chreece/homeassistant/config"), Path("/config")):
        if (candidate / ".storage").is_dir():
            return candidate
    return None

class ScenarioHost:
    def __init__(self):
        self.occupied = ("a",)
        self.sleeping = frozenset()
        self.settings = {"sleep_mute_tts": True, "person_area_enabled": {}}
        self._queue = deque()
        self._wake = SimpleNamespace(set=lambda: None)
        self._availability_timeout = 5.
    def _occupied_area_ids(self): return self.occupied
    def _sleep_area_ids(self): return self.sleeping
    def _all_occupied_rooms_sleeping(self):
        return bool(self.occupied and set(self.occupied).issubset(self.sleeping))
    def _fallback_area_id(self): return "relay"
    def _fallback_door_allows(self, areas): return self.door_open
    def _schedule_save(self): pass
    def _notify_update(self): pass
    def _schedule_prefetch(self, job): pass
    def _prepare_staged_route(self, job):
        job.outputs = self._staged_areas(job, job.routing_stage)
        return bool(job.outputs)
    def _job_runnable_now(self, job): return bool(job.outputs)
    def _routing_stage_age(self, job): return 0.
    def _advance_staged_route(self, job, reason):
        stages = ("primary", "occupied", "fallback", "general")
        job.routing_stage = stages[min(stages.index(job.routing_stage)+1, 3)]
        job.routing_stage_started_at = datetime.now(UTC).isoformat()
    door_open = True

def job(stage="primary"):
    ts = datetime.now(UTC).isoformat()
    return SimpleNamespace(
        job_id="synthetic", created_at=ts, routing_mode="room_fallback",
        routing_stage=stage, routing_stage_started_at=ts,
        routing_seen_occupied=None, routing_history=[], routing_retry_after=None,
        routing_audio_retry=False, routing_channel_retry=None,
        occupancy_requested=True, preferred_areas=("a",), outputs=("a",),
        status="pending", started_at=None, finished_at=None, error=None,
        channel_errors={}, successful_channels=[], ai={"pending_preprocessing": False},
        text_tts="[synthetic only]", text_notify="[synthetic only]")

def scenarios(path):
    results = {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        manager = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                       and n.name == "AnnouncementManager")
        methods = {n.name: n for n in manager.body if isinstance(n, ast.FunctionDef)}
        ns = {
            "CONF_SLEEP_MUTE_TTS": "sleep_mute_tts", "DEFAULT_SLEEP_MUTE_TTS": True,
            "RoomRouteMoved": type("RoomRouteMoved", (RuntimeError,), {}),
            "utcnow_iso": lambda: datetime.now(UTC).isoformat(),
            "datetime": datetime, "UTC": UTC,
            "STAGES": ("primary", "occupied", "fallback", "general"),
        }
        for name in ("_staged_areas", "_room_route_moved", "_assert_live_room_route",
                     "_requeue_after_room_move", "_staged_route_ready",
                     "_sleep_tts_muted_now"):
            m = ast.fix_missing_locations(ast.Module(body=[methods[name]], type_ignores=[]))
            exec(compile(m, str(path), "exec"), ns)
            setattr(ScenarioHost, name, ns[name])
    except Exception as e:
        return {"source": "installed_manager_AST", "error": type(e).__name__}
    def test(name, fn):
        try:
            results[name] = "PASS" if fn() else "FAIL"
        except Exception as e:
            results[name] = "ERROR:" + type(e).__name__
    h = ScenarioHost()
    j = job()
    test("occupied_target_preferred", lambda: h._staged_areas(j, "primary") == ("a",))
    h.occupied = ("b",)
    test("empty_target_skipped", lambda: h._staged_areas(j, "primary") == ())
    test("new_occupied_room_selected", lambda: h._staged_areas(j, "occupied") == ("b",))
    test("stale_speaker_detected", lambda: h._room_route_moved(j, ("a",)))
    def rejected():
        try: h._assert_live_room_route(j, ("a",))
        except ns["RoomRouteMoved"]: return True
        return False
    test("physical_output_guard", rejected)
    h._requeue_after_room_move(j, "simulated movement")
    test("durable_requeue_no_AI_repeat", lambda:
         list(h._queue) == [j] and not j.ai["pending_preprocessing"]
         and j.routing_stage == "primary" and j.routing_seen_occupied == ("b",))
    j = job("fallback")
    j.outputs = ("relay",)
    test("fallback_blocked_empty_original", lambda: h._staged_areas(j, "fallback") == ())
    h.occupied = ("a",)
    test("fallback_allowed_original_occupied_door_open",
         lambda: h._staged_areas(j, "fallback") == ("relay",))
    h.door_open = False
    test("fallback_blocked_closed_door", lambda: h._staged_areas(j, "fallback") == ())
    h.door_open = True
    h.sleeping = frozenset(("a",))
    test("sleep_mutes_physical_routes",
         lambda: h._sleep_tts_muted_now() and h._staged_areas(j, "primary") == ())
    h.settings["sleep_mute_tts"] = False
    test("sleep_mute_disabled_restores_route",
         lambda: not h._sleep_tts_muted_now() and h._staged_areas(j, "primary") == ("a",))
    h.settings["sleep_mute_tts"] = True
    h.sleeping = frozenset()
    h.occupied = ("b",)
    j = job()
    j.routing_mode = "normal"
    test("exact_device_route_unchanged", lambda: not h._room_route_moved(j, ("a",)))
    j.routing_mode = "room_fallback"
    j.occupancy_requested = False
    test("occupied_only_false_unchanged", lambda: not h._room_route_moved(j, ("a",)))
    j = job("general")
    j.routing_seen_occupied = ("a",)
    test("general_wait_rechecks_room_move",
         lambda: h._staged_route_ready(j) and j.routing_stage == "occupied"
         and j.outputs == ("b",))
    return {"source": "installed_manager_AST_no_HA_services",
            "passed": sum(v == "PASS" for v in results.values()),
            "total": len(results), "results": results}

def main():
    out = Path(os.environ.get("AH_LOG_DIR",
               str(Path.home() / "projects/announcement_hub/logs"))).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    root = config_path()
    report = {"run_utc": STAMP, "read_only": True, "config_found": root is not None}
    if root is None:
        report["error"] = "Set AH_CONFIG_DIR=/path/to/homeassistant/config"
    else:
        entries = load(root / ".storage/core.config_entries").get("data", {}).get("entries", [])
        entry = next((e for e in entries if e.get("domain") == "announcement_hub"), {})
        cfg = {**(entry.get("data") or {}), **(entry.get("options") or {})}
        source = root / "custom_components/announcement_hub"
        report["installed_version"] = load(source / "manifest.json").get("version", "missing")
        report["config_entry_found"] = bool(entry)
        report["selected_settings"] = {k: cfg[k] for k in SAFE_KEYS if k in cfg}
        report["configured_output_counts"] = {
            k: len(cfg.get(k) or ()) for k in
            ("notify_outputs", "tts_engines", "tts_room_players",
             "snapcast_outputs", "companion_tts_outputs")}
        store_path = root / ".storage" / (
            "announcement_hub.queue." + entry.get("entry_id", "")
        )
        if not store_path.exists():
            report["host_queue_store_status"] = "missing"
        else:
            try:
                raw_storage = json.loads(store_path.read_text(encoding="utf-8"))
                report["host_queue_store_status"] = (
                    "readable"
                    if isinstance(raw_storage, dict)
                    and isinstance(raw_storage.get("data"), dict)
                    else "unparseable_schema"
                )
            except PermissionError:
                report["host_queue_store_status"] = "PermissionError"
                raw_storage = {}
            except (ValueError, OSError, UnicodeError) as exc:
                report["host_queue_store_status"] = type(exc).__name__
                raw_storage = {}
        if report["host_queue_store_status"] == "missing":
            raw_storage = {}
        stored = raw_storage.get("data", {}) if isinstance(raw_storage, dict) else {}
        queued = stored.get("jobs", []) if isinstance(stored, dict) else []
        report["persisted_queue"] = [
            {"routing_stage": j.get("routing_stage"), "status": j.get("status"),
             "routing_history": (j.get("routing_history") or [])[-3:],
             "ai_status": (j.get("ai") or {}).get("status"),
             "ai_pending": (j.get("ai") or {}).get("pending_preprocessing")}
            for j in queued[:40]]
        report["persisted_queue_count"] = (
            len(queued) if report["host_queue_store_status"] == "readable"
            else None
        )
        last = stored.get("last") or {}
        report["last_job"] = {
            "status": last.get("status"),
            "routing_mode": last.get("routing_mode"),
            "routing_stage": last.get("routing_stage"),
            "successful_output_count": len(last.get("successful_channels") or []),
            "failed_output_count": len(last.get("channel_errors") or {}),
            "ai_status": (last.get("ai") or {}).get("status"),
            "recent_routing": (last.get("routing_history") or [])[-4:],
        }
        report["recent_AI"] = [
            {k: x.get(k) for k in ("status", "elapsed_seconds", "retry_count", "failure_reason")}
            for x in (stored.get("ai_history") or [])[-20:]]
        try:
            logs = subprocess.run(
                ["docker", "logs", "--since", "6h", "--tail", "3500", "homeassistant"],
                capture_output=True, text=True, timeout=12, check=False)
            raw = logs.stdout + "\n" + logs.stderr
            report["log_signals_6h"] = {
                k: raw.casefold().count(pattern.casefold())
                for k, pattern in SIGNALS.items()}
        except (OSError, subprocess.TimeoutExpired):
            report["log_signals_6h"] = {"unavailable": True}
        # A private Home Assistant Store is often mode 0600 inside the
        # container even when the config-entry file is host-readable.
        # Use a read-only Python subprocess INSIDE the existing HA container
        # to distinguish a missing file from an empty queue, and inspect
        # historical recorder samples without requesting an API credential.
        helper = Path(__file__).with_name(
            "announcement_hub_container_evidence.py"
        )
        report["container_probe"] = {"status": "helper_missing"}
        if helper.is_file():
            try:
                result = subprocess.run(
                    ["docker", "exec", "-i", "homeassistant", "python3", "-"],
                    input=helper.read_text(encoding="utf-8"),
                    capture_output=True,
                    text=True,
                    timeout=24,
                    check=False,
                )
                if result.returncode == 0:
                    detail = json.loads(result.stdout)
                    report["container_probe"] = detail
                    item = detail.get("queue_store", {})
                    if item.get("status") == "readable" and "job_count" in item:
                        report["persisted_queue_count"] = item["job_count"]
                        report["queue_store_verified_by_container"] = True
                        report["persisted_queue"] = item.get("pending_summary", [])
                        report["recent_AI"] = item.get("recent_ai", [])
                        report["last_job"] = item.get(
                            "last", {"status": "unverified"}
                        )
                    else:
                        report["queue_store_verified_by_container"] = False
                else:
                    report["container_probe"] = {
                        "status": "docker_probe_failed",
                        "exit_code": result.returncode,
                    }
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                report["container_probe"] = {
                    "status": "docker_probe_unavailable",
                    "error_type": type(exc).__name__,
                }
        if report["persisted_queue_count"] is None:
            report["persisted_queue"] = []
            report["last_job"] = {"status": "unverified"}
            report["recent_AI"] = []

        token = os.environ.get("HASS_TOKEN") or os.environ.get("HA_TOKEN")
        report["current_state"] = {"live_api": False}
        if token:
            try:
                base = os.environ.get("HASS_BASE_URL", "http://127.0.0.1:8123").rstrip("/")
                req = Request(base + "/api/states", headers={"Authorization": "Bearer " + token})
                with urlopen(req, timeout=7) as response:
                    states = json.load(response)
                ids = {x for x in (cfg.get("occupancy_sensor"), cfg.get("sleep_rooms_entity")) if x}
                report["current_state"] = {
                    "live_api": True,
                    "sensors": {
                        s.get("entity_id"): {
                            "status": "available" if s.get("state") not in ("unknown", "unavailable") else "unavailable",
                            "last_updated": s.get("last_updated"),
                            "attribute_found": (
                                (cfg.get("occupancy_attribute") or "") in s.get("attributes", {})
                                if s.get("entity_id") == cfg.get("occupancy_sensor") and cfg.get("occupancy_attribute")
                                else ((cfg.get("sleep_rooms_attribute") or "") in s.get("attributes", {})
                                      if s.get("entity_id") == cfg.get("sleep_rooms_entity") and cfg.get("sleep_rooms_attribute")
                                      else True)),
                        }
                        for s in states if s.get("entity_id") in ids}}
            except Exception as exc:
                report["current_state"] = {"live_api": False, "error_type": type(exc).__name__}
        report["scenarios"] = scenarios(source / "manager.py")
        report["potential_blockers"] = []
        if report["installed_version"] != "0.10.0b25":
            report["potential_blockers"].append("Installed integration is not v0.10.0b25")
        if not entry:
            report["potential_blockers"].append("Announcement Hub config entry not found")
        container_store = (
            report.get("container_probe", {}).get("queue_store", {})
        )
        if report["persisted_queue_count"] is None:
            report["potential_blockers"].append(
                "Persisted queue could not be verified (missing/private storage)"
            )
        if report["last_job"]["status"] in ("failed", "completed_with_errors") or (
            container_store.get("last", {}).get("status")
            in ("failed", "completed_with_errors")
        ):
            report["potential_blockers"].append("Previous completed announcement had delivery errors")
        if not cfg.get("occupancy_sensor"):
            report["potential_blockers"].append("No occupancy sensor: cannot follow movement")
        if report["persisted_queue_count"] not in (None, 0):
            report["potential_blockers"].append(
                "Persisted undelivered queue is non-empty"
            )
        if any(item.get("ai_pending") for item in report["persisted_queue"]):
            report["potential_blockers"].append("One or more AI generations remain pending")
        snapshots = report.get("container_probe", {}).get("sources", {})
        for label in ("occupied_rooms", "sleeping_rooms"):
            source_report = snapshots.get(label, {})
            if source_report.get("unknown_values"):
                report["potential_blockers"].append(
                    f"Recorder sample for {label} contains unrecognized areas"
                )
            if source_report.get("configured") and source_report.get(
                "selected_attribute_present"
            ) is False:
                report["potential_blockers"].append(
                    f"Recorder sample for {label} lacks selected attribute"
                )
        if not report["current_state"]["live_api"]:
            report["potential_blockers"].append(
                "No authenticated live HA API read; recorder data is historical"
            )
    json_path = out / f"ah-scenarios-{STAMP}.json"
    txt_path = out / f"ah-scenarios-{STAMP}.txt"
    tar_path = out / f"ah-scenarios-{STAMP}.tar.gz"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n")
    s = report.get("scenarios", {})
    lines = ["READ_ONLY=YES", f"VERSION={report.get('installed_version','unknown')}",
             f"SCENARIOS={s.get('passed',0)}/{s.get('total',0)}",
             f"PERSISTED_QUEUE={report.get('persisted_queue_count','unverified')}",
             f"HOST_STORE={report.get('host_queue_store_status','unverified')}",
             f"CONTAINER_STORE={report.get('container_probe',{}).get('queue_store',{}).get('status','unverified')}",
             f"RECORDER={report.get('container_probe',{}).get('recorder_status','unavailable')}",
             f"LAST_JOB_STATUS={report.get('last_job',{}).get('status','unknown')}",
             f"LIVE_API={report.get('current_state',{}).get('live_api', False)}",
             *("BLOCKER=" + x for x in report.get("potential_blockers", [])),
             *("SCENARIO_" + v + "=" + k for k,v in s.get("results",{}).items()),
             f"ARCHIVE={tar_path}"]
    txt_path.write_text("\n".join(lines) + "\n")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(json_path, arcname=json_path.name)
        tar.add(txt_path, arcname=txt_path.name)
    print("\n".join(lines))
    return 0 if root and s.get("passed") == s.get("total") else 2

if __name__ == "__main__":
    sys.exit(main())
