#!/usr/bin/env python3
"""Privacy-limited Ollama AI Task path verification, from the HA Docker network.

Default checks are read-only: Ollama /api/version, /api/ps, /api/tags.
AH_ACTIVE_PROBE=1 additionally requests at most four benign model tokens
(no Home Assistant notification/automation calls). Never prints configured
URLs, API keys, prompts, generated text, raw response bodies or raw logs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import time

TARGET = "ai_task.qwen3_8_task"

HA_PROBE = r'''
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

TARGET = "ai_task.qwen3_8_task"
def load(name):
    try:
        return json.loads((Path("/config/.storage")/name).read_text("utf-8")).get("data", {})
    except (OSError,ValueError,UnicodeError):
        return {}
reg = load("core.entity_registry")
entries = load("core.config_entries").get("entries", []) or []
entity = next((x for x in reg.get("entities",[]) if x.get("entity_id")==TARGET), {})
owner = next((x for x in entries if x.get("entry_id")==entity.get("config_entry_id")), {})
subentry_id = entity.get("config_subentry_id")
subentries = owner.get("subentries") or []
if isinstance(subentries, dict):
    subentries = list(subentries.values())
sub = next((x for x in subentries if x.get("subentry_id")==subentry_id), {})
if not sub:
    sub = next((x for x in subentries if x.get("subentry_type")=="ai_task_data"), {})
settings = {
    **(owner.get("data") or {}),
    **(owner.get("options") or {}),
    **(sub.get("data") or {}),
}
model = str(settings.get("model") or "")
endpoint = str(settings.get("url") or "").rstrip("/")
auth = settings.get("api_key")
headers = {"Accept":"application/json"}
if isinstance(auth,str) and auth.strip():
    headers["Authorization"] = "Bearer " + auth.strip()
report = {
    "entity_found":bool(entity),
    "entity_platform":entity.get("platform"),
    "config_entry_found":bool(owner),
    "config_entry_domain":owner.get("domain"),
    "subentry_found":bool(sub),
    "model":model,
    "configured_num_ctx":settings.get("num_ctx"),
    "configured_think":settings.get("think"),
    "configured_keep_alive":settings.get("keep_alive"),
    "configured_URL_present":bool(endpoint),
    "configured_api_key_present":bool(auth),
    "HA_in_container_time_utc":datetime.now(timezone.utc).isoformat(),
    "reachability":{},
}

def request(path, body=None, deadline=4):
    started=time.monotonic()
    if urlsplit(endpoint).scheme not in ("http", "https"):
        return None,{"status":"no_valid_endpoint_scheme"}
    h=dict(headers)
    if body is not None:
        h["Content-Type"]="application/json"
    try:
        req=Request(endpoint+path,
          data=json.dumps(body).encode("utf-8") if body is not None else None,
          headers=h,
          method="POST" if body is not None else "GET")
        with urlopen(req,timeout=deadline) as response:
            value=json.loads(response.read(300000))
            return value,{
                "status":"ok",
                "http_status":response.status,
                "elapsed_ms":round((time.monotonic()-started)*1000),
            }
    except HTTPError as error:
        return None,{
            "status":"http_error", "http_status":error.code,
            "elapsed_ms":round((time.monotonic()-started)*1000),
        }
    except Exception as error:
        return None,{
            "status":"error", "error_type":type(error).__name__,
            "elapsed_ms":round((time.monotonic()-started)*1000),
        }

version,info=request("/api/version")
if isinstance(version,dict) and info["status"]=="ok":
    info["ollama_version"]=str(version.get("version",""))[:50]
report["reachability"]["version"]=info

loaded,info=request("/api/ps")
if isinstance(loaded,dict) and info["status"]=="ok":
    models=loaded.get("models") or []
    info["loaded_models_count"]=len(models)
    info["configured_model_loaded"]=any(
        x.get("name")==model or x.get("model")==model for x in models
    )
    selected=next((x for x in models if x.get("name")==model or x.get("model")==model),{})
    info["selected_model_context_length"]=selected.get("context_length")
    info["selected_model_total_size_bytes"]=selected.get("size")
    info["selected_model_vram_size_bytes"]=selected.get("size_vram")
report["reachability"]["loaded"]=info

tags,info=request("/api/tags")
if isinstance(tags,dict) and info["status"]=="ok":
    models=tags.get("models") or []
    info["available_models_count"]=len(models)
    info["configured_model_exists"]=any(
        x.get("name")==model or x.get("model")==model for x in models
    )
report["reachability"]["tags"]=info

# A single optional generation is conducted through the same configured
# server from the HA container, never through HA's notification service.
# Keep inference explicitly opt-in and bounded.
report["minimal_inference"]={"status":"disabled"}
if os.environ.get("AH_ACTIVE_PROBE")=="1" and model and info.get("status")!="no_valid_endpoint_scheme":
    response,metrics=request("/api/generate",{
        "model":model,
        "prompt":"Respond with OK.",
        "stream":False,
        "think":False,
        "options":{"num_predict":4,"temperature":0,"num_ctx":2048},
        "keep_alive":-1,
    }, deadline=18)
    if isinstance(response,dict) and metrics["status"]=="ok":
        metrics["eval_count"]=response.get("eval_count")
        metrics["total_duration_ms"]=(
            round(response.get("total_duration",0)/1e6)
            if isinstance(response.get("total_duration"),(int,float)) else None
        )
        metrics["done"]=response.get("done")
    report["minimal_inference"]=metrics
print(json.dumps(report,ensure_ascii=False,separators=(",",":"),default=str))
'''

def run(args:list[str], input_text:str|None=None, timeout:int=25):
    try:
        result=subprocess.run(
            args,input=input_text,capture_output=True,text=True,
            check=False,timeout=timeout)
        return result.returncode,result.stdout
    except (OSError,subprocess.TimeoutExpired):
        return None,""

def gpu_vram():
    ans=[]
    for entry in sorted(Path("/sys/class/drm").glob("card*/device/mem_info_vram_total")):
        try:
            total=int(entry.read_text().strip())
            used=int(entry.with_name("mem_info_vram_used").read_text().strip())
        except (OSError,ValueError):
            continue
        if not total:
            continue
        ans.append({
            "card":entry.parents[1].name,
            "vram_total_gib":round(total/1024**3,2),
            "vram_used_gib":round(used/1024**3,2),
            "vram_free_gib":round(max(0,total-used)/1024**3,2),
        })
    return ans

def inspect_status(name):
    code,raw=run(["docker","inspect",name],timeout=8)
    if code!=0:
        return {"status":"unavailable"}
    try:
        status=json.loads(raw)[0].get("State",{})
        return {
            "status":status.get("Status"),
            "started_at":status.get("StartedAt"),
            "restart_count":json.loads(raw)[0].get("RestartCount"),
        }
    except (ValueError,IndexError,TypeError):
        return {"status":"unparseable"}

def probe():
    report={
        "utc":datetime.now(timezone.utc).isoformat(),
        "default_read_only":True,
        "optional_benign_inference":os.environ.get("AH_ACTIVE_PROBE")=="1",
        "ha_docker":inspect_status("homeassistant"),
        "ollama_docker":inspect_status("ollama"),
        "gpu_vram":gpu_vram(),
    }
    code,out=run(["docker","exec","-i",
                   "--env","AH_ACTIVE_PROBE="+(
                       "1" if os.environ.get("AH_ACTIVE_PROBE")=="1" else "0"),
                   "homeassistant","python3","-"],
                 input_text=HA_PROBE,timeout=28)
    if code==0:
        try:
            report["ha_to_ollama"]=json.loads(out)
        except ValueError:
            report["ha_to_ollama"]={"status":"invalid_container_json"}
    else:
        report["ha_to_ollama"]={
            "status":"failed_to_run_probe",
            "exit_code":code,
        }
    code,out=run(["docker","exec","ollama","ollama","ps"],timeout=9)
    if code==0:
        lines=out.splitlines()
        report["ollama_ps"]={
            "status":"ok",
            "loaded_count":max(0,len(lines)-1),
            "model_processor_status":[
                {"name":line.split()[0],
                 "processor": next((v for v in line.split() if "CPU" in v or "GPU" in v),"unavailable"),
                 "context":next((v for v in line.split() if v.isdigit() and int(v)>1024),"unknown")}
                for line in lines[1:5] if line.split()
            ],
        }
    else:
        report["ollama_ps"]={"status":"unavailable"}
    return report

def main():
    report=probe()
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root=Path(os.environ.get("AH_LOG_DIR",
              str(Path.home()/"projects/announcement_hub/logs"))).expanduser()
    root.mkdir(parents=True,exist_ok=True)
    out=root/f"ah-ollama-link-{stamp}.json"
    archive=root/f"ah-ollama-link-{stamp}.tar.gz"
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with tarfile.open(archive,"w:gz") as f:
        f.add(out,arcname=out.name)
    link=report.get("ha_to_ollama",{})
    probes=link.get("reachability",{})
    print("READ_ONLY=" + str(report["default_read_only"] and not report["optional_benign_inference"]))
    print("HA_TO_OLLAMA_VERSION="+str(probes.get("version",{}).get("status","unavailable")))
    print("HA_TO_OLLAMA_MODELS="+str(probes.get("tags",{}).get("status","unavailable")))
    print("HA_TASK_MODEL="+str(link.get("model","unknown")))
    print("HA_TASK_NUM_CTX="+str(link.get("configured_num_ctx","unknown")))
    print("HA_TASK_THINK="+str(link.get("configured_think","unknown")))
    print("VRAM_GPU_CARDS="+str(len(report["gpu_vram"])))
    print("ONE_TOKEN_TEST="+str(link.get("minimal_inference",{}).get("status","disabled")))
    print("EVIDENCE_ARCHIVE="+str(archive))

if __name__=="__main__":
    main()
