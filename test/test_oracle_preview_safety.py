import asyncio
import json
from pathlib import Path

import pytest

from jeuxRPG.multiplayer.d1_client import D1Client
from scripts.deploy_oracle_test import TEST_URL, validate_target
from scripts.verify_single_preview import cleanup, seed, verify

ENV = {
    "RPG_D1_WORKER_URL": TEST_URL,
    "RPG_RUNTIME_MODE": "single",
    "RPG_DATABASE_BACKEND": "d1",
}


@pytest.mark.parametrize(
    "url",
    [
        "https://jeux-rpg-d1.dasbap-jeux-rpg.workers.dev",
        "https://jeux-rpg-d1-preview.dasbap-jeux-rpg.workers.dev",
        TEST_URL + "/production",
    ],
)
def test_production_and_import_preview_refused_before_network(monkeypatch, url):
    def forbidden(*_):
        raise AssertionError("La cible interdite ne doit recevoir aucun appel")

    monkeypatch.setattr(D1Client, "__init__", forbidden)
    environment = {**ENV, "RPG_D1_WORKER_URL": url}
    with pytest.raises(ValueError):
        asyncio.run(verify(environment))
    with pytest.raises(ValueError):
        seed(environment, 1, 0)
    with pytest.raises(ValueError):
        cleanup(environment, set())


@pytest.mark.parametrize(
    "identifier",
    [
        "c76f19e2-8a32-4072-b4aa-51ff2984a979",  # production
        "494fd86e-648f-44c7-9a89-85ce6b74ac2c",  # imported preview
    ],
)
def test_deployment_refuses_real_database_bindings(identifier):
    configuration = json.loads(
        (
            Path(__file__).resolve().parents[1] / "cloudflare/wrangler.oracle-test.json"
        ).read_text()
    )
    configuration["d1_databases"][0]["database_id"] = identifier
    with pytest.raises(ValueError):
        validate_target(configuration)


def test_cleanup_refuses_unknown_accounts_before_claiming_generation(monkeypatch):
    monkeypatch.setattr(D1Client, "__init__", lambda *_: None)
    monkeypatch.setattr(
        D1Client, "read_snapshot", lambda *_: {"accounts": [{"id": "unknown"}]}
    )

    def forbidden(*_):
        raise AssertionError("Ne pas prendre le contrôle ni supprimer des lignes")

    monkeypatch.setattr(D1Client, "claim_snapshot", forbidden)
    monkeypatch.setattr(D1Client, "persist_checkpoint", forbidden)
    with pytest.raises(RuntimeError, match="avant prise"):
        cleanup(ENV, {"our-fixture"})
