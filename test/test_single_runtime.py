import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from jeuxRPG.multiplayer.d1_client import D1Client, D1StorageError, StaleRuntimeError
from jeuxRPG.multiplayer.distributed import (
    LocalRateLimiter,
    PresenceRegistry,
    build_rate_limiter,
)
from jeuxRPG.multiplayer.realtime import create_app
from jeuxRPG.multiplayer.realtime_store import TABLES
from jeuxRPG.multiplayer.redis_configuration import redis_url
from jeuxRPG.multiplayer.single_runtime import SingleCoordinator

ENV = {
    "RPG_RUNTIME_MODE": "single",
    "RPG_DATABASE_BACKEND": "d1",
    "RPG_D1_WORKER_URL": "https://isolated.invalid",
    "RPG_D1_SERVICE_TOKEN": "test-only-" * 5,
    "RPG_ADMIN_TOKEN": "admin-test-" * 5,
    "RPG_PUBLIC_ORIGIN": "https://engine.test",
    # Stale distributed configuration must never connect to Redis.
    "REDIS_URLS": "invalid-legacy-configuration",
}


@pytest.fixture
def d1(monkeypatch):
    from copy import deepcopy

    state = {"fence": 0, "data": {table: [] for table in TABLES}, "fail": False}

    def health(_):
        if state["fail"]:
            raise D1StorageError("isolated outage")

    def claim(_):
        health(None)
        state["fence"] += 1
        state["data"]["meta"] = [
            row for row in state["data"]["meta"] if row["key"] != "runtime_fence"
        ]
        state["data"]["meta"].append(
            {"key": "runtime_fence", "value": str(state["fence"])}
        )
        return state["fence"], deepcopy(state["data"])

    def persist(_, fence, batch):
        from jeuxRPG.multiplayer.realtime_store import KEYS

        health(None)
        if fence != state["fence"]:
            raise StaleRuntimeError("Moteur remplacé")
        for (table, key), row in batch.items():
            if (table, key) == ("meta", ("runtime_fence",)):
                continue
            state["data"][table] = [
                item
                for item in state["data"][table]
                if tuple(item[column] for column in KEYS[table]) != key
            ]
            if row is not None:
                state["data"][table].append(deepcopy(row))

    monkeypatch.setattr(D1Client, "health", health)
    monkeypatch.setattr(D1Client, "claim_snapshot", claim)
    monkeypatch.setattr(D1Client, "persist_checkpoint", persist)
    return state


def test_single_ignores_redis_and_preserves_local_limits():
    assert redis_url(ENV) is None
    limiter = build_rate_limiter(ENV)
    assert isinstance(limiter, LocalRateLimiter)
    assert limiter.accept("ip", 1)
    assert not limiter.accept("ip", 1)
    assert PresenceRegistry.from_environment(ENV).redis is None


@pytest.mark.parametrize(
    "extra",
    [{"VERCEL": "1"}, {"RPG_DATABASE_BACKEND": "turso"}, {"RPG_RUNTIME_MODE": "typo"}],
)
def test_invalid_runtime_refuses_startup(extra):
    with pytest.raises(ValueError):
        create_app({**ENV, **extra})


def test_d1_outage_refuses_startup(d1):
    d1["fail"] = True
    with pytest.raises(D1StorageError), TestClient(create_app(ENV)):
        pass


def test_https_accounts_save_and_restore_without_redis(d1):
    with TestClient(create_app(ENV), base_url="https://engine.test") as client:
        assert (
            '<meta name="rpg-realtime-url" content="/api/ws">' in client.get("/").text
        )
        assert client.get("/ready").status_code == 200
        assert (
            client.post(
                "/api/register", json={"name": "Legacy", "class_name": "Knight"}
            ).status_code
            != 200
        )
        response = client.post(
            "/api/account/signup",
            json={"username": "alice", "password": "test-password-123"},
            headers={"Origin": "https://engine.test"},
        )
        assert response.status_code == 201, response.text
        token = response.json()["token"]
        assert (
            client.post(
                "/api/account/login", json={}, headers={"Origin": "https://evil.test"}
            ).status_code
            == 403
        )
        with client.websocket_connect(
            "wss://engine.test/api/ws", headers={"Origin": "https://engine.test"}
        ) as socket:
            socket.send_json(
                {
                    "type": "authenticate",
                    "headers": {"Authorization": "Bearer " + token},
                }
            )
            assert socket.receive_json() == {"type": "authenticated"}
            socket.send_json(
                {
                    "id": "me",
                    "path": "/api/account/me",
                    "method": "GET",
                    "headers": {"Authorization": "Bearer " + token},
                }
            )
            result = socket.receive_json()
            assert result["id"] == "me"
            assert result["result"]["status"] == 200
    with TestClient(create_app(ENV), base_url="https://engine.test") as client:
        assert (
            client.get(
                "/api/account/me", headers={"Authorization": "Bearer " + token}
            ).status_code
            == 200
        )
        assert client.app.state.coordinator.store.service.legacy_auth is False


def test_shutdown_failure_keeps_memory_and_allows_retry(d1):
    async def run():
        coordinator = SingleCoordinator(ENV)
        await coordinator.start()
        response = await coordinator.rpc(
            {
                "path": "/api/account/signup",
                "method": "POST",
                "body": {"username": "alice", "password": "test-password-123"},
                "host": "localhost",
                "peer": "127.0.0.1",
                "scheme": "http",
            }
        )
        assert response["status"] == 201
        d1["fail"] = True
        with pytest.raises(RuntimeError, match="Arrêt refusé"):
            await coordinator.close()
        assert coordinator.owner()
        assert coordinator.started
        assert coordinator.store.pending
        assert all(not task.done() for task in coordinator.tasks)
        d1["fail"] = False
        await coordinator.close()
        assert not coordinator.owner()
        restored = SingleCoordinator(ENV)
        await restored.start()
        assert (
            restored.store.db.execute("SELECT username FROM accounts").fetchone()[0]
            == "alice"
        )
        await restored.close()

    asyncio.run(run())


def test_socket_requires_account_authentication(d1):
    with (
        TestClient(create_app(ENV), base_url="https://engine.test") as client,
        client.websocket_connect(
            "wss://engine.test/api/ws", headers={"Origin": "https://engine.test"}
        ) as socket,
    ):
        socket.send_json({"path": "/api/account/me", "method": "GET"})
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == 1008


def test_replaced_engine_cannot_save_or_accept_commands(d1):
    async def run():
        first, second = SingleCoordinator(ENV), SingleCoordinator(ENV)
        await first.start()
        await second.start()
        assert second.fence > first.fence
        await first.write_checkpoint(first.store, {}, first.fence)
        assert first.fenced and not first.owner()
        response = await first.rpc({"path": "/api/account/me"})
        assert response["status"] == 503
        await first.close()
        await second.close()

    asyncio.run(run())
