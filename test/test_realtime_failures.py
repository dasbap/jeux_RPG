import asyncio

from jeuxRPG.multiplayer.realtime import Coordinator
from jeuxRPG.multiplayer.realtime_store import RuntimeStore
from jeuxRPG.multiplayer.service import GameError
from test_realtime import ENV, message


def test_password_work_limit_survives_memory_store_replacement(monkeypatch):
    async def run():
        coordinator = Coordinator(ENV, store=RuntimeStore(ENV))
        calls = []
        def refused(*args):
            calls.append(1)
            raise GameError('unauthorized', 'Compte absent', 401)
        try:
            for attempt in range(11):
                coordinator.store.close()
                coordinator.store = RuntimeStore(ENV)
                monkeypatch.setattr(coordinator.store.service, 'prepare_account_login', refused)
                result = await coordinator.execute(message('/api/account/login', {'username': 'alice', 'password': 'passwordpassword'}))
                assert result['status'] == (401 if attempt < 10 else 429)
            assert len(calls) == 10
        finally:
            await coordinator.close()
    asyncio.run(run())






def test_save_does_not_remove_mutation_that_arrives_during_persistence(monkeypatch):
    async def run():
        store = RuntimeStore(ENV)
        store.request(message('/api/register', {'name': 'Concurrent', 'class_name': 'Knight'}))
        coordinator = Coordinator(ENV, store=store)
        original = store.pending_batch()
        key = next(key for key in original if key[0] == 'players')
        def persist(fence, batch):
            store.pending[key] = {**batch[key], 'name': 'Later'}
        monkeypatch.setattr(store, 'persist', persist)
        await coordinator.save(store, 1)
        assert store.pending[key]['name'] == 'Later'
        assert store.save_count == 1
        store.close()
    asyncio.run(run())




def test_close_waits_for_request_capture_to_finish():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    store = RuntimeStore(ENV)
    capturing, release, closing, closed = Event(), Event(), Event(), Event()
    original_capture = store.capture

    def delayed_capture(*args, **kwargs):
        capturing.set()
        assert release.wait(5)
        return original_capture(*args, **kwargs)

    def close():
        closing.set()
        store.close()
        closed.set()

    store.capture = delayed_capture
    with ThreadPoolExecutor(max_workers=2) as pool:
        request = pool.submit(store.request, message('/api/register', {'name':'Alice', 'class_name':'Knight'}))
        assert capturing.wait(5)
        shutdown = pool.submit(close)
        try:
            assert closing.wait(5)
            assert not closed.wait(.1)
        finally:
            release.set()
        assert request.result(timeout=5)['status'] == 201
        shutdown.result(timeout=5)
    assert closed.is_set()
