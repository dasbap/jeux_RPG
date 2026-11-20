import asyncio
import json
import signal
import socket

import httpx
import pytest
import uvicorn
from test_single_runtime import ENV, d1  # noqa: F401

from jeuxRPG.multiplayer.host import PersistentServer
from jeuxRPG.multiplayer.host_configuration import TEST_WORKER, validate
from jeuxRPG.multiplayer.realtime import create_app
from scripts.render_oracle_cloud_init import ASSETS, render


def test_signal_waits_for_d1_and_blocks_new_mutations(d1, monkeypatch):  # noqa: F811
    async def run():
        notifications = []
        monkeypatch.setattr("jeuxRPG.multiplayer.host.notify", notifications.append)
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        environment = {**ENV, "RPG_PUBLIC_ORIGIN": f"https://127.0.0.1:{port}"}
        app = create_app(environment)
        coordinator = app.state.coordinator
        server = PersistentServer(
            uvicorn.Config(app, log_level="error", access_log=False),
            coordinator,
            retry_seconds=0.02,
        )
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(5):
                while not server.started:
                    await asyncio.sleep(0.01)
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
                response = await http.post(
                    "/api/account/signup",
                    json={"username": "alice", "password": "test-password-123"},
                )
                assert response.status_code == 201
                token = response.json()["token"]
                response = await coordinator.rpc(
                    {
                        "path": "/api/account/character",
                        "method": "POST",
                        "body": {
                            "action": "create",
                            "name": "Savedhero",
                            "class_name": "Knight",
                        },
                        "host": "localhost",
                        "peer": "127.0.0.1",
                        "scheme": "http",
                        "headers": {"Authorization": "Bearer " + token},
                    }
                )
                assert response["status"] == 200
                d1["fail"] = True
                server.handle_exit(signal.SIGTERM, None)
                async with asyncio.timeout(5):
                    while not coordinator.draining:
                        await asyncio.sleep(0.01)
                assert not task.done() and not server.should_exit
                assert coordinator.store.pending
                assert (await http.get("/ready")).status_code == 503
                response = await http.post(
                    "/api/account/signup",
                    json={"username": "bob", "password": "test-password-123"},
                )
                assert response.status_code == 503
                server.handle_exit(signal.SIGINT, None)
                server.handle_exit(signal.SIGINT, None)
                assert not server.force_exit
                d1["fail"] = False
            async with asyncio.timeout(5):
                await task
            assert d1["data"]["players"][0]["name"] == "Savedhero"
            assert len(d1["data"]["accounts"]) == 1
            assert any(item.startswith("READY=1") for item in notifications)
            assert any(item.startswith("STOPPING=1") for item in notifications)
        finally:
            d1["fail"] = False
            server.stop_requested = True
            if not task.done():
                async with asyncio.timeout(5):
                    await task
            listener.close()

    asyncio.run(run())


@pytest.mark.parametrize("domain", [None, "engine.example.org"])
@pytest.mark.skipif(not ASSETS.exists(), reason="Kit Oracle retiré : migration Northflank")
def test_cloud_init_contains_pinned_code_without_runtime_secrets(domain):
    data = json.loads(render("a" * 40, domain).split("\n", 1)[1])
    assert data["runcmd"] == [
        ["/usr/local/sbin/jeux-rpg-bootstrap", "a" * 40, domain or ""]
    ]
    assert not any(file["path"].endswith("runtime.env") for file in data["write_files"])
    assert data["package_upgrade"] is False


@pytest.mark.parametrize(
    "revision,domain",
    [
        ("master", None),
        ("a" * 40, "https://example.org"),
        ("a" * 40, "bad;command.example"),
    ],
)
def test_cloud_init_rejects_unpinned_or_shell_arguments(revision, domain):
    with pytest.raises(ValueError):
        render(revision, domain)


def test_host_configuration_refuses_production_before_start():
    environment = {
        **ENV,
        "RPG_DEPLOYMENT_STAGE": "preview",
        "RPG_D1_WORKER_URL": TEST_WORKER,
        "RPG_RUNTIME_REALMS": "1",
    }
    validate(environment)
    with pytest.raises(ValueError):
        validate(
            {
                **environment,
                "RPG_D1_WORKER_URL": "https://jeux-rpg-d1.dasbap-jeux-rpg.workers.dev",
            }
        )
    with pytest.raises(ValueError):
        validate({**environment, "RPG_DEPLOYMENT_STAGE": "production"})
