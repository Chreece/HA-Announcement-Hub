"""Read-only AI provider health probe never exports raw logs or secrets."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/announcement_hub_ai_provider_health.py"
spec = importlib.util.spec_from_file_location("ah_ai_provider_health_test", SCRIPT)
assert spec and spec.loader
health = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = health
spec.loader.exec_module(health)


def test_provider_probe_uses_only_read_only_docker_commands():
    code = SCRIPT.read_text(encoding="utf-8")
    assert "docker stop" not in code
    assert "docker restart" not in code
    assert "services.async_call(" not in code
    assert '["docker", "exec", "-i", "homeassistant", "python3", "-"]' in code
    assert '["docker", "logs"' in code
    assert '["docker", "stats"' in code
    assert 'ollama", "ps"' in code


def test_logs_are_counted_not_exported(monkeypatch, tmp_path, capsys):
    private_text = "PERSONAL_BEDROOM_ANNOUNCEMENT_SHOULD_NOT_LEAK"
    def fake_run(argv, **kwargs):
        if argv[:2] == ["docker", "inspect"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps([{
                "State": {"Status": "running", "Running": True,
                          "StartedAt": "2026-10-31T06:50:00Z"},
                "RestartCount": 2,
            }]), stderr="")
        if argv[:3] == ["docker", "exec", "-i"] and argv[3] == "homeassistant":
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "entity_registered": True, "entity_platform": "ollama",
                "provider_entry_domain": "ollama",
                "provider_entry_state": "loaded",
                "home_assistant_log_excerpt_for_counts_only":
                    "AI agent local has not responded after 60 seconds " + private_text,
            }), stderr="")
        if argv[:3] == ["docker", "exec", "-i"] and argv[3] == "ollama-rocm":
            return SimpleNamespace(returncode=0,
                                   stdout="NAME ID SIZE PROCESSOR UNTIL\nqwen3:8b ABC 6GB 100%GPU 4m\n",
                                   stderr="")
        if argv[:2] == ["docker", "ps"]:
            return SimpleNamespace(returncode=0, stdout="homeassistant\nollama-rocm\n",
                                   stderr="")
        if argv[:2] == ["docker", "logs"]:
            # Docker's log output may be exclusively on stderr.
            return SimpleNamespace(returncode=0, stdout="",
                                   stderr="GPU out of memory " + private_text)
        if argv[:2] == ["docker", "stats"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "Name": "ollama-rocm", "CPUPerc": "99.0%",
                "MemUsage": "6GiB / 24GiB", "PIDs": "8",
            }) + "\n", stderr="")
        raise AssertionError(argv)
    monkeypatch.setattr(health.subprocess, "run", fake_run)
    monkeypatch.setenv("AH_LOG_DIR", str(tmp_path))
    report = health.probe()
    assert report["provider"]["provider_entry_domain"] == "ollama"
    assert report["provider"]["ha_file_log_signal_counts"]["ai_request_slow"] == 1
    assert report["ha_docker_log_signal_counts_3h"]["gpu_oom"] == 1
    assert report["ollama_containers"][0]["ollama_ps_model_count"] == 1
    assert report["resource_usage"][0]["Name"] == "ollama-rocm"
    assert private_text not in json.dumps(report)
    health.main()
    output = capsys.readouterr().out
    assert private_text not in output
    archive = next(tmp_path.glob("ah-ai-provider-*.tar.gz"))
    assert archive.is_file()


def test_unavailable_docker_is_reported_without_raising(monkeypatch):
    monkeypatch.setattr(
        health.subprocess, "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )
    report = health.probe()
    assert report["homeassistant"]["status"] == "unavailable"
    assert not report["ollama_container_detected"]
    assert report["resource_usage"] == []
