#!/usr/bin/env python3
"""Read-only, privacy-limited Home Assistant container evidence probe.

Run via docker exec -i homeassistant python3 - with this file on stdin.
Never invokes Home Assistant services, writes database records, changes HA
configuration, or emits credentials / notification message text.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
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
        modern = {"metadata_id", "attributes_id", "last_updated_ts"} <= columns
        history: dict[str, Any] = {}
        for entity_id in dict.fromkeys(ids):
            if modern:
                rows = connection.execute(
                    """SELECT s.state, s.last_updated_ts, a.shared_attrs
                       FROM states AS s
                       JOIN states_meta AS m ON m.metadata_id=s.metadata_id
                       LEFT JOIN state_attributes AS a ON a.attributes_id=s.attributes_id
                       WHERE m.entity_id=?
                       ORDER BY s.state_id DESC LIMIT ?""",
                    (entity_id, count)
                ).fetchall()
            elif "entity_id" in columns:
                rows = connection.execute(
                    """SELECT state, last_updated, attributes FROM states
                       WHERE entity_id=? ORDER BY state_id DESC LIMIT ?""",
                    (entity_id, count)
                ).fetchall()
            else:
                return {}, "recorder_schema_unsupported"
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
