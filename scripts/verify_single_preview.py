"""Real loopback WebSockets and remote D1, restricted to the fictitious Oracle test."""

import argparse
import asyncio
import json
import math
import secrets
import socket
import time
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from dotenv import dotenv_values
from websockets.asyncio.client import connect

from jeuxRPG.multiplayer import tactics, tutorial
from jeuxRPG.multiplayer.d1_client import D1Client, D1StorageError
from jeuxRPG.multiplayer.realtime import create_app
from jeuxRPG.multiplayer.realtime_store import KEYS, TABLES, RuntimeStore
from jeuxRPG.multiplayer.single_runtime import SingleCoordinator
from scripts.deploy_oracle_test import LOCAL_ENV, ROOT, TEST_URL


def validate_environment(environment):
    if (
        environment.get("RPG_D1_WORKER_URL") != TEST_URL
        or environment.get("RPG_RUNTIME_MODE") != "single"
        or environment.get("RPG_DATABASE_BACKEND") != "d1"
        or environment.get("VERCEL")
    ):
        raise ValueError("Recette réservée au Worker Oracle fictif en mode single/D1")


def seed(environment, users, combat_users):
    """Build fictitious accounts off the load path, without changing password limits."""
    validate_environment(environment)
    client = D1Client(environment)
    client.health()
    snapshot = client.read_snapshot()
    if any(rows for table, rows in snapshot.items() if table != "meta"):
        raise RuntimeError("La recette exige une base fictive vide")
    fence, snapshot = client.claim_snapshot()
    store = RuntimeStore(environment, snapshot)
    password = secrets.token_urlsafe(24)
    clients = []
    try:
        for index in range(users):
            name = f"OracleTest{index:02}"
            account = store.service.account_login(name, password, signup=True)
            token = account["token"]
            selected = store.service.account_character(
                token, "create", name=name, class_name="Knight"
            )
            session = store.service.command(token, secrets.token_hex(16), "tutorial")[
                "session"
            ]
            party = json.loads(
                store.db.execute(
                    "SELECT data FROM tutorials WHERE session_id=?", (session["id"],)
                ).fetchone()[0]
            )
            combat = index < combat_users
            if combat:
                tutorial.spawn(
                    party, store.service._now(), lambda: 0.2, [], origin="explore"
                )
                for character in party["characters"].values():
                    character["stats"]["hp"].update(max=10000, current=10000)
            else:
                party.update(
                    step="village", position="rosee", visited=["clearing", "rosee"]
                )
            store.db.execute(
                "UPDATE tutorials SET data=? WHERE session_id=?",
                (json.dumps(party), session["id"]),
            )
            store.capture()
            batch = store.pending_batch()
            store.persist(fence, batch)
            store.saved(batch)
            clients.append(
                {
                    "account": account["account"]["id"],
                    "token": token,
                    "combat": combat,
                    "player": selected["selected"],
                    "session": session["id"],
                }
            )
        return clients, password
    except Exception:
        known = {row["id"] for row in store.rows("accounts")}
        persisted = {row["id"] for row in client.read_snapshot()["accounts"]}
        if not persisted.issubset(known):
            raise RuntimeError(
                "Comptes inconnus : nettoyage de la préparation refusé"
            ) from None
        cleanup(environment, persisted)
        raise
    finally:
        store.close()


@asynccontextmanager
async def engine(environment):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    settings = {**environment, "RPG_PUBLIC_ORIGIN": f"https://127.0.0.1:{port}"}
    app = create_app(settings)
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="warning", access_log=False, lifespan="on")
    )
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(90):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("Le moteur ASGI n'a pas démarré")
                await asyncio.sleep(0.05)
        yield app.state.coordinator, origin
    finally:
        server.should_exit = True
        try:
            async with asyncio.timeout(90):
                await task
        finally:
            listener.close()


def latency(values):
    ordered = sorted(values)
    if not ordered:
        return None
    return {
        name: round(
            ordered[min(len(ordered) - 1, math.ceil(len(ordered) * percentile) - 1)], 2
        )
        for name, percentile in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99), ("max", 1))
    }


async def rpc(socket_client, message, counts):
    started = time.monotonic()
    await socket_client.send(json.dumps(message))
    async with asyncio.timeout(15):
        while True:
            raw = await socket_client.recv()
            counts["bytes"] += len(raw.encode())
            result = json.loads(raw)
            if result.get("type") == "state":
                counts["pushes"] += 1
            if result.get("id") == message["id"]:
                return result["result"], (time.monotonic() - started) * 1000


def movement(state, cycle):
    session = state.get("session") or {}
    party = session.get("tutorial") or {}
    battle = party.get("battle")
    if not battle:
        return None
    unit = battle.get("players", {}).get(session.get("me"))
    if not unit:
        return None
    destination = [2, 8] if cycle % 8 == 0 else [1, 8]
    route = tactics.path(battle["map"], unit["position"], destination)
    if not route:
        return None
    return {
        "session_id": session["id"],
        "revision": session["revision"],
        "encounter": party["encounter_number"],
        "x": destination[0],
        "y": destination[1],
        "path": route,
    }


async def load(coordinator, origin, clients, seconds):
    gate, ready = asyncio.Event(), asyncio.Queue()
    handshakes = asyncio.Semaphore(8)
    results = []

    async def player(index, client):
        counts = {
            "bytes": 0,
            "pushes": 0,
            "states": 0,
            "actions": 0,
            "conflicts": 0,
            "latencies": [],
            "action_latencies": [],
            "errors": [],
        }
        announced = False
        try:
            async with AsyncExitStack() as stack:
                async with handshakes:
                    transport = await stack.enter_async_context(
                        connect(
                            origin.replace("http", "ws", 1) + "/api/ws",
                            origin=origin,
                            max_size=4_000_000,
                            open_timeout=30,
                        )
                    )
                    await transport.send(
                        json.dumps(
                            {
                                "type": "authenticate",
                                "headers": {
                                    "Authorization": "Bearer " + client["token"]
                                },
                            }
                        )
                    )
                    response = json.loads(await asyncio.wait_for(transport.recv(), 30))
                    if response != {"type": "authenticated"}:
                        raise RuntimeError("Authentification WebSocket refusée")
                announced = True
                ready.put_nowait(True)
                await gate.wait()
                deadline = time.monotonic() + seconds
                cycle = 0
                while time.monotonic() < deadline:
                    started = time.monotonic()
                    request = {
                        "id": f"{index}-{cycle}",
                        "path": "/api/state",
                        "method": "GET",
                        "headers": {"Authorization": "Bearer " + client["token"]},
                    }
                    response, elapsed = await rpc(transport, request, counts)
                    if response["status"] != 200:
                        raise RuntimeError(f"État HTTP {response['status']}")
                    counts["states"] += 1
                    counts["latencies"].append(elapsed)
                    params = (
                        movement(response["body"], cycle)
                        if client["combat"] and cycle % 4 == 0
                        else None
                    )
                    if params:
                        response, elapsed = await rpc(
                            transport,
                            {
                                **request,
                                "id": f"move-{index}-{cycle}",
                                "path": "/api/commands",
                                "method": "POST",
                                "body": {
                                    "request_id": secrets.token_hex(16),
                                    "action": "battle_move",
                                    "params": params,
                                },
                            },
                            counts,
                        )
                        if response["status"] == 200:
                            counts["actions"] += 1
                            counts["action_latencies"].append(elapsed)
                        elif response["status"] == 409:
                            counts["conflicts"] += 1
                        else:
                            raise RuntimeError(f"Commande HTTP {response['status']}")
                    cycle += 1
                    await asyncio.sleep(max(0, 1 - (time.monotonic() - started)))
        except Exception as error:
            counts["errors"].append(f"{type(error).__name__}: {error}")
            if not announced:
                ready.put_nowait(False)
        finally:
            results.append(counts)

    tasks = [
        asyncio.create_task(player(index, client))
        for index, client in enumerate(clients)
    ]
    try:
        async with asyncio.timeout(60):
            authenticated = [await ready.get() for _ in clients]
        peak = coordinator.connections
        if not all(authenticated) or peak != len(clients):
            raise RuntimeError(f"Connexions simultanées : {peak}/{len(clients)}")
        gate.set()
        await asyncio.gather(*tasks)
    finally:
        gate.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    errors = [error for result in results for error in result["errors"]]
    return {
        "simultaneous_authenticated_sockets": peak,
        "duration_seconds": seconds,
        "combat_sessions": sum(client["combat"] for client in clients),
        "town_sessions": sum(not client["combat"] for client in clients),
        "state_requests": sum(result["states"] for result in results),
        "state_pushes_received": sum(result["pushes"] for result in results),
        "movement_actions": sum(result["actions"] for result in results),
        "action_conflicts": sum(result["conflicts"] for result in results),
        "received_bytes": sum(result["bytes"] for result in results),
        "state_latency_ms": latency(
            [value for result in results for value in result["latencies"]]
        ),
        "movement_latency_ms": latency(
            [value for result in results for value in result["action_latencies"]]
        ),
        "errors": errors,
    }


async def outage_and_recovery(coordinator, origin, client):
    async with coordinator.lock:
        store = coordinator.store
        party = json.loads(
            store.db.execute(
                "SELECT data FROM tutorials WHERE session_id=?", (client["session"],)
            ).fetchone()[0]
        )
        character = party["characters"][client["player"]]
        character["exp"] += 37
        expected = character["exp"]
        store.db.execute(
            "UPDATE tutorials SET data=? WHERE session_id=?",
            (json.dumps(party), client["session"]),
        )
        store.capture()
    original = store.persist

    def unavailable(*_):
        raise D1StorageError("Panne de transport injectée dans le moteur de test")

    store.persist = unavailable
    try:
        await coordinator.flush()
        assert store.pending and store.last_save_error
        async with httpx.AsyncClient(base_url=origin) as http:
            assert (await http.get("/ready")).status_code == 503
        try:
            await coordinator.close()
        except RuntimeError:
            assert coordinator.owner() and coordinator.started and store.pending
        else:
            raise AssertionError("Fermeture acceptée sans confirmation D1")
    finally:
        store.persist = original
    await coordinator.flush()
    assert not store.pending and not store.last_save_error
    async with httpx.AsyncClient(base_url=origin) as http:
        assert (await http.get("/ready")).status_code == 200
    return expected


def cleanup(environment, expected_accounts):
    validate_environment(environment)
    client = D1Client(environment)
    snapshot = client.read_snapshot()
    if {row["id"] for row in snapshot["accounts"]} != expected_accounts:
        raise RuntimeError(
            "Comptes inattendus : nettoyage refusé avant prise de génération"
        )
    fence, data = client.claim_snapshot()
    if {row["id"] for row in data["accounts"]} != expected_accounts:
        raise RuntimeError("Comptes inattendus : nettoyage refusé")
    # Child tables precede their parents. Small batches stay below Worker limits.
    for table in reversed(TABLES):
        if table == "meta":
            continue
        rows = data[table]
        for offset in range(0, len(rows), 200):
            batch = {
                (table, tuple(row[key] for key in KEYS[table])): None
                for row in rows[offset : offset + 200]
            }
            client.persist_checkpoint(fence, batch)
    assert not any(
        rows for table, rows in client.read_snapshot().items() if table != "meta"
    )


async def verify(environment, users=40, combat_users=20, seconds=30):
    validate_environment(environment)
    if (
        not 1 <= users <= 40
        or not 0 <= combat_users <= users
        or not 1 <= seconds <= 240
    ):
        raise ValueError("Charge autorisée : 1–40 joueurs, 1–240 secondes")
    clients, password = await asyncio.to_thread(seed, environment, users, combat_users)
    accounts = {fixture["account"] for fixture in clients}
    try:
        report = await exercise(environment, clients, password, seconds, combat_users)
        report["cleanup"] = "all fictitious game rows removed; metadata retained"
        return report
    finally:
        await asyncio.to_thread(cleanup, environment, accounts)


async def exercise(environment, clients, password, seconds, combat_users):
    report = {
        "engine": "local Python ASGI",
        "storage": "remote Cloudflare D1, fictitious jeux-rpg-preview",
        "transport": "real loopback TCP WebSockets, without TLS/proxy",
        "production_capacity_validated": False,
    }
    async with engine(environment) as (coordinator, origin):
        report["load"] = await load(coordinator, origin, clients, seconds)
        if report["load"]["errors"]:
            raise RuntimeError(
                "Erreurs de charge : " + json.dumps(report["load"]["errors"])
            )
        if combat_users and not report["load"]["movement_actions"]:
            raise RuntimeError("Aucun déplacement de combat mesuré")
        await coordinator.flush()
        assert not coordinator.store.pending and not coordinator.store.last_save_error
        report["save_after_load"] = {
            "confirmed": True,
            "failures": coordinator.save_failures,
            "checkpoints": coordinator.store.save_count,
        }
        expected = await outage_and_recovery(coordinator, origin, clients[0])
        report["injected_transport_outage"] = (
            "pending preserved; readiness 503; close refused; retry confirmed"
        )
    async with (
        engine(environment) as (coordinator, origin),
        httpx.AsyncClient(base_url=origin, timeout=30) as http,
    ):
        response = await http.post(
            "/api/account/login",
            json={"username": "OracleTest00", "password": password},
        )
        assert response.status_code == 200
        for fixture in clients:
            response = await http.get(
                "/api/state",
                headers={"Authorization": "Bearer " + fixture["token"]},
            )
            assert response.status_code == 200
            assert response.json()["player"]["id"] == fixture["player"]
        party = json.loads(
            coordinator.store.db.execute(
                "SELECT data FROM tutorials WHERE session_id=?",
                (clients[0]["session"],),
            ).fetchone()[0]
        )
        assert party["characters"][clients[0]["player"]]["exp"] == expected
        report["restart"] = {
            "accounts_and_sessions_restored": len(clients),
            "password_login": "ok",
            "progression": "ok",
        }
        report["reconnect"] = await load(coordinator, origin, clients, 2)
        assert not report["reconnect"]["errors"]
        replacement = SingleCoordinator(environment)
        await replacement.start()
        try:
            async with asyncio.timeout(12):
                while (await http.get("/ready")).status_code != 503:
                    await asyncio.sleep(0.2)
            assert coordinator.fenced
            response = await http.get(
                "/api/account/me",
                headers={"Authorization": "Bearer " + clients[0]["token"]},
            )
            assert response.status_code == 503
            report["fencing"] = (
                "replacement generation allocated; old engine detects rejection and refuses commands"
            )
        finally:
            await replacement.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=LOCAL_ENV)
    parser.add_argument("--users", type=int, default=40)
    parser.add_argument("--combat-users", type=int, default=20)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".data/oracle-test/report.json"
    )
    args = parser.parse_args()
    report = asyncio.run(
        verify(
            dict(dotenv_values(args.env_file)),
            args.users,
            args.combat_users,
            args.seconds,
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
