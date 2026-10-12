import asyncio
import time

from redis.exceptions import TimeoutError

from jeuxRPG.multiplayer.realtime import Coordinator, RELEASE
from jeuxRPG.multiplayer.realtime_store import RuntimeStore
from jeuxRPG.multiplayer.service import GameError
from test_realtime import ENV, message


class ReleaseRedis:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    async def eval(self, script, *args):
        assert script == RELEASE
        self.calls += 1
        if self.fail:
            raise TimeoutError('Redis indisponible')
        return 1


def owner(store, redis):
    coordinator = Coordinator(ENV, redis=redis, store=store)
    coordinator.local = False
    coordinator.deadline = time.monotonic() + 25
    return coordinator


def test_release_keeps_unsaved_changes_when_flush_fails():
    async def run():
        store = RuntimeStore(ENV)
        try:
            store.request(message('/api/register', {'name': 'Alice', 'class_name': 'Knight'}))
            redis = ReleaseRedis()
            coordinator = owner(store, redis)
            async def failed_flush():
                store.last_save_error = True
            coordinator.flush = failed_flush
            await coordinator.release()
            assert coordinator.store is store
            assert coordinator.owner()
            assert store.pending
            assert redis.calls == 0
        finally:
            store.close()
    asyncio.run(run())


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


def test_release_timeout_is_retryable_and_does_not_close_store():
    async def run():
        store = RuntimeStore(ENV)
        redis = ReleaseRedis(fail=True)
        coordinator = owner(store, redis)
        await coordinator.release()
        assert coordinator.store is store
        assert store.db.execute('SELECT 1').fetchone()[0] == 1
        redis.fail = False
        await coordinator.release()
        assert coordinator.store is None
        assert not coordinator.owner()
        assert redis.calls == 2
    asyncio.run(run())


def test_command_waits_for_release_and_refuses_closed_owner():
    async def run():
        entered = asyncio.Event()
        proceed = asyncio.Event()
        class DelayedRedis(ReleaseRedis):
            async def eval(self, script, *args):
                entered.set()
                await proceed.wait()
                return await super().eval(script, *args)
        store = RuntimeStore(ENV)
        coordinator = owner(store, DelayedRedis())
        release = asyncio.create_task(coordinator.release())
        await entered.wait()
        command = asyncio.create_task(coordinator.execute(message('/api/state', token='missing')))
        await asyncio.sleep(0)
        assert not command.done()
        proceed.set()
        await release
        assert (await command)['status'] == 503
        assert coordinator.store is None
    asyncio.run(run())


def test_checkpoint_rejection_never_acknowledges_or_persists(monkeypatch):
    async def run():
        store = RuntimeStore(ENV)
        store.request(message('/api/register', {'name': 'Pending', 'class_name': 'Knight'}))
        class RejectedRedis:
            async def eval(self, *args):
                return 0
        coordinator = owner(store, RejectedRedis())
        def forbidden(*args):
            raise AssertionError('Rejected lease must not persist')
        monkeypatch.setattr(store, 'persist', forbidden)
        batch = store.pending_batch()
        await coordinator.save(store, batch, store.snapshot(), 1)
        assert store.pending == batch and store.last_save_error
        assert coordinator.checkpoint_rejections == 1
        assert store.due is not None and store.save_count == 0
        store.close()
    asyncio.run(run())


def test_combined_redis_turso_failures_then_retry_preserves_mutations(monkeypatch):
    async def run():
        store = RuntimeStore(ENV)
        store.request(message('/api/register', {'name': 'Recovery', 'class_name': 'Knight'}))
        class FlakyRedis:
            failures = 1
            async def eval(self, *args):
                if self.failures:
                    self.failures -= 1
                    raise TimeoutError('isolated Redis outage')
                return 1
        coordinator = owner(store, FlakyRedis())
        calls = []
        def persist(fence, batch):
            calls.append(batch)
            if len(calls) == 1:
                raise OSError('isolated Turso outage')
        monkeypatch.setattr(store, 'persist', persist)
        original = store.pending_batch()
        for _ in range(2):
            await coordinator.save(store, original, store.snapshot(), 1)
            assert store.pending == original and store.last_save_error
        await coordinator.save(store, original, store.snapshot(), 1)
        assert not store.pending and store.save_count == 1
        assert coordinator.save_failures == 2 and calls[1] == original
        store.close()
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
        await coordinator.save(store, original, store.snapshot(), 1)
        assert store.pending[key]['name'] == 'Later'
        assert store.save_count == 1
        store.close()
    asyncio.run(run())


def test_owner_loss_reports_pending_mutations_before_closing(caplog):
    async def run():
        class LostLease:
            async def eval(self, *args):
                return 0
        store = RuntimeStore(ENV)
        store.request(message('/api/register', {'name': 'LostOwner', 'class_name': 'Knight'}))
        count = len(store.pending)
        assert count > 0
        coordinator = owner(store, LostLease())
        await coordinator.elect()
        assert coordinator.store is None and not coordinator.owner()
        assert coordinator.owner_pending_drops == count
        assert 'mutations locales en attente' in caplog.text
    asyncio.run(run())


def test_simultaneous_owner_loss_does_not_close_store_twice():
    async def run():
        class LostLease:
            calls = 0
            both_returned = asyncio.Event()
            async def eval(self, *args):
                self.calls += 1
                if self.calls == 2:
                    self.both_returned.set()
                return 0
        store = RuntimeStore(ENV)
        store.request(message('/api/register', {'name': 'ConcurrentLoss', 'class_name': 'Knight'}))
        count = len(store.pending)
        redis = LostLease()
        coordinator = owner(store, redis)
        async with coordinator.lock:
            tasks = [asyncio.create_task(coordinator.elect()) for _ in range(2)]
            await asyncio.wait_for(redis.both_returned.wait(), 1)
        await asyncio.gather(*tasks)
        assert coordinator.store is None
        assert coordinator.owner_pending_drops == count
    asyncio.run(run())
