"""Stateless Vercel runtime: D1 atomically commits each simulated operation."""

import asyncio
import json
import random
import time

from .d1_client import D1Client, D1StorageError, SnapshotConflict
from .realtime_store import KEYS, TABLES, RuntimeStore
from .runtime_configuration import runtime_environment

RUNTIME_KEYS = {
    **KEYS,
    "presence": ("player_id",),
    "chat": ("id",),
    "request_limits": ("key",),
    "chat_streams": ("player_id", "connection"),
}
PRESENCE_KEY = "d1_runtime_presence"


def changes(before, after):
    result = {}
    for table, keys in RUNTIME_KEYS.items():
        old = {tuple(row[key] for key in keys): row for row in before[table]}
        new = {tuple(row[key] for key in keys): row for row in after[table]}
        for key in old.keys() | new.keys():
            if old.get(key) != new.get(key):
                result[(table, key)] = new.get(key)
    return result


class D1Coordinator:
    def __init__(self, environment, client=None):
        if environment.get("RPG_DATABASE_BACKEND") != "d1":
            raise ValueError("Le moteur serverless requiert D1")
        # Old hosting settings must never silently re-enable a Redis client.
        self.environment = runtime_environment(environment)
        self.client = client or D1Client(self.environment)
        self.connections = self.handshakes = 0
        self.store = None
        self.lock = asyncio.Lock()

    def owner(self):
        return False  # No instance owns durable state or relies on a background tick.

    async def ready(self):
        result = await asyncio.to_thread(self.client.health)
        return result.get("runtime_transactions") == 1

    def transaction(self, message):
        snapshot = self.client.runtime_snapshot()
        metadata = {row["key"]: row["value"] for row in snapshot["meta"]}
        fence = int(metadata.get("runtime_fence", "0"))
        store = RuntimeStore(self.environment, {key: snapshot[key] for key in TABLES})
        try:
            for table in RUNTIME_KEYS.keys() - set(TABLES):
                for row in snapshot[table]:
                    columns = list(row)
                    store.db.execute(
                        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                        tuple(row.values()),
                    )
            for sequence in getattr(snapshot, "sequences", ()):
                cursor = store.db.execute(
                    "UPDATE sqlite_sequence SET seq=max(seq,?) WHERE name=?",
                    (sequence["seq"], sequence["name"]),
                )
                if not cursor.rowcount:
                    store.db.execute(
                        "INSERT INTO sqlite_sequence(name,seq) VALUES(?,?)",
                        (sequence["name"], sequence["seq"]),
                    )
            presence = json.loads(metadata.get(PRESENCE_KEY, "{}"))
            for key, value in presence.items():
                if time.time() - value["seen"] < 60:
                    store.service.runtime_presence[key] = value
            store.service.tick()
            result = store.request(message)
            presence = dict(store.service.runtime_presence.items())
            store.db.execute(
                "INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (PRESENCE_KEY, json.dumps(presence, separators=(",", ":"))),
            )
            after = {table: store.rows(table) for table in RUNTIME_KEYS}
            # Includes transient combat positions/HP, chat and rate limits as well
            # as progress checkpoints. Every successful response survives VM loss.
            self.client.commit_runtime(fence, changes(snapshot, after))
            result["headers"].update(
                {
                    "X-RPG-Runtime": "d1-transaction",
                    "X-RPG-Save-Pending": "0",
                    "X-RPG-D1-Trips": "2",
                }
            )
            return result
        finally:
            store.close()

    async def rpc(self, message):
        started = time.perf_counter()
        async with self.lock:
            for attempt in range(8):
                task = asyncio.create_task(asyncio.to_thread(self.transaction, message))
                try:
                    result = await asyncio.shield(task)
                    trips = str(2 * (attempt + 1))
                    result["headers"]["X-RPG-D1-Trips"] = trips
                    result["headers"]["Server-Timing"] = (
                        f'app;dur={(time.perf_counter() - started) * 1000:.1f}, trips;desc="{trips}"'
                    )
                    return result
                except asyncio.CancelledError:
                    # A caller disconnect cannot interrupt an unacknowledged commit.
                    try:
                        await task
                    finally:
                        raise
                except SnapshotConflict:
                    await asyncio.sleep(
                        random.uniform(0.01, min(0.3, 0.02 * 2**attempt))
                    )
                except D1StorageError as error:
                    raise RuntimeError(
                        "Transaction D1 non confirmee ; reessayer la meme commande"
                    ) from error
            raise RuntimeError("Conflits D1 persistants ; reessayer la meme commande")

    async def flush(self):
        pass  # rpc never acknowledges a pending RAM-only mutation.

    async def release(self):
        pass

    async def close(self):
        pass
