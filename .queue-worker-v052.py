from pathlib import Path
import json

ROOT=Path(".")
C=ROOT/"custom_components"/"announcement_hub"

def rep(path, old, new):
    text=path.read_text(encoding="utf-8")
    count=text.count(old)
    if count!=1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    path.write_text(text.replace(old,new,1),encoding="utf-8")

m=C/"manager.py"

rep(m,
'''            "prefetching": sorted(
                job_id
                for job_id, task in self._prefetch_tasks.items()
                if not task.done()
            ),
''',
'''            "prefetching": sorted(
                job_id
                for job_id, task in self._prefetch_tasks.items()
                if not task.done()
            ),
            "worker_alive": bool(
                self._worker_task is not None and not self._worker_task.done()
            ),
''')

rep(m,
'''        self._running = True
        self._worker_task = self.entry.async_create_background_task(
            self.hass,
            self._async_worker(),
            f"{DOMAIN} worker",
        )
''',
'''        self._running = True
        self._ensure_worker()
''')

anchor='''    async def async_stop(self) -> None:
'''
text=m.read_text(encoding="utf-8")
if anchor not in text:
    raise SystemExit("worker helper anchor missing")
helpers='''    def _ensure_worker(self) -> None:
        """Ensure exactly one live queue worker exists while the manager runs."""
        if not self._running:
            return
        if self._worker_task is not None and not self._worker_task.done():
            return

        task = self.entry.async_create_background_task(
            self.hass,
            self._async_worker(),
            f"{DOMAIN} worker",
        )
        self._worker_task = task

        def _worker_done(done_task: asyncio.Task[None]) -> None:
            if self._worker_task is done_task:
                self._worker_task = None
            if done_task.cancelled():
                return
            error = done_task.exception()
            if error is not None:
                _LOGGER.error(
                    "Announcement Hub queue worker stopped unexpectedly",
                    exc_info=(type(error), error, error.__traceback__),
                )
            if self._running:
                # A permanent worker must never leave accepted jobs stranded.
                # Restart on the next loop turn so an unexpected worker failure
                # cannot recurse synchronously.
                self.hass.loop.call_soon(self._ensure_worker)
                if self._queue:
                    self._wake.set()
            self._notify_update()

        task.add_done_callback(_worker_done)

'''
m.write_text(text.replace(anchor,helpers+anchor,1),encoding="utf-8")

rep(m,
'''        self._queue.append(job)
        self._schedule_prefetch(job)
        self._schedule_save()
        self._wake.set()
''',
'''        self._queue.append(job)
        self._schedule_prefetch(job)
        self._schedule_save()
        self._ensure_worker()
        self._wake.set()
''')

rep(m,
'''    async def async_update_config(self) -> None:
        self._notify_update()
''',
'''    async def async_update_config(self) -> None:
        # Options changes must not leave a dead worker behind. This is cheap
        # when the worker is healthy and self-heals a previously stopped task.
        self._ensure_worker()
        if self._queue:
            self._wake.set()
        self._notify_update()
''')

# version
rep(C/"const.py",'VERSION: Final = "0.5.1"','VERSION: Final = "0.5.2"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.5.1":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.5.2"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# tests
test=ROOT/"tests"/"test_queue_worker_supervision.py"
test.write_text('''"""Regression contracts for the self-healing serialized queue worker."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "custom_components" / "announcement_hub" / "manager.py"


def test_worker_is_self_healing_and_send_checks_it() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    assert "def _ensure_worker(self)" in source
    assert "self._ensure_worker()" in source
    assert "self._wake.set()" in source
    assert "self.hass.loop.call_soon(self._ensure_worker)" in source
    assert '"worker_alive": bool(' in source


def test_worker_remains_a_config_entry_background_task() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    assert "self.hass.async_create_task(" not in source
    assert source.count("self.entry.async_create_background_task(") == 2
''',encoding="utf-8")

res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8")
text=text.replace('assert manifest["version"] == "0.5.1"','assert manifest["version"] == "0.5.2"')
res.write_text(text,encoding="utf-8")

ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.5.2 - 2026-10-02

- Added supervision for the permanent serialized queue worker.
- Every accepted announcement now verifies that a live worker exists before the
  wake event is signalled.
- An unexpectedly stopped worker is logged with its real exception and restarted
  automatically on the next event-loop turn.
- Options updates also verify worker health and wake pending work.
- Exposed worker_alive in diagnostics/status data.
- The worker remains a ConfigEntry background task; no normal Home Assistant
  startup-blocking task was introduced.

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied Announcement Hub 0.5.2 queue-worker supervision")
