"""The on-host scenario runner uses the installed code and never sends HA actions."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "announcement_hub_onhost_scenarios.py"
MANAGER = ROOT / "custom_components" / "announcement_hub" / "manager.py"
spec = importlib.util.spec_from_file_location("announcement_hub_host_scenarios", TOOL)
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_installed_production_routing_passes_synthetic_room_scenarios():
    result = audit.scenarios(MANAGER)
    assert result["source"] == "installed_manager_AST_no_HA_services"
    assert result["passed"] == result["total"] == 14, result


def test_tool_has_no_ha_service_or_remote_mutation_calls():
    source = TOOL.read_text(encoding="utf-8")
    assert "services.async_call(" not in source
    assert "docker\", \"logs" in source
    assert "docker\", \"inspect" in source
    assert ".storage/core.config_entries" in source
    assert "mode=selector" not in source
    assert "HASS_TOKEN" in source


def test_host_run_is_read_only_and_redacts_message_body(tmp_path, monkeypatch, capsys):
    config = tmp_path / "ha-config"
    comp = config / "custom_components" / "announcement_hub"
    storage = config / ".storage"
    comp.mkdir(parents=True)
    storage.mkdir()
    (comp / "manager.py").write_text(MANAGER.read_text(encoding="utf-8"))
    (comp / "manifest.json").write_text('{"version":"0.10.0b25"}', encoding="utf-8")
    (storage / "core.config_entries").write_text(json.dumps({
        "data": {"entries": [{
            "domain": "announcement_hub",
            "entry_id": "abc123",
            "data": {"occupancy_sensor": "sensor.rooms",
                     "notify_outputs": ["entity:notify.pixel"],
                     "default_use_ai": True},
            "options": {},
        }]},
    }), encoding="utf-8")
    (storage / "announcement_hub.queue.abc123").write_text(json.dumps({
        "data": {
            "jobs": [{
                "routing_stage": "general",
                "status": "pending",
                "text_tts": "DO_NOT_EXPORT_PRIVATE_MESSAGE",
                "text_notify": "DO_NOT_EXPORT_PRIVATE_MESSAGE",
                "ai": {"pending_preprocessing": True, "status": "pending"},
            }],
            "ai_history": [{"status": "pending", "elapsed_seconds": 42}],
        },
    }), encoding="utf-8")
    monkeypatch.setenv("AH_CONFIG_DIR", str(config))
    monkeypatch.setenv("AH_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.delenv("HASS_TOKEN", raising=False)
    monkeypatch.delenv("HA_TOKEN", raising=False)
    monkeypatch.setattr(audit.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout="Announcement AI agent slow", stderr=""
    ))
    assert audit.main() == 0
    report = next((tmp_path / "logs").glob("*.json")).read_text(encoding="utf-8")
    assert "DO_NOT_EXPORT_PRIVATE_MESSAGE" not in report
    data = json.loads(report)
    assert data["scenarios"]["passed"] == 14
    assert data["persisted_queue_count"] == 1
    assert data["host_queue_store_status"] == "readable"
    assert "log_signals_24h" in data
    assert "log_signals_6h" in data
    assert data["current_state"] == {"live_api": False}
    assert "HASS_TOKEN" not in report
    assert next((tmp_path / "logs").glob("*.tar.gz")).is_file()



def test_two_read_only_snapshots_detect_ai_backlog_progress(tmp_path, monkeypatch):
    config = tmp_path / "ha"
    storage = config / ".storage"
    comp = config / "custom_components" / "announcement_hub"
    storage.mkdir(parents=True)
    comp.mkdir(parents=True)
    (comp / "manager.py").write_text(MANAGER.read_text("utf-8"))
    (comp / "manifest.json").write_text('{"version":"0.10.0b25"}')
    (storage / "core.config_entries").write_text(json.dumps({
        "data": {"entries": [{
            "domain": "announcement_hub", "entry_id": "sample",
            "data": {"occupancy_sensor": "sensor.rooms"},
        }]}
    }))
    monkeypatch.setenv("AH_CONFIG_DIR", str(config))
    monkeypatch.setenv("AH_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("AH_OBSERVE_SECONDS", "70")
    monkeypatch.delenv("HASS_TOKEN", raising=False)
    monkeypatch.delenv("HA_TOKEN", raising=False)
    invocations = []
    sleeps = []
    monkeypatch.setattr(audit.time, "sleep", lambda seconds: sleeps.append(seconds))

    def fake_docker(args, **kwargs):
        if args[:3] == ["docker", "exec", "-i"]:
            invocations.append(tuple(args))
            waiting = 82 if len(invocations) == 1 else 81
            data = {
                "queue_store": {
                    "status": "readable",
                    "job_count": 83 if waiting == 82 else 82,
                    "pending_summary": [],
                    "recent_ai": [],
                    "backlog_metrics": {
                        "count_by_ai_state": {"waiting_for_ai": waiting},
                        "last_AI_completed_job_marker": "old" if waiting == 82 else "new",
                    },
                }
            }
            return SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(audit.subprocess, "run", fake_docker)
    assert audit.main() == 0
    assert sleeps == [70]
    assert len(invocations) == 2
    report = json.loads(next((tmp_path / "logs").glob("*.json")).read_text())
    obs = report["AI_queue_observation"]
    assert obs["status"] == "progress_observed"
    assert obs["first_queue_size"] == 83
    assert obs["second_queue_size"] == 82
    assert obs["first_waiting_for_AI"] == 82
    assert obs["second_waiting_for_AI"] == 81
    assert obs["completed_AI_marker_changed"] is True
