from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('.')
COMPONENT = ROOT / 'custom_components' / 'announcement_hub'


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected exactly one match, found {count}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


manager = COMPONENT / 'manager.py'

replace_once(
    manager,
    '''        if not job.successful_channels:
            detail = "; ".join(
                f"{channel}: {error}"
                for channel, error in job.channel_errors.items()
            )
            raise HomeAssistantError(
                "No configured delivery channel succeeded"
                + (f": {detail}" if detail else "")
            )
''',
    '''        # A job whose configured outputs all stayed unavailable is a valid
        # no-op after the availability window. Only actual recorded channel
        # errors can turn a no-delivery job into a failure.
        if not job.successful_channels and job.channel_errors:
            detail = "; ".join(
                f"{channel}: {error}"
                for channel, error in job.channel_errors.items()
            )
            raise HomeAssistantError(
                "No configured delivery channel succeeded"
                + (f": {detail}" if detail else "")
            )
''',
)

replace_once(
    manager,
    '''        """Deliver ready outputs and retry unavailable/failed outputs in one window."""
''',
    '''        """Deliver ready outputs, wait once, then silently skip unavailable ones."""
''',
)

replace_once(
    manager,
    '''        for item in pending:
            channel_name = channel(item)
            if last_error := last_errors.get(channel_name):
                error = (
                    f"Delivery did not succeed within {timeout:g}s; "
                    f"last error: {last_error}"
                )
            else:
                error = f"Output remained unavailable for {timeout:g}s"
            self._record_channel_failure(job, channel_name, error)
''',
    '''        # Remaining items are unavailable outputs, not announcement errors.
        # Keep this at debug level for diagnostics without creating Repairs/log
        # warnings or marking the job completed_with_errors.
        if pending:
            skipped = {
                channel(item): last_errors.get(channel(item), "unavailable")
                for item in pending
            }
            _LOGGER.debug(
                "Announcement %s skipped unavailable output(s) after %ss: %s",
                job.job_id,
                f"{timeout:g}",
                skipped,
            )
''',
)

replace_once(
    manager,
    '''            if not await self._async_wait_player_available(player, job):
                self._record_channel_failure(
                    job,
                    f"player:{player}",
                    f"Output remained unavailable for {self._availability_timeout:g}s",
                )
                return
''',
    '''            if not await self._async_wait_player_available(player, job):
                return
''',
)

replace_once(
    manager,
    '''        for entity_id in pending:
            self._record_channel_failure(
                job,
                f"snapcast:{entity_id}",
                f"Output remained unavailable for {timeout:g}s",
            )
''',
    '''        if pending:
            _LOGGER.debug(
                "Announcement %s skipped unavailable Snapcast output(s) after %ss: %s",
                job.job_id,
                f"{timeout:g}",
                pending,
            )
''',
)

replace_once(
    manager,
    '''        if not await self._async_wait_player_available(player, job):
            raise HomeAssistantError(
                f"TTS media player {player} remained unavailable for "
                f"{self._availability_timeout:g}s"
            )
''',
    '''        if not await self._async_wait_player_available(player, job):
            return
''',
)

replace_once(
    manager,
    '''            engines = await self._async_available_tts_engines(job)
            if not engines:
                raise HomeAssistantError("No selected TTS engine is available")
''',
    '''            engines = await self._async_available_tts_engines(job)
            if not engines:
                return
''',
)

manifest_path = COMPONENT / 'manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
if manifest.get('version') != '0.3.3':
    raise SystemExit(f"Unexpected manifest version: {manifest.get('version')}")
manifest['version'] = '0.3.4'
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

replace_once(
    COMPONENT / 'const.py',
    'VERSION: Final = "0.3.3"',
    'VERSION: Final = "0.3.4"',
)

replace_once(
    ROOT / 'tests' / 'test_resources.py',
    'assert manifest["version"] == "0.3.3"',
    'assert manifest["version"] == "0.3.4"',
)

replace_once(
    ROOT / 'tests' / 'test_resources.py',
    '    assert "Delivery did not succeed within" in manager\n',
    '    assert "skipped unavailable output(s)" in manager\n',
)

test_path = ROOT / 'tests' / 'test_unavailable_output_policy.py'
test_path.write_text(
    '''"""Regression contracts for silent handling of unavailable outputs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "announcement_hub"


def test_unavailable_outputs_do_not_create_channel_errors() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "then silently skip unavailable ones" in manager
    assert "skipped unavailable output(s)" in manager
    assert "self._record_channel_failure(job, channel_name, error)" not in manager
    assert "Delivery did not succeed within" not in manager


def test_all_unavailable_outputs_are_a_valid_no_op() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "if not job.successful_channels and job.channel_errors:" in manager
    assert "if not await self._async_wait_player_available(player, job):\\n                return" in manager
    assert "skipped unavailable Snapcast output(s)" in manager


def test_silent_skip_change_does_not_regress_task_lifecycle() -> None:
    manager = (COMPONENT / "manager.py").read_text(encoding="utf-8")
    assert "self.hass.async_create_task(" not in manager
    assert manager.count("self.entry.async_create_background_task(") == 2
''',
    encoding='utf-8',
)

changelog = ROOT / 'CHANGELOG.md'
text = changelog.read_text(encoding='utf-8')
heading = '# Changelog\n\n'
if not text.startswith(heading):
    raise SystemExit('Unexpected changelog header')
entry = '''## 0.3.4 - 2026-10-02

- Treat outputs that remain unavailable after the configured wait window as
  skipped outputs instead of delivery errors.
- Stop emitting warning logs, channel-failed events, and
  `completed_with_errors` solely because a TV, phone, Snapcast client, media
  player, or TTS engine is offline.
- Let an announcement complete as a successful no-op when every matching output
  stays unavailable; actual configuration and processing errors still fail.
- Preserve the config-entry background-task lifecycle fix so this behavior does
  not participate in Home Assistant startup.

'''
changelog.write_text(heading + entry + text[len(heading):], encoding='utf-8')

print('Applied Announcement Hub 0.3.4 silent-unavailable-output policy')
