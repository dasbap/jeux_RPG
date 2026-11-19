import json

import pytest
from dotenv import dotenv_values

from scripts.prepare_vercel_preview import PROJECT, TEAM, WORKER, configuration, prepare


@pytest.fixture
def preview_environment():
    return {
        "RPG_D1_WORKER_URL": WORKER,
        "RPG_D1_SERVICE_TOKEN": "fictitious-token",
        "RPG_ADMIN_TOKEN": "a" * 40,
        "REDIS_URL": "rediss://fixture.invalid:6379",
        "RPG_RELEASE_SHA": "a" * 40,
    }


@pytest.mark.parametrize(
    "url",
    [
        "https://jeux-rpg-d1.dasbap-jeux-rpg.workers.dev",
        WORKER + ".attacker.invalid",
        "",
        WORKER + "/other",
    ],
)
def test_preview_refuses_other_databases(preview_environment, url):
    with pytest.raises(ValueError, match="fictif"):
        configuration({**preview_environment, "RPG_D1_WORKER_URL": url})


@pytest.mark.parametrize("key", ["RPG_D1_SERVICE_TOKEN", "RPG_ADMIN_TOKEN"])
def test_preview_refuses_missing_or_redacted_credentials(preview_environment, key):
    with pytest.raises(ValueError, match="absente"):
        configuration({**preview_environment, key: "[SENSITIVE]"})


def test_preview_replaces_pulled_settings_without_production_secrets(
    tmp_path, preview_environment
):
    folder = tmp_path / ".vercel"
    folder.mkdir()
    path = folder / ".env.preview.local"
    path.write_text(
        "TURSO_AUTH_TOKEN='production'\nRPG_D1_SERVICE_TOKEN='[SENSITIVE]'\n"
    )
    settings = {"framework": "python", "buildCommand": "python scripts/check_vercel.py"}
    project = folder / "project.json"
    project.write_text(
        json.dumps({"projectId": PROJECT, "orgId": TEAM, "settings": settings})
    )
    prepare(tmp_path, {**preview_environment, "UNRELATED_SECRET": "production"})
    assert json.loads(project.read_text())["settings"] == settings
    values = dotenv_values(path)
    assert values["RPG_D1_SERVICE_TOKEN"] == "fictitious-token"
    assert values["RPG_RUNTIME_MODE"] == "d1"
    assert "REDIS_URL" not in values
    assert values["RPG_RESET_TEST_PLAYERS"] == "0"
    assert "TURSO_AUTH_TOKEN" not in values and "UNRELATED_SECRET" not in values


def test_invalid_configuration_does_not_overwrite_local_files(
    tmp_path, preview_environment
):
    with pytest.raises(ValueError, match="Commit"):
        prepare(tmp_path, {**preview_environment, "RPG_RELEASE_SHA": "wrong"})
    assert not (tmp_path / ".vercel").exists()


def test_preview_refuses_to_retarget_an_existing_project(tmp_path, preview_environment):
    folder = tmp_path / ".vercel"
    folder.mkdir()
    project = folder / "project.json"
    project.write_text(json.dumps({"projectId": "another-project", "orgId": TEAM}))
    before = project.read_bytes()
    with pytest.raises(ValueError, match="autre projet"):
        prepare(tmp_path, preview_environment)
    assert project.read_bytes() == before
    assert not (folder / ".env.preview.local").exists()
