"""Read-only Docker container probe: private Store and historic recorder data."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "announcement_hub_container_evidence.py"
spec = importlib.util.spec_from_file_location("ah_container_evidence_test", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture(tmp_path):
    root = tmp_path / "config"
    store = root / ".storage"
    store.mkdir(parents=True)
    (store / "core.config_entries").write_text(json.dumps({
        "data": {"entries": [{
            "domain": "announcement_hub", "entry_id": "entry-abc",
            "data": {
                "occupancy_sensor": "sensor.multi_room_presence",
                "occupancy_attribute": "rooms",
                "sleep_rooms_entity": "input_text.sleeprooms",
                "sleep_rooms_attribute": "",
                "notify_outputs": ["entity:notify.phone"],
                "tts_media_player": "media_player.mpd",
                "SECRET_TOKEN": "DO_NOT_EXPORT_TOKEN",
            },
        }]},
    }), encoding="utf-8")
    (store / "core.area_registry").write_text(json.dumps({
        "data": {"areas": [
            {"id": "kueche", "name": "Küche", "aliases": ["Kitchen"]},
            {"id": "schlafzimmer", "name": "Schlafzimmer", "aliases": ["Bedroom"]},
        ]},
    }), encoding="utf-8")
    (store / "announcement_hub.queue.entry-abc").write_text(json.dumps({
        "data": {
            "jobs": [{
                "status": "pending", "routing_stage": "occupied",
                "text_tts": "DO_NOT_EXPORT_SPOKEN_CONTENT",
                "ai": {"pending_preprocessing": True},
            }],
            "last": {
                "status": "failed", "text_notify": "DO_NOT_EXPORT_WRITTEN_CONTENT",
                "channel_errors": {"provider": "PRIVATE_MESSAGE_FAILED"},
            },
            "ai_history": [{"status": "fallback_original", "elapsed_seconds": 82}],
        },
    }), encoding="utf-8")
    conn = sqlite3.connect(root / "home-assistant_v2.db")
    conn.executescript("""
       CREATE TABLE states_meta (metadata_id INTEGER PRIMARY KEY, entity_id TEXT);
       CREATE TABLE state_attributes (attributes_id INTEGER PRIMARY KEY, shared_attrs TEXT);
       CREATE TABLE states (
           state_id INTEGER PRIMARY KEY, metadata_id INTEGER, attributes_id INTEGER,
           state TEXT, last_updated_ts REAL
       );
    """)
    ts = datetime.now(timezone.utc).timestamp() - 40
    for idx, (entity, value, attrs) in enumerate([
        ("sensor.multi_room_presence", "2", {"rooms": ["Küche", "invalid-room"]}),
        ("input_text.sleeprooms", '["Bedroom"]', {}),
        ("media_player.mpd", "playing", {}),
        ("notify.phone", "unknown", {}),
    ], 1):
        conn.execute("INSERT INTO states_meta VALUES (?,?)", (idx, entity))
        conn.execute("INSERT INTO state_attributes VALUES (?,?)",
                     (idx, json.dumps(attrs, ensure_ascii=False)))
        conn.execute("INSERT INTO states VALUES (?,?,?,?,?)",
                     (idx, idx, idx, value, ts))
    conn.commit()
    conn.close()
    return root


def test_private_store_and_source_parsing_are_grounded_in_installed_config(tmp_path):
    report = mod.read_evidence(fixture(tmp_path))
    assert report["read_only"] is True
    assert report["entry_found"]
    assert report["queue_store"]["status"] == "readable"
    assert report["queue_store"]["job_count"] == 1
    assert report["queue_store"]["last"]["status"] == "failed"
    assert report["recorder_status"] == "recorder_last_observed_not_live"
    occupied = report["sources"]["occupied_rooms"]
    assert occupied["parsed_tokens"] == ["Küche", "invalid-room"]
    assert occupied["recognized_area_ids"] == ["kueche"]
    assert occupied["unknown_values"] == ["invalid-room"]
    sleep = report["sources"]["sleeping_rooms"]
    assert sleep["parsed_tokens"] == ["Bedroom"]
    assert sleep["recognized_area_ids"] == ["schlafzimmer"]
    assert report["output_recorder_states"][0]["entity_id"] == "notify.phone"
    serialized = json.dumps(report)
    for banned in ("DO_NOT_EXPORT_SPOKEN_CONTENT", "DO_NOT_EXPORT_WRITTEN_CONTENT",
                   "DO_NOT_EXPORT_TOKEN", "PRIVATE_MESSAGE_FAILED"):
        assert banned not in serialized
    assert "last_updated" not in report["sources"]["occupied_rooms"]


def test_missing_store_is_not_misrepresented_as_empty_queue(tmp_path):
    root = fixture(tmp_path)
    (root / ".storage" / "announcement_hub.queue.entry-abc").unlink()
    report = mod.read_evidence(root)
    assert report["queue_store"]["status"] == "missing"
    assert "job_count" not in report["queue_store"]


def test_python_style_list_is_detected_as_unrecognized_not_trusted_json():
    raw = "['Küche', 'Schlafzimmer']"
    values = mod.state_tokens(raw)
    assert values != ["Küche", "Schlafzimmer"]


def test_database_connection_is_read_only_and_no_ha_service_is_called():
    code = SCRIPT.read_text(encoding="utf-8")
    assert 'mode=ro' in code
    assert "PRAGMA query_only=ON" in code
    assert "services.async_call(" not in code
    assert "docker stop" not in code
    assert "INSERT INTO" not in code
