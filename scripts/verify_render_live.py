"""Bounded WebSocket probe of the isolated Render test service, never production."""

import argparse
import asyncio
import json
import os
import secrets
import time
from pathlib import Path

import httpx
from websockets.asyncio.client import connect

from scripts.verify_single_preview import latency

ORIGIN = "https://jeux-rpg-render-test.onrender.com"
ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".data/render/load-clients.json"


def save_private(data):
    PRIVATE.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(PRIVATE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(data, stream)


async def prepare(users):
    data = (
        json.loads(PRIVATE.read_text())
        if PRIVATE.exists()
        else {
            "prefix": "RenderLoad" + secrets.token_hex(3),
            "password": secrets.token_urlsafe(24),
            "clients": [],
        }
    )
    async with httpx.AsyncClient(
        base_url=ORIGIN, headers={"Origin": ORIGIN}, timeout=40
    ) as http:
        health = await http.get("/ready")
        assert health.status_code == 200 and health.json() == {"status": "ready"}
        while len(data["clients"]) < users:
            index = len(data["clients"])
            username = data["prefix"] + f"{index:02}"
            for _attempt in range(6):
                response = await http.post(
                    "/api/account/signup",
                    json={"username": username, "password": data["password"]},
                )
                if response.status_code != 429:
                    break
                await asyncio.sleep(15)
            assert response.status_code == 201, f"Signup HTTP {response.status_code}"
            token = response.json()["token"]
            client = {
                "username": username,
                "token": token,
                "character": False,
                "adventure": False,
            }
            data["clients"].append(client)
            save_private(data)
            print(json.dumps({"accounts_prepared": len(data["clients"])}), flush=True)
            # Respect the service's password-work limit of ten attempts/minute.
            if len(data["clients"]) < users:
                await asyncio.sleep(7)
        for client in data["clients"][:users]:
            headers = {"Authorization": "Bearer " + client["token"]}
            if not client["character"]:
                response = await http.post(
                    "/api/account/character",
                    headers=headers,
                    json={
                        "action": "create",
                        "name": client["username"],
                        "class_name": "Knight",
                    },
                )
                assert response.status_code == 200, (
                    f"Character HTTP {response.status_code}"
                )
                client["character"] = True
                save_private(data)
            if not client["adventure"]:
                response = await http.post(
                    "/api/commands",
                    headers=headers,
                    json={
                        "request_id": secrets.token_hex(16),
                        "action": "tutorial",
                        "params": {},
                    },
                )
                assert response.status_code == 200, (
                    f"Adventure HTTP {response.status_code}"
                )
                client["adventure"] = True
                save_private(data)
    return data["clients"][:users]


async def probe(clients, seconds):
    gate, ready = asyncio.Event(), asyncio.Queue()
    handshakes = asyncio.Semaphore(4)
    state = {
        "bytes": 0,
        "pushes": 0,
        "states": 0,
        "latencies": [],
        "errors": [],
        "connected": 0,
    }

    async def player(index, client):
        announced = False
        try:
            async with handshakes:
                socket = await connect(
                    ORIGIN.replace("https", "wss", 1) + "/api/ws",
                    origin=ORIGIN,
                    max_size=4_000_000,
                    open_timeout=40,
                )
                await socket.send(
                    json.dumps(
                        {
                            "type": "authenticate",
                            "headers": {"Authorization": "Bearer " + client["token"]},
                        }
                    )
                )
                assert json.loads(await asyncio.wait_for(socket.recv(), 30)) == {
                    "type": "authenticated"
                }
            try:
                state["connected"] += 1
                announced = True
                ready.put_nowait(True)
                await gate.wait()
                deadline = time.monotonic() + seconds
                cycle = 0
                while time.monotonic() < deadline:
                    identifier = f"{index}-{cycle}"
                    started = time.monotonic()
                    await socket.send(
                        json.dumps(
                            {
                                "id": identifier,
                                "path": "/api/state",
                                "method": "GET",
                                "headers": {
                                    "Authorization": "Bearer " + client["token"]
                                },
                            }
                        )
                    )
                    async with asyncio.timeout(20):
                        while True:
                            raw = await socket.recv()
                            state["bytes"] += len(raw.encode())
                            if state["bytes"] > 128 * 1024 * 1024:
                                raise RuntimeError("Traffic budget exceeded")
                            message = json.loads(raw)
                            if message.get("type") == "state":
                                state["pushes"] += 1
                            if message.get("id") == identifier:
                                assert message["result"]["status"] == 200
                                state["states"] += 1
                                state["latencies"].append(
                                    (time.monotonic() - started) * 1000
                                )
                                break
                    cycle += 1
                    await asyncio.sleep(max(0, 1 - (time.monotonic() - started)))
            finally:
                await socket.close()
        except Exception as error:
            state["errors"].append(type(error).__name__)
            if not announced:
                ready.put_nowait(False)

    tasks = [
        asyncio.create_task(player(index, client))
        for index, client in enumerate(clients)
    ]
    try:
        async with asyncio.timeout(120):
            outcomes = [await ready.get() for _ in clients]
        started = time.monotonic()
        gate.set()
        await asyncio.gather(*tasks)
        return {
            "players": len(clients),
            "authenticated_connections": state["connected"],
            "all_connected": all(outcomes),
            "configured_seconds": seconds,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "state_responses": state["states"],
            "pushes": state["pushes"],
            "received_bytes": state["bytes"],
            "latency_ms": latency(state["latencies"]),
            "errors": state["errors"],
            "combat_load": False,
            "production_capacity_validated": False,
        }
    finally:
        gate.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def run(users, seconds):
    clients = await prepare(users)
    report = await probe(clients, seconds)
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.get(ORIGIN + "/ready")
        report["ready_after"] = response.status_code == 200 and response.json() == {
            "status": "ready"
        }
    output = ROOT / f".data/render/load{users}.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)
    if report["errors"] or not report["all_connected"] or not report["ready_after"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, choices=range(1, 41), default=1)
    parser.add_argument("--seconds", type=int, choices=range(5, 31), default=15)
    args = parser.parse_args()
    asyncio.run(run(args.users, args.seconds))


if __name__ == "__main__":
    main()
