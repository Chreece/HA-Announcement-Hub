#!/usr/bin/env python3
"""Read-only, privacy-limited Home Assistant container evidence probe.

Run via docker exec -i homeassistant python3 - with this file on stdin.
Never invokes Home Assistant services, writes database records, changes HA
configuration, or emits credentials / notification message text.
"""
from __future__ import annotations

from datetime import datetime, timezone
from collections import Counter
from collections.abc import Mapping
import json
import hashlib
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any

SELECTED_KEYS = (
    "occupancy_sensor", "occupancy_attribute",
    "sleep_rooms_entity", "sleep_rooms_attribute",
)
OUTPUT_KEYS = ("notify_outputs", "snapcast_outputs", "tts_room_players",
               "companion_tts_outputs", "tts_engines")
MAX_OUTPUTS = 25

def read_json(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return (data if isinstance(data, dict) else {}), "readable"
    except (PermissionError, OSError) as exc:
        return {}, type(exc).__name__
    except (ValueError, UnicodeError):
        return {}, "unparseable"

def state_tokens(raw: Any) -> list[str]:
    """Match installed AnnouncementManager._occupancy_values behavior."""
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [str(k).strip() for k, v in raw.items() if v and str(k).strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(item).strip() for item in raw if str(item).strip()]
    val = str(raw).strip()
    if not val:
        return []
    if val.startswith("[") and val.endswith("]"):
        try:
            val_json = json.loads(val)
            if isinstance(val_json, list):
                return [str(item).strip() for item in val_json if str(item).strip()]
        except (ValueError, TypeError):
            pass
    return [part.strip().strip("'\"") for part in re.split(r"[,;\n]+", val)
            if part.strip().strip("'\"")]

def area_resolution(values: list[str], registry: dict[str, Any]) -> dict[str, Any]:
    raw_areas = registry.get("data", {}).get("areas", []) or []
    named: dict[str, str] = {}
    for area in raw_areas:
        identifier = area.get("id")
        if not identifier:
            continue
        named[str(identifier).casefold()] = identifier
        for candidate in [area.get("name"), *(area.get("aliases") or [])]:
            if candidate:
                named[str(candidate).casefold()] = identifier
    found: list[str] = []
    unknown: list[str] = []
    for v in values:
        area = named.get(v.casefold())
        (found if area else unknown).append(area or v)
    return {
        "recognized_area_ids": list(dict.fromkeys(found))[:20],
        "unknown_values": list(dict.fromkeys(unknown))[:20],
        "areas_catalog_size": len(raw_areas),
    }

def latest_states(database: Path, ids: list[str], *, count: int = 5) -> tuple[dict[str, Any], str]:
    if not database.is_file():
        return {}, "recorder_db_missing"
    try:
        # read-only URI and query_only prevent data modifications. This may
        # read the SQLite WAL, but does not checkpoint/write it.
        connection = sqlite3.connect(
            f"file:{database}?mode=ro", uri=True, timeout=3
        )
        connection.execute("PRAGMA query_only=ON")
    except (sqlite3.Error, OSError) as error:
        return {}, "recorder_open_" + type(error).__name__
    try:
        columns = {x[1] for x in connection.execute("PRAGMA table_info(states)")}
        # HA recorder storage evolved over time. Select only known columns
        # discovered from PRAGMA; never guess the timestamp/attribute layout.
        stamps = (
            "last_updated_ts", "last_changed_ts",
            "last_reported_ts", "last_updated", "last_changed",
        )
        time_col = next((key for key in stamps if key in columns), None)
        has_metadata = "metadata_id" in columns
        has_legacy_entity = "entity_id" in columns
        attrs_join = "attributes_id" in columns
        if not ("state" in columns and (has_metadata or has_legacy_entity)):
            return {}, "recorder_schema_unsupported"
        stamp_sql = f"s.{time_col}" if time_col else "NULL"
        if attrs_join:
            attrs_join_sql = (
                " LEFT JOIN state_attributes AS a"
                " ON a.attributes_id=s.attributes_id"
            )
            attrs_sql = "a.shared_attrs"
        else:
            attrs_join_sql = ""
            attrs_sql = "s.attributes" if "attributes" in columns else "NULL"
        if has_metadata:
            query = (
                f"SELECT s.state, {stamp_sql}, {attrs_sql} FROM states AS s"
                " JOIN states_meta AS m ON m.metadata_id=s.metadata_id"
                + attrs_join_sql
                + " WHERE m.entity_id=? ORDER BY s.state_id DESC LIMIT ?"
            )
        else:
            query = (
                f"SELECT s.state, {stamp_sql}, {attrs_sql} FROM states AS s"
                + attrs_join_sql
                + " WHERE s.entity_id=? ORDER BY s.state_id DESC LIMIT ?"
            )
        history: dict[str, Any] = {}
        for entity_id in dict.fromkeys(ids):
            rows = connection.execute(query, (entity_id, count)).fetchall()
            snapshots = []
            for raw_state, stamp, attrs in rows:
                if isinstance(stamp, (int, float)):
                    observed = datetime.fromtimestamp(stamp, timezone.utc).isoformat()
                    age = round((datetime.now(timezone.utc).timestamp() - stamp) / 60, 1)
                else:
                    observed = str(stamp) if stamp else None
                    age = None
                try:
                    attrs_dict = json.loads(attrs or "{}")
                except (TypeError, ValueError):
                    attrs_dict = {}
                snapshots.append({
                    "state": str(raw_state or "")[:220],
                    "observed_at": observed,
                    "age_minutes": age,
                    # Only source-selected attributes will be extracted by caller.
                    "_attributes": attrs_dict if isinstance(attrs_dict, dict) else {},
                })
            history[entity_id] = snapshots
        return history, "recorder_last_observed_not_live"
    except sqlite3.Error as error:
        return {}, "recorder_query_" + type(error).__name__
    finally:
        connection.close()

def queue_backlog_metrics(jobs: list[Any], ai_history: list[Any]) -> dict[str, Any]:
    """Summarize ALL jobs without exporting job IDs, prompts, or generated text."""
    now = datetime.now(timezone.utc)
    stage_count: Counter[str] = Counter()
    mode_count: Counter[str] = Counter()
    ai_count: Counter[str] = Counter()
    provider_count: Counter[str] = Counter()
    age_buckets = {
        "under_5_minutes": 0,
        "5_to_30_minutes": 0,
        "30_to_120_minutes": 0,
        "over_120_minutes": 0,
        "timestamp_unavailable": 0,
    }
    pending_ages: list[float] = []
    ready_ages: list[float] = []
    room_load: Counter[str] = Counter()
    job_status_count: Counter[str] = Counter()
    duplicates: Counter[tuple[Any, ...]] = Counter()

    for item in jobs:
        if not isinstance(item, Mapping):
            continue
        ai = item.get("ai") or {}
        if not isinstance(ai, Mapping):
            ai = {}
        stage_count[str(item.get("routing_stage", "unknown"))] += 1
        mode_count[str(item.get("routing_mode", "unknown"))] += 1
        job_status_count[str(item.get("status", "unknown"))] += 1
        for room in set(item.get("preferred_areas") or item.get("outputs") or ()):
            if isinstance(room, str):
                room_load[room] += 1
        ai_pending = bool(ai.get("pending_preprocessing"))
        ai_count["waiting_for_ai" if ai_pending else "ai_finished_or_disabled"] += 1
        if ai_pending:
            provider = str(ai.get("requested_agent_id") or "not_recorded")
            provider_count[provider] += 1
            identity = (
                str(ai.get("source_tts")),
                str(ai.get("source_notify")),
                provider,
                str(ai.get("requested_mode")),
                str(ai.get("requested_target_language")),
            )
            duplicates[identity] += 1
        try:
            dt = datetime.fromisoformat(str(item.get("created_at") or ""))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            elapsed = max(0.0, (now-dt).total_seconds()/60)
        except (TypeError, ValueError, OverflowError):
            age_buckets["timestamp_unavailable"] += 1
            continue
        if elapsed < 5:
            age_buckets["under_5_minutes"] += 1
        elif elapsed < 30:
            age_buckets["5_to_30_minutes"] += 1
        elif elapsed < 120:
            age_buckets["30_to_120_minutes"] += 1
        else:
            age_buckets["over_120_minutes"] += 1
        if ai_pending:
            pending_ages.append(elapsed)
        else:
            ready_ages.append(elapsed)

    historical = [x for x in ai_history if isinstance(x, Mapping)]
    samples = [
        float(x["elapsed_seconds"])
        for x in historical[-20:]
        if isinstance(x.get("elapsed_seconds"), (float, int))
    ]
    duplicates_counts = sorted(
        (count for count in duplicates.values() if count > 1),
        reverse=True,
    )
    first = next((x for x in jobs if isinstance(x, Mapping)), {})
    first_ai = first.get("ai") or {}
    if not isinstance(first_ai, Mapping):
        first_ai = {}
    first_summary = {
        "status": first.get("status"),
        "routing_stage": first.get("routing_stage"),
        "routing_mode": first.get("routing_mode"),
        "ai_pending": bool(first_ai.get("pending_preprocessing")),
        "ai_status": first_ai.get("status"),
        "strict_targets": bool(first.get("strict_targets")),
        "occupied_only": bool(first.get("occupancy_requested", True)),
        "preferred_area_count": len(first.get("preferred_areas") or []),
        "selected_area_count": len(first.get("outputs") or []),
        "notify_outputs": len(first.get("notify_outputs") or []),
        "room_tts_players": len(first.get("room_tts_players") or []),
        "snapcast_clients": len(first.get("snapcast_clients") or []),
        "companion_tts_entries": len(first.get("companion_tts_entries") or []),
        "person_targets": len(first.get("person_ids") or []),
        "presence_sensors": len(first.get("presence_sensors") or []),
        "recent_routing": (first.get("routing_history") or [])[-3:],
    }
    finished = historical[-1] if historical else {}
    last_id = str(finished.get("job_id") or "")
    ai_progress_marker = (
        hashlib.sha256(last_id.encode("utf-8")).hexdigest()[:16]
        if last_id else None
    )
    return {
        "count_by_stage": dict(stage_count),
        "count_by_routing_mode": dict(mode_count),
        "count_by_job_status": dict(job_status_count),
        "first_queued_job": first_summary,
        "oldest_AI_ready_job_wait_minutes": round(max(ready_ages), 1) if ready_ages else None,
        "most_jobs_sharing_one_room": max(room_load.values(), default=0),
        "distinct_queued_room_count": len(room_load),
        "count_by_ai_state": dict(ai_count),
        "count_by_requested_ai_provider": dict(provider_count),
        "job_age_buckets": age_buckets,
        "oldest_AI_wait_minutes": round(max(pending_ages), 1) if pending_ages else None,
        "duplicate_AI_prompt_group_sizes": duplicates_counts[:10],
        "duplicate_AI_jobs_avoidable_by_reuse": sum(n-1 for n in duplicates_counts),
        "recent_AI_samples": len(samples),
        "last_AI_completed_job_marker": ai_progress_marker,
        "last_AI_completed_job_created_at": finished.get("created_at"),
        "recent_AI_average_seconds": round(sum(samples)/len(samples), 1) if samples else None,
        "recent_AI_max_seconds": round(max(samples), 1) if samples else None,
    }

def read_evidence(config: Path = Path("/config")) -> dict[str, Any]:
    entries, entries_status = read_json(config / ".storage/core.config_entries")
    rows = entries.get("data", {}).get("entries", [])
    entry = next((e for e in rows if e.get("domain") == "announcement_hub"), {})
    settings = {**(entry.get("data") or {}), **(entry.get("options") or {})}
    report: dict[str, Any] = {
        "read_only": True,
        "entry_read_status": entries_status,
        "entry_found": bool(entry),
    }
    storage_name = "announcement_hub.queue." + str(entry.get("entry_id") or "")
    storage, status = read_json(config / ".storage" / storage_name)
    report["queue_store"] = {
        "status": status,
        "has_data": "data" in storage,
    }
    if status == "readable":
        stored = storage.get("data", {})
        if isinstance(stored, dict):
            jobs = stored.get("jobs") or []
            last = stored.get("last") or {}
            report["queue_store"].update({
                "job_count": len(jobs),
                "backlog_metrics": queue_backlog_metrics(
                    jobs, stored.get("ai_history") or []
                ),
                "pending_summary": [
                    {
                        "status": j.get("status"),
                        "routing_stage": j.get("routing_stage"),
                        "ai_pending": bool((j.get("ai") or {}).get("pending_preprocessing")),
                        "recent_routing": (j.get("routing_history") or [])[-3:],
                    }
                    for j in jobs[:25] if isinstance(j, dict)
                ],
                "last": {
                    "status": last.get("status"),
                    "routing_stage": last.get("routing_stage"),
                    "successful_channels": len(last.get("successful_channels") or []),
                    "failed_channels": len(last.get("channel_errors") or {}),
                    "ai_status": (last.get("ai") or {}).get("status"),
                },
                "recent_ai": [
                    {
                        "status": x.get("status"),
                        "elapsed_seconds": x.get("elapsed_seconds"),
                        "failure_reason": x.get("failure_reason"),
                    }
                    for x in (stored.get("ai_history") or [])[-15:] if isinstance(x, dict)
                ],
            })
    registry, registry_status = read_json(config / ".storage/core.area_registry")
    report["area_registry_status"] = registry_status
    source_spec = {
        "occupied_rooms": (
            settings.get("occupancy_sensor"),
            settings.get("occupancy_attribute") or "",
        ),
        "sleeping_rooms": (
            settings.get("sleep_rooms_entity"),
            settings.get("sleep_rooms_attribute") or "",
        ),
    }
    ids: list[str] = [
        value for value, attr in source_spec.values()
        if isinstance(value, str) and value
    ]
    for key in ("notify_outputs", "snapcast_outputs", "tts_room_players", "tts_engines"):
        for ref in settings.get(key) or []:
            if not isinstance(ref, str):
                continue
            entity = ref.removeprefix("entity:")
            if entity.startswith(("notify.", "media_player.", "tts.")):
                ids.append(entity)
    if isinstance(settings.get("tts_media_player"), str):
        ids.append(settings["tts_media_player"])
    ids = list(dict.fromkeys(ids))[:2 + MAX_OUTPUTS]
    # Default SQLite recorder; MariaDB/filtered/excluded entities may have
    # no rows. Never describe recorder data as current HA state.
    history, db_status = latest_states(config / "home-assistant_v2.db", ids)
    report["recorder_status"] = db_status
    report["sources"] = {}
    for label, (entity_id, attribute) in source_spec.items():
        if not entity_id:
            report["sources"][label] = {"configured": False}
            continue
        snapshots = history.get(entity_id) or []
        report["sources"][label] = {
            "configured": True,
            "entity_id": entity_id,
            "selection": "attribute:" + attribute if attribute else "state",
            "recorder_records": len(snapshots),
        }
        if snapshots:
            current = snapshots[0]
            selected_raw = (
                current["_attributes"].get(attribute)
                if attribute else current["state"]
            )
            tokens = state_tokens(selected_raw)
            report["sources"][label].update({
                "recorder_age_minutes": current["age_minutes"],
                "selected_attribute_present": (
                    attribute in current["_attributes"] if attribute else True
                ),
                "state_status": (
                    "unavailable" if current["state"] in ("unknown", "unavailable")
                    else "recorded"
                ),
                "parsed_tokens": tokens[:20],
                **area_resolution(tokens, registry),
                "recent_recorder_observations": [
                    {"age_minutes": x["age_minutes"], "state": x["state"][:70]}
                    for x in snapshots[:5]
                ],
            })
    report["output_recorder_states"] = [
        {
            "entity_id": entity,
            "state": history[entity][0]["state"],
            "age_minutes": history[entity][0]["age_minutes"],
        }
        for entity in ids
        if entity not in {x[0] for x in source_spec.values()}
        and history.get(entity)
    ][:MAX_OUTPUTS]
    # The above values are historical recorder values, NEVER HA live states.
    return report

def main() -> None:
    print(json.dumps(read_evidence(), ensure_ascii=False, separators=(",", ":"), default=str))

if __name__ == "__main__":
    main()
