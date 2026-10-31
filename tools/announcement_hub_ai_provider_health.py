#!/usr/bin/env python3
"""Read-only local AI Task / Ollama health evidence for Announcement Hub.

No HA API tokens or credentials, no generation request, no device service
calls, no queue mutation, no container/network restart. Logs become counters,
never verbatim private message or provider payload content.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

AI_ENTITY = "ai_task.qwen3_8_task"
SIGNALS = {
    "ai_request_slow": r"AI agent.*has not responded|continuing to await AI provider",
    "ai_preprocessing_error": r"AI preprocessing task failed|AI preprocessing failed",
    "ai_invalid_response": r"AI agent.*invalid or unsafe|AI result validation failed",
    "ai_request_failure": r"AI agent.*failed|ai_task.*(?:error|exception)",
    "ai_provider_timeout": r"provider_timeout|timed?\s*out",
    "ai_task_mention": r"ai_task|qwen3",
    "ollama_mention": r"ollama",
    "gpu_oom": r"out of memory|cannot allocate memory|memory allocation failed",
    "gpu_error": r"hip error|rocm error|gpu reset|device lost",
}

def safe_run(argv: list[str], *, input_text: str | None = None,
             timeout: int = 10) -> tuple[int | None, str]:
    try:
        result = subprocess.run(
            argv, input=input_text, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        return result.returncode, result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return None, ""

def counters(text: str) -> dict[str, int]:
    return {
        key: len(re.findall(pattern, text, flags=re.IGNORECASE))
        for key, pattern in SIGNALS.items()
    }

CONTAINER_PROBE = r'''import json
from pathlib import Path
root=Path("/config/.storage")
def data(name):
    try: return json.loads((root/name).read_text("utf-8")).get("data",{})
    except (OSError,ValueError,UnicodeError): return {}
registry=data("core.entity_registry")
entry_list=data("core.config_entries").get("entries",[])
entity=next((x for x in registry.get("entities",[]) if x.get("entity_id")=="ai_task.qwen3_8_task"),{})
provider=next((x for x in entry_list if x.get("entry_id")==entity.get("config_entry_id")),{})
try:
    path=Path("/config/home-assistant.log")
    with path.open("rb") as f:
        f.seek(0,2)
        f.seek(max(0,f.tell()-2500000))
        recent=f.read().decode("utf-8",errors="replace")
except OSError: recent=""
print(json.dumps({
    "entity_registered":bool(entity),
    "entity_platform":entity.get("platform"),
    "provider_entry_domain":provider.get("domain"),
    "provider_entry_state":str(provider.get("state") or "unknown"),
    "home_assistant_log_available":bool(recent),
    "home_assistant_log_excerpt_for_counts_only":recent,
},ensure_ascii=False))
'''

def inspect(name: str) -> dict:
    code, output = safe_run(["docker", "inspect", name])
    if code != 0:
        return {"status": "unavailable"}
    try:
        item = json.loads(output)[0]
        state = item.get("State", {})
        return {
            "status": state.get("Status"),
            "running": state.get("Running"),
            "started_at": state.get("StartedAt"),
            "restart_count": item.get("RestartCount"),
            "health": (state.get("Health") or {}).get("Status"),
        }
    except (ValueError, IndexError, TypeError):
        return {"status": "unparseable"}

def docker_names() -> list[str]:
    code, output = safe_run(["docker", "ps", "--format", "{{.Names}}"])
    return output.splitlines() if code == 0 else []

def ollama_health(name: str) -> dict:
    probe: dict = {"container": name, "inspect": inspect(name)}
    code, output = safe_run(["docker", "exec", "-i", name, "ollama", "ps"], timeout=9)
    probe["ollama_ps_command"] = (
        "ok" if code == 0 else ("timeout_or_unavailable" if code is None else "failed")
    )
    if code == 0:
        # The Ollama command prints model NAME, ID, SIZE, PROCESSOR and UNTIL.
        # Model names are not credentials; never export server endpoints.
        probe["ollama_ps_model_count"] = max(0, len(output.splitlines()) - 1)
        probe["ollama_ps_rows"] = [
            line[:180] for line in output.splitlines()[1:7]
        ]
    code, logs = safe_run(
        ["docker", "logs", "--since", "3h", "--tail", "3500", name],
        timeout=12,
    )
    probe["log_signal_counts_3h"] = counters(logs) if code == 0 else {"unavailable": True}
    return probe

def probe() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    report = {
        "captured_at_utc": now,
        "read_only": True,
        "target_ai_entity": AI_ENTITY,
        "homeassistant": inspect("homeassistant"),
        "provider": {"status": "unavailable"},
    }
    code, output = safe_run(
        ["docker", "exec", "-i", "homeassistant", "python3", "-"],
        input_text=CONTAINER_PROBE, timeout=12,
    )
    if code == 0:
        try:
            details = json.loads(output)
            recent = details.pop("home_assistant_log_excerpt_for_counts_only", "")
            details["ha_file_log_signal_counts"] = counters(recent)
            report["provider"] = details
        except (ValueError, TypeError):
            report["provider"] = {"status": "unparseable"}
    elif code is not None:
        report["provider"] = {"status": "container_probe_failed"}

    code, logs = safe_run(
        ["docker", "logs", "--since", "3h", "--tail", "5500", "homeassistant"],
        timeout=12,
    )
    report["ha_docker_log_signal_counts_3h"] = (
        counters(logs) if code == 0 else {"unavailable": True}
    )

    matches = [name for name in docker_names() if "ollama" in name.casefold()]
    report["ollama_containers"] = [ollama_health(name) for name in matches[:3]]
    report["ollama_container_detected"] = bool(matches)

    args = ["docker", "stats", "--no-stream", "--format", "{{json .}}",
            "homeassistant", *matches[:3]]
    code, output = safe_run(args, timeout=14)
    if code == 0:
        report["resource_usage"] = [
            {
                key: item.get(key)
                for key in ("Name", "CPUPerc", "MemUsage", "MemPerc", "PIDs")
            }
            for line in output.splitlines()[:4]
            for item in [json.loads(line)]
            if isinstance(item, dict)
        ]
    else:
        report["resource_usage"] = []
    return report

def main() -> None:
    root = Path(os.environ.get(
        "AH_LOG_DIR", str(Path.home() / "projects/announcement_hub/logs")
    )).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = root / f"ah-ai-provider-{stamp}.json"
    archive = root / f"ah-ai-provider-{stamp}.tar.gz"
    report = probe()
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(path, arcname=path.name)
    print("READ_ONLY=YES")
    print("HA_CONTAINER_STATUS=" + str(report["homeassistant"]["status"]))
    print("HA_STARTED_AT=" + str(report["homeassistant"].get("started_at")))
    print("AI_TASK_PLATFORM=" + str(report["provider"].get("entity_platform")))
    print("AI_PROVIDER_INTEGRATION=" + str(report["provider"].get("provider_entry_domain")))
    print("OLLAMA_CONTAINERS=" + str(len(report["ollama_containers"])))
    for item in report["ollama_containers"]:
        print(item["container"] + "_MODEL_COUNT=" +
              str(item.get("ollama_ps_model_count", "unavailable")))
    print("EVIDENCE_ARCHIVE=" + str(archive))

if __name__ == "__main__":
    main()
