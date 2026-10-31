"""Read-only Home Assistant-to-Ollama path probe and bounded opt-in smoke check."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "announcement_hub_ollama_link_probe.py"
spec = importlib.util.spec_from_file_location("test_ollama_link", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def run_ha_subprocess_code(tmp_path, monkeypatch, active=False):
    storage = tmp_path / ".storage"
    storage.mkdir()
    (storage / "core.entity_registry").write_text(json.dumps({
        "data": {"entities": [{
            "entity_id": "ai_task.qwen3_8_task",
            "platform": "ollama",
            "config_entry_id": "entry",
            "config_subentry_id": "subentry",
        }]}
    }))
    (storage / "core.config_entries").write_text(json.dumps({
        "data": {"entries": [{
            "entry_id": "entry", "domain": "ollama",
            "data": {"url": "http://SECRET_HOST:11434",
                     "api_key": "SECRET_API_KEY"},
            "subentries": [{
                "subentry_id": "subentry", "subentry_type": "ai_task_data",
                "data": {"model": "qwen3.8-greek:latest", "num_ctx": 16384,
                         "think": False, "keep_alive": -1},
            }],
        }]}
    }))

    calls = []
    def urlopen(request, timeout):
        calls.append((request.full_url, request.get_method(), timeout))
        suffix = request.full_url.split("/api/")[-1]
        if suffix == "version":
            response = {"version": "0.40.6"}
        elif suffix == "ps":
            response = {"models": [{
                "name": "qwen3.8-greek:latest",
                "size": 18000000000,
                "size_vram": 9500000000,
                "context_length": 16384,
                "digest": "PRIVATE_DIGEST",
            }]}
        elif suffix == "tags":
            response = {"models": [{"name": "qwen3.8-greek:latest"}]}
        elif suffix == "generate":
            response = {
                "done": True,
                "response": "SECRET_GENERATED_ANSWER",
                "eval_count": 4,
                "total_duration": 3000000000,
            }
        else:
            raise AssertionError(request.full_url)
        class MockResponse:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, maximum): return json.dumps(response).encode()
        return MockResponse()
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("AH_ACTIVE_PROBE", "1" if active else "0")
    code = mod.HA_PROBE.replace(
        'Path("/config/.storage")',
        "Path(" + repr(str(storage)) + ")",
    )
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exec(compile(code,"nested probe","exec"),{"__name__":"__main__"})
    data = json.loads(stdout.getvalue())
    return data,calls


def test_passive_provider_probe_reads_task_settings_and_only_calls_get(tmp_path,monkeypatch):
    report,calls = run_ha_subprocess_code(tmp_path,monkeypatch)
    assert report["entity_found"] is True
    assert report["config_entry_domain"] == "ollama"
    assert report["subentry_found"] is True
    assert report["model"] == "qwen3.8-greek:latest"
    assert report["configured_num_ctx"] == 16384
    assert report["configured_think"] is False
    assert report["configured_keep_alive"] == -1
    assert report["reachability"]["version"]["status"] == "ok"
    assert report["reachability"]["loaded"]["configured_model_loaded"] is True
    assert report["reachability"]["loaded"]["selected_model_context_length"] == 16384
    assert report["reachability"]["loaded"]["selected_model_vram_size_bytes"] == 9500000000
    assert report["reachability"]["tags"]["configured_model_exists"] is True
    assert len(calls) == 3
    assert all(method == "GET" for _,method,_ in calls)
    assert report["minimal_inference"]["status"] == "disabled"
    output=json.dumps(report)
    assert "SECRET_HOST" not in output
    assert "SECRET_API_KEY" not in output
    assert "PRIVATE_DIGEST" not in output


def test_opt_in_bounded_generation_never_leaks_text(tmp_path,monkeypatch):
    report,calls = run_ha_subprocess_code(tmp_path,monkeypatch,active=True)
    assert len(calls) == 4
    assert calls[-1][1] == "POST"
    assert calls[-1][2] == 18
    assert report["minimal_inference"]["status"] == "ok"
    assert report["minimal_inference"]["eval_count"] == 4
    assert report["minimal_inference"]["total_duration_ms"] == 3000
    assert "SECRET_GENERATED_ANSWER" not in json.dumps(report)


def test_ollama_ps_parser_retains_cpu_gpu_memory_split(monkeypatch):
    def fake_run(args,input_text=None,timeout=25):
        if args[:2]==["docker","inspect"]:
            return 0,json.dumps([{"State":{"Status":"running","StartedAt":"2026-10-31T07:00:00Z"},"RestartCount":0}])
        if args[:3]==["docker","exec","-i"]:
            return 0,json.dumps({"reachability":{"version":{"status":"ok"}}})
        if args[:3]==["docker","exec","ollama"]:
            return 0,(
                "NAME ID SIZE PROCESSOR CONTEXT RUNNER UNTIL\n"
                "qwen3.8-greek:latest 7470c1e6b714 18 GB 47%/53% CPU/GPU 16384 llamacpp Forever\n"
            )
        raise AssertionError(args)
    monkeypatch.setattr(mod,"run",fake_run)
    monkeypatch.setattr(mod,"gpu_vram",lambda: [])
    report=mod.probe()
    assert report["ollama_ps"]["loaded_count"] == 1
    assert report["ollama_ps"]["model_processor_status"][0]["processor"] == "47%/53% CPU/GPU"
    assert report["ollama_ps"]["model_processor_status"][0]["context"] == "16384"


def test_probe_never_uses_home_assistant_notification_or_restarts():
    source=SCRIPT.read_text()
    assert "notify.announcement_hub" not in source
    assert "docker restart" not in source
    assert "docker stop" not in source
    assert "POST" in source   # opt-in benign Ollama inference only
    assert 'os.environ.get("AH_ACTIVE_PROBE")=="1"' in source
