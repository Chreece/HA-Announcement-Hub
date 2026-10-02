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

# Add wall-clock parsing imports.
rep(m,
"import asyncio\n",
"import asyncio\nfrom datetime import UTC, datetime\n",
)

old_worker='''    async def _async_worker(self) -> None:
        while self._running:
            if not self._queue:
                self._wake.clear()
                if not self._queue:
                    await self._wake.wait()
                continue

            job = self._queue.popleft()
            self._current = job
'''
new_worker='''    async def _async_worker(self) -> None:
        while self._running:
            job = self._next_runnable_job()
            if job is None:
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=0.25)
                except TimeoutError:
                    pass
                continue

            self._queue.remove(job)
            self._current = job
'''
rep(m,old_worker,new_worker)

anchor='''    async def _async_process_job(self, job: AnnouncementJob) -> None:
'''
helpers='''    def _pending_age_seconds(self, job: AnnouncementJob) -> float:
        """Return how long a pending job has been waiting."""
        try:
            created = datetime.fromisoformat(job.created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            return max(0.0, (datetime.now(UTC) - created).total_seconds())
        except (TypeError, ValueError):
            return 0.0

    def _job_has_ready_visual_output(self, job: AnnouncementJob) -> bool:
        if not job.notify_text or not job.notify_outputs:
            return False
        return any(
            notify_output_available(self.hass, output)
            for output in resolve_notify_outputs(self.hass, job.notify_outputs)
            if output_matches_areas(
                job.notify_output_areas.get(output.ref, output.area_id),
                job.outputs,
            )
        )

    def _job_has_ready_companion_tts(self, job: AnnouncementJob) -> bool:
        if not job.tts_text or not job.companion_tts_entries:
            return False
        return any(
            companion_output_available(self.hass, output)
            for output in resolve_companion_tts_outputs(
                self.hass, job.companion_tts_entries
            )
            if output_matches_areas(
                job.companion_tts_entry_areas.get(
                    output.entry_id, output.area_id
                ),
                job.outputs,
            )
        )

    def _job_has_ready_server_tts(self, job: AnnouncementJob) -> bool:
        if (
            not job.tts_text
            or not job.server_tts_enabled
            or not job.tts_engines
            or not job.tts_media_player
        ):
            return False
        player = self.hass.states.get(job.tts_media_player)
        if player is None or player.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            return False
        if not any(
            tts_engine_available(self.hass, engine)
            for engine in job.tts_engines
        ):
            return False
        if not job.snapcast_clients:
            return True
        return any(
            self._snapcast_output_available(entity_id)
            for entity_id in job.snapcast_clients
            if not job.outputs
            or job.snapcast_client_areas.get(
                entity_id, entity_area_id(self.hass, entity_id)
            )
            in set(job.outputs)
        )

    def _job_runnable_now(self, job: AnnouncementJob) -> bool:
        """Return whether at least one frozen delivery channel can run now."""
        return (
            self._job_has_ready_visual_output(job)
            or self._job_has_ready_server_tts(job)
            or self._job_has_ready_companion_tts(job)
        )

    def _expire_waiting_job(self, job: AnnouncementJob) -> None:
        """Finish a never-runnable pending job silently after its wait window."""
        if job not in self._queue:
            return
        self._queue.remove(job)
        job.status = "completed"
        job.finished_at = utcnow_iso()
        job.error = None
        self._prefetch_tasks.pop(job.job_id, None)
        self._last = job
        self._fire_event(EVENT_FINISHED, job)
        _LOGGER.debug(
            "Announcement %s expired after waiting %ss for a runnable output",
            job.job_id,
            f"{self._availability_timeout:g}",
        )
        self._schedule_save()
        self._notify_update()

    def _next_runnable_job(self) -> AnnouncementJob | None:
        """Pick the oldest runnable job without letting waiters block the queue."""
        timeout = self._availability_timeout
        for job in tuple(self._queue):
            if self._job_runnable_now(job):
                return job
            if timeout <= 0 or self._pending_age_seconds(job) >= timeout:
                self._expire_waiting_job(job)
        return None

'''
text=m.read_text(encoding="utf-8")
if anchor not in text:
    raise SystemExit("process-job anchor missing")
m.write_text(text.replace(anchor,helpers+anchor,1),encoding="utf-8")

# Wake the scheduler when prefetch finishes, since a TTS job may become runnable.
rep(m,
'''            self._schedule_save()
            self._notify_update()

        task.add_done_callback(_done)
''',
'''            self._schedule_save()
            self._wake.set()
            self._notify_update()

        task.add_done_callback(_done)
''')

# v0.5.3
rep(C/"const.py",'VERSION: Final = "0.5.2"','VERSION: Final = "0.5.3"')
manifest=C/"manifest.json"
j=json.loads(manifest.read_text(encoding="utf-8"))
if j.get("version")!="0.5.2":
    raise SystemExit(f"unexpected manifest version {j.get('version')}")
j["version"]="0.5.3"
manifest.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")

# Regression tests.
(ROOT/"tests"/"test_nonblocking_queue_scheduler.py").write_text('''"""Contracts for non-blocking pending queue scheduling."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "custom_components" / "announcement_hub" / "manager.py"


def test_worker_scans_for_runnable_jobs_instead_of_popping_fifo_head() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    worker = source[source.index("async def _async_worker"):source.index("async def _async_process_job")]
    assert "job = self._next_runnable_job()" in worker
    assert "self._queue.popleft()" not in worker
    assert "self._queue.remove(job)" in worker


def test_waiting_jobs_expire_without_blocking_newer_ready_jobs() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    assert "def _next_runnable_job(" in source
    assert "if self._job_runnable_now(job):" in source
    assert "self._pending_age_seconds(job) >= timeout" in source
    assert "def _expire_waiting_job(" in source


def test_scheduler_readiness_covers_visual_server_and_companion_outputs() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    assert "def _job_has_ready_visual_output(" in source
    assert "def _job_has_ready_server_tts(" in source
    assert "def _job_has_ready_companion_tts(" in source
    assert "notify_output_available(self.hass, output)" in source
    assert "self._snapcast_output_available(entity_id)" in source
    assert "companion_output_available(self.hass, output)" in source


def test_scheduler_keeps_startup_safe_background_task_lifecycle() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    assert "self.hass.async_create_task(" not in source
    assert source.count("self.entry.async_create_background_task(") == 2
''',encoding="utf-8")

res=ROOT/"tests"/"test_resources.py"
text=res.read_text(encoding="utf-8").replace(
    'assert manifest["version"] == "0.5.2"',
    'assert manifest["version"] == "0.5.3"',
)
res.write_text(text,encoding="utf-8")

ch=ROOT/"CHANGELOG.md"
text=ch.read_text(encoding="utf-8")
head="# Changelog\n\n"
entry='''## 0.5.3 - 2026-10-02

- Replaced strict FIFO dequeueing with a readiness scheduler.
- A pending job whose outputs are unavailable stays pending until its availability
  timeout, but no longer blocks newer jobs that can run immediately.
- The scheduler always picks the oldest currently runnable job, preserving order
  among runnable work while allowing unavailable waiters to be overtaken.
- Timed-out jobs with no runnable output complete as silent no-ops.
- Actual announcement execution remains strictly serialized: only one job is
  processing at a time, so announcements do not interrupt each other.
- Readiness checks cover visual notify outputs, server TTS/Snapcast, and
  Companion App TTS.
- No new long-lived tasks were added; the startup-safe ConfigEntry worker
  lifecycle remains unchanged.

'''
if not text.startswith(head):
    raise SystemExit("unexpected changelog")
ch.write_text(head+entry+text[len(head):],encoding="utf-8")

print("Applied Announcement Hub 0.5.3 readiness scheduler")
