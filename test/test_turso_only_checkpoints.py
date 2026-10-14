import asyncio
import json
import time

import pytest
from test_realtime import ENV, adventure

from jeuxRPG.multiplayer.realtime import OWNER, RETIRE_CHECKPOINT, Coordinator
from jeuxRPG.multiplayer.realtime_store import RuntimeStore


class MetadataRedis:
    def __init__(self):
        self.calls = []
        self.retired = False

    async def eval(self, script, *args):
        assert script in (OWNER, RETIRE_CHECKPOINT)
        self.calls.append(args)
        self.retired = self.retired or script == RETIRE_CHECKPOINT
        return 1


def solo_inventory(store):
    player, session_id = adventure(store)
    row = store.db.execute("SELECT data FROM tutorials WHERE session_id=?", (session_id,)).fetchone()
    party = json.loads(row[0])
    party["inventory"].setdefault(player["player"]["id"], {})["private_solo_material"] = 1
    store.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), session_id))
    store.capture()
    assert "private_solo_material" in store.snapshot()
    return player


def test_solo_inventory_is_persisted_to_turso_without_sending_snapshot_to_redis(monkeypatch):
    async def run():
        store = RuntimeStore(ENV)
        try:
            player = solo_inventory(store)
            redis = MetadataRedis()
            coordinator = Coordinator(ENV, redis=redis, store=store)
            coordinator.local = False
            coordinator.deadline = time.monotonic() + 25
            persisted = []
            monkeypatch.setattr(store, "persist", lambda fence, batch: persisted.append(batch))
            await coordinator.save(store, 1)
            assert persisted and not store.pending
            assert len(redis.calls) == 1
            assert redis.calls[0] == (1, coordinator.prefix + "lease", coordinator.uid + ":1")
            assert player["token"] not in json.dumps(redis.calls)
            assert "inventory" not in json.dumps(redis.calls)
            assert "private_solo_material" not in json.dumps(redis.calls)
        finally:
            store.close()
    asyncio.run(run())


@pytest.mark.parametrize("failed_persistence", [False, True])
def test_legacy_redis_checkpoint_is_retired_only_after_pending_data_reaches_turso(monkeypatch, failed_persistence):
    async def run():
        source = RuntimeStore(ENV)
        try:
            solo_inventory(source)
            saved = json.dumps({"durable": json.loads(source.snapshot()), "pending": [{"table": table, "key": key, "row": row} for (table, key), row in source.pending_batch().items()]})
            assert "private_solo_material" in saved
            expected = source.pending_batch()
        finally:
            source.close()
        redis = MetadataRedis()
        coordinator = Coordinator(ENV, redis=redis)
        persisted = []
        def persist(store, fence, batch):
            assert not redis.retired
            persisted.append(batch)
            if failed_persistence:
                raise OSError("fixture Turso indisponible")
        monkeypatch.setattr(RuntimeStore, "persist", persist)
        if failed_persistence:
            with pytest.raises(OSError):
                await coordinator.restore_legacy_checkpoint(saved)
            assert not redis.retired
        else:
            assert await coordinator.restore_legacy_checkpoint(saved)
            assert redis.retired
        assert persisted == [expected]
        assert "inventory" not in json.dumps(redis.calls)
    asyncio.run(run())
