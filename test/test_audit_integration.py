import asyncio
import json
from contextlib import suppress

import pytest

from jeuxRPG.multiplayer.realtime import Coordinator
from jeuxRPG.multiplayer.realtime_store import RuntimeStore
from scripts.verify_deployment import deployment_base
from test_realtime import ENV, adventure


def test_candidate_url_is_used_without_production_alias():
    url = 'https://jeux-rpg-new-dasbaps-projects.vercel.app'
    assert deployment_base(url) == url
    for invalid in ('https://jeux-rpg.vercel.app', url + '?x=1', url + '#x', 'http://' + url[8:]):
        with pytest.raises(SystemExit):
            deployment_base(invalid)


def test_receipt_capture_never_scans_whole_journal(monkeypatch):
    store = RuntimeStore(ENV)
    player, room = adventure(store)
    original = store.rows
    def rows(table):
        assert table not in ('receipts', 'receipt_expiry')
        return original(table)
    monkeypatch.setattr(store, 'rows', rows)
    store.capture()
    assert store.durable['receipts']
    store.db.execute('DELETE FROM receipts')
    store.capture()
    assert not store.durable['receipts']
    assert any(table == 'receipts' and value is None for (table, key), value in store.pending.items())
    store.close()


def test_legacy_checkpoint_receipts_receive_expiry():
    store = RuntimeStore(ENV)
    adventure(store)
    durable = json.loads(store.snapshot())
    durable.pop('receipt_expiry')
    restored = RuntimeStore(ENV, durable)
    assert restored.db.execute('SELECT COUNT(*) FROM receipt_expiry').fetchone()[0] == len(durable['receipts'])
    restored.close()
    store.close()


def test_relay_password_work_does_not_block_other_players():
    async def run():
        slow_started, finish, fast_received = asyncio.Event(), asyncio.Event(), asyncio.Event()
        coordinator = Coordinator(ENV, store=RuntimeStore(ENV))
        class Redis:
            async def publish(self, channel, payload):
                if any(item['id'] == 'fast' for item in json.loads(payload)):
                    fast_received.set()
        coordinator.redis = Redis()
        calls = []
        async def execute(message):
            calls.append(message)
            if message == 'slow':
                slow_started.set()
                await finish.wait()
            return {'status': 200}
        coordinator.execute = execute
        task = asyncio.create_task(coordinator.pump())
        try:
            await coordinator.received.put({'id': 'slow', 'source': 'other', 'message': 'slow'})
            await asyncio.wait_for(slow_started.wait(), 2)
            await coordinator.received.put({'id': 'slow', 'source': 'other', 'message': 'slow'})
            await coordinator.received.put({'id': 'fast', 'source': 'other', 'message': 'fast'})
            await asyncio.wait_for(fast_received.wait(), 2)
            assert calls.count('slow') == 1
            assert not finish.is_set()
        finally:
            finish.set()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await asyncio.gather(*list(coordinator.relay_tasks.values()))
            coordinator.store.close()
    asyncio.run(run())


def test_forty_concurrent_combat_commands_and_checkpoint_replay():
    import time
    import uuid
    from test_realtime import message
    from test_tutorial import Clock, command
    async def run():
        store = RuntimeStore(ENV, clock=Clock())
        store.service.clock.ratio = 1
        store.service.random = lambda: .5
        coordinator = Coordinator(ENV, store=store)
        requests = []
        for index in range(40):
            token = store.service.register(f'Joueur {index}', ('Knight', 'Mage', 'Archer', 'Priest', 'Necromancien')[index % 5])['token']
            command(store.service, token, 'tutorial')
            state = command(store.service, token, 'explore')
            assert state['tutorial']['battle']
            requests.append(message('/api/commands', {'request_id': uuid.uuid4().hex, 'action': 'hide', 'params': {'session_id': state['id'], 'revision': state['revision'], 'encounter': state['tutorial']['encounter_number']}}, token))
        durations = []
        async def execute(request):
            start = time.perf_counter()
            result = await coordinator.execute(request)
            durations.append((time.perf_counter() - start) * 1000)
            assert result['status'] == 200
            return result
        results = await asyncio.gather(*(execute(request) for request in requests))
        assert len(results) == 40
        restored = RuntimeStore(ENV, json.loads(store.snapshot()))
        for request, result in zip(requests, results):
            replay = restored.request(request)
            assert replay['status'] == 200
            assert replay['body'] == result['body']
        print(f'40 commandes de combat concurrentes, p95 local {sorted(durations)[37]:.2f} ms, maximum {max(durations):.2f} ms')
        restored.close()
        store.close()
    asyncio.run(run())
