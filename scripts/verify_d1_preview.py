"""Exercise real D1 persistence using fictitious data on the empty preview only."""

import argparse
import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

from jeuxRPG.multiplayer.d1_client import D1Client, D1StorageError
from jeuxRPG.multiplayer.realtime_store import RuntimeStore


def verify(environment):
    if not urlsplit(environment["RPG_D1_WORKER_URL"]).hostname.startswith("jeux-rpg-d1-preview."):
        raise ValueError("Recette réservée au Worker de préproduction")
    client = D1Client(environment)
    client.health()
    original = client.read_snapshot()
    if any(rows for table, rows in original.items() if table != "meta"):
        raise RuntimeError("La recette exige une base de préproduction vide")
    fence = 4_000_000_000_000_000 + time.time_ns() // 1000
    store = RuntimeStore.load(environment, fence)
    resumed = None
    try:
        password = secrets.token_urlsafe(24)
        account = store.service.account_login("D1Preview", password, signup=True)
        token = account["token"]
        store.service.account_character(token, "create", name="D1Preview", class_name="Knight")
        store.service.command(token, "preview-tutorial", "tutorial")
        store.capture()
        batch = store.pending_batch()
        store.persist(fence, batch)
        store.saved(batch)
        resumed = RuntimeStore.load(environment, fence + 1)
        assert resumed.service.state(token)["player"]["name"] == "D1Preview"
        assert resumed.service.account_login("D1Preview", password)["token"]
        assert resumed.rows("tutorials") == store.rows("tutorials")

        # A higher fence wins even when old and new engines write concurrently.
        def persist(generation):
            try:
                client.persist_checkpoint(generation, {})
                return True
            except RuntimeError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(persist, [fence, fence + 2]))
        assert outcomes == [False, True]
        before = client.read_snapshot()
        player = before["players"][0]
        invalid = {
            ("players", (player["id"],)): {**player, "hp": 1},
            ("account_status", ("nonexistent",)): {"player_id": "nonexistent", "suspended": 0},
        }
        try:
            client.persist_checkpoint(fence + 3, invalid)
        except D1StorageError:
            pass
        else:
            raise AssertionError("Le lot invalide a été accepté")
        assert client.read_snapshot() == before
        return {"health": "ok", "accounts": "ok", "resume": "ok", "fencing": "ok", "atomic_rollback": "ok"}
    finally:
        if resumed is not None:
            resumed.close()
        store.close()
        current = client.read_snapshot()
        from jeuxRPG.multiplayer.realtime_store import KEYS

        cleanup = {
            (table, tuple(row[key] for key in KEYS[table])): None
            for table, rows in current.items() if table != "meta"
            for row in rows
        }
        client.persist_checkpoint(fence + 10, cleanup)
        assert not any(rows for table, rows in client.read_snapshot().items() if table != "meta")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(dotenv_values(args.env_file))))
