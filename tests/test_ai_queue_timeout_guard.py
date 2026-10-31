"""Bound provider waits, keep generate prompts queued, and recover after cooldown."""
from __future__ import annotations

import ast
import asyncio
from datetime import UTC, datetime, timedelta
import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'announcement_hub'
FILTER = ROOT / 'ai_filter.py'
MANAGER = ROOT / 'manager.py'


def test_all_provider_requests_have_a_deadline():
    src = FILTER.read_text()
    assert 'AI_FILTER_PROVIDER_TIMEOUT_SECONDS = 120.0' in src
    tree = ast.parse(src)
    provider_calls = [
        node for node in ast.walk(tree) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'async_call'
    ]
    assert len(provider_calls) == 3
    bounded = [
        node for node in ast.walk(tree) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'wait_for'
        and any(k.arg == 'timeout' for k in node.keywords)
    ]
    assert len(bounded) >= 3


def test_generate_timeout_and_rewrite_circuit_breaker():
    spec = importlib.util.spec_from_file_location('guard_ai_filter', FILTER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.AI_FILTER_PROVIDER_TIMEOUT_SECONDS = 0.02

    source = ast.parse(MANAGER.read_text())
    cls = next(x for x in source.body if isinstance(x, ast.ClassDef)
               and x.name == 'AnnouncementManager')
    selected = [x for x in cls.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                and x.name in {'_ai_provider_cooling', '_async_rewrite_job'}]
    assert len(selected) == 2
    isolated = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
        name='IsolatedManager', bases=[], keywords=[], body=selected,
        decorator_list=[])], type_ignores=[]))
    namespace = {
        'asyncio': asyncio, 'datetime': datetime, 'timedelta': timedelta,
        'UTC': UTC, '_LOGGER': logging.getLogger(__name__),
        'async_filter_announcement': module.async_filter_announcement,
    }
    exec(compile(isolated, str(MANAGER), 'exec'), namespace)
    Manager = namespace['IsolatedManager']

    class Services:
        calls = 0
        slow = True

        async def async_call(self, _domain, _service, _payload, **_kwargs):
            self.calls += 1
            if self.slow:
                await asyncio.sleep(0.2)
            return {'data': {'text_tts': 'Generated result.', 'text_notify': None}}

    class Job:
        def __init__(self, mode):
            self.job_id = mode
            self.ai = {'pending_preprocessing': True,
                       'requested_mode': mode,
                       'source_tts': 'Write an announcement about security.',
                       'source_notify': None,
                       'requested_agent_id': 'ai_task.local',
                       'requested_fallback_agent_id': None,
                       'requested_generate_title': False,
                       'status': 'pending'}
            self.text_tts = self.ai['source_tts']
            self.text_notify = None
            self.routing_mode = 'normal'
            self.tts_text = None
            self.notify_text = None

    async def check():
        service = Services()
        manager = Manager()
        manager.hass = SimpleNamespace(services=service)
        manager.settings = {}
        manager._running = True
        manager._ai_provider_cooldowns = {}
        manager._queue = []
        manager._wake = SimpleNamespace(set=lambda: None)
        manager._schedule_save = lambda: None
        manager._notify_update = lambda: None
        manager._fill_prefetch_slots = lambda: None
        manager._schedule_prefetch = lambda job: None
        gen = Job('generate')
        manager._queue.append(gen)
        await manager._async_rewrite_job(gen)
        assert gen.ai['pending_preprocessing'] is True
        assert gen.ai['status'] == 'waiting_for_ai'
        assert gen.ai['failure_reason'] == 'provider_timeout'
        assert gen.ai['generation_retry_after']
        assert gen.text_tts.startswith('Write an announcement')
        assert gen.tts_text is None
        assert manager._ai_provider_cooling('ai_task.local')
        calls = service.calls

        rewrite = Job('rewrite')
        manager._queue.append(rewrite)
        await manager._async_rewrite_job(rewrite)
        assert service.calls == calls  # Circuit breaker skipped the provider.
        assert not rewrite.ai['pending_preprocessing']
        assert rewrite.ai['failure_reason'] == 'provider_cooldown'
        assert rewrite.text_tts == rewrite.ai.get('source_tts', rewrite.text_tts)

        manager._ai_provider_cooldowns.clear()
        service.slow = False
        gen.ai['generation_retry_after'] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        await manager._async_rewrite_job(gen)
        assert not gen.ai['pending_preprocessing']
        assert gen.text_tts == 'Generated result.'
        assert 'generation_retry_after' not in gen.ai

    asyncio.run(check())
