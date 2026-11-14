import json

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from test_single_runtime import ENV, d1  # noqa: F401
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from jeuxRPG.multiplayer.container_host import configuration
from jeuxRPG.multiplayer.host_configuration import TEST_WORKER
from scripts.prepare_render_preview import prepare

PREVIEW = {
    **ENV,
    "RPG_D1_WORKER_URL": TEST_WORKER,
    "RPG_PUBLIC_ORIGIN": "https://engine-test.onrender.com",
    "RPG_DEPLOYMENT_STAGE": "preview",
    "RPG_RUNTIME_REALMS": "1",
}


@pytest.mark.parametrize(
    "overrides",
    [
        {"RPG_D1_WORKER_URL": "https://production.invalid"},
        {"RPG_DEPLOYMENT_STAGE": "production"},
        {"RPG_PUBLIC_ORIGIN": "http://engine.onrender.com"},
        {"RPG_PUBLIC_ORIGIN": "https://onrender.com.evil.invalid"},
        {"RPG_PUBLIC_ORIGIN": "https://engine.onrender.com/path"},
        {"WEB_CONCURRENCY": "2"},
        {"VERCEL": "1"},
        {"RPG_RUNTIME_MODE": "distributed"},
        {"PORT": "0"},
        {"PORT": "not-a-port"},
    ],
)
def test_container_refuses_unsafe_configuration(overrides):
    with pytest.raises(ValueError):
        configuration({**PREVIEW, **overrides})


def test_container_serves_https_origin_behind_ingress(d1):  # noqa: F811
    config = configuration(PREVIEW)
    assert config.host == "0.0.0.0" and config.port == 8080 and config.workers == 1
    app = ProxyHeadersMiddleware(config.app, trusted_hosts="*")
    with TestClient(app, base_url="http://engine-test.onrender.com") as client:
        headers = {
            "X-Forwarded-Proto": "https",
            "Origin": "https://engine-test.onrender.com",
        }
        assert client.get("/ready").status_code == 200
        response = client.post(
            "/api/account/signup",
            headers=headers,
            json={"username": "alice", "password": "test-password-123"},
        )
        assert response.status_code == 201
        token = response.json()["token"]
        with client.websocket_connect(
            "ws://engine-test.onrender.com/api/ws", headers=headers
        ) as socket:
            socket.send_json(
                {
                    "type": "authenticate",
                    "headers": {"Authorization": "Bearer " + token},
                }
            )
            assert socket.receive_json() == {"type": "authenticated"}
        rejected = client.post(
            "/api/account/signup",
            headers={**headers, "Origin": "https://evil.invalid"},
            json={"username": "mallory", "password": "test-password-123"},
        )
        assert rejected.status_code == 403
    assert [row["username"] for row in d1["data"]["accounts"]] == ["alice"]


def test_render_injected_hostname_and_port():
    environment = {
        **PREVIEW,
        "RENDER_EXTERNAL_HOSTNAME": "assigned.onrender.com",
        "PORT": "10000",
    }
    environment.pop("RPG_PUBLIC_ORIGIN")
    config = configuration(environment)
    assert config.port == 10000
    assert (
        config.app.state.coordinator.environment["RPG_PUBLIC_ORIGIN"]
        == "https://assigned.onrender.com"
    )
    with pytest.raises(ValueError):
        configuration({**environment, "RENDER_EXTERNAL_HOSTNAME": "evil.invalid"})


def test_private_environment_does_not_copy_other_secrets(tmp_path, d1):  # noqa: F811
    source, destination = tmp_path / "source.env", tmp_path / "private/runtime.env"
    source.write_text(
        "\n".join(f"{key}={value}" for key, value in PREVIEW.items())
        + "\nDUCKDNS_TOKEN=unrelated-secret\n",
        encoding="utf-8",
    )
    prepare(PREVIEW["RPG_PUBLIC_ORIGIN"], source, destination)
    saved = dotenv_values(destination, interpolate=False)
    assert saved["RPG_D1_SERVICE_TOKEN"] == PREVIEW["RPG_D1_SERVICE_TOKEN"]
    assert "DUCKDNS_TOKEN" not in saved and "REDIS_URLS" not in saved
    assert d1["fence"] == 0
    with pytest.raises(FileExistsError):
        prepare(PREVIEW["RPG_PUBLIC_ORIGIN"], source, destination)


def test_missing_credentials_never_create_runtime_file(tmp_path):
    destination = tmp_path / "runtime.env"
    with pytest.raises(ValueError):
        prepare("https://engine.onrender.com", tmp_path / "missing.env", destination)
    assert not destination.exists()


def test_render_secret_file_is_loaded_only_for_runtime_tokens(tmp_path, monkeypatch):
    secret_file = tmp_path / "rpg-runtime.json"
    monkeypatch.setattr("jeuxRPG.multiplayer.container_host.SECRET_FILE", secret_file)
    environment = {
        key: value
        for key, value in PREVIEW.items()
        if key not in {"RPG_D1_SERVICE_TOKEN", "RPG_ADMIN_TOKEN"}
    }
    secret_values = {
        key: PREVIEW[key] for key in ("RPG_D1_SERVICE_TOKEN", "RPG_ADMIN_TOKEN")
    }
    secret_file.write_text(json.dumps(secret_values), encoding="utf-8")
    config = configuration(environment)
    assert (
        config.app.state.coordinator.environment["RPG_D1_SERVICE_TOKEN"]
        == PREVIEW["RPG_D1_SERVICE_TOKEN"]
    )
    with pytest.raises(ValueError, match="deux valeurs"):
        configuration({**environment, "RPG_ADMIN_TOKEN": "different-" * 5})
    secret_values["RPG_D1_WORKER_URL"] = "https://production.invalid"
    secret_file.write_text(json.dumps(secret_values), encoding="utf-8")
    with pytest.raises(ValueError, match="deux jetons"):
        configuration(environment)
