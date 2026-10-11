import asyncio
import time

from redis.exceptions import TimeoutError

from jeuxRPG.multiplayer.realtime import Coordinator, RELEASE
from jeuxRPG.multiplayer.realtime_store import RuntimeStore
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
