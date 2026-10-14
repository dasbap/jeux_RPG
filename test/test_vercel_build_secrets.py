import pytest
from dotenv import dotenv_values

from scripts.prepare_vercel_environment import prepare


def test_prebuilt_environment_replaces_secret_placeholders_and_preserves_redis(tmp_path):
    path = tmp_path / "production.local"
    path.write_text("TURSO_AUTH_TOKEN='[SENSITIVE]'\nRPG_RUNTIME_REALMS='[SENSITIVE]'\nREDIS_URL='redis://fixture'\nOTHER_SECRET='[SENSITIVE]'\n")
    secrets = {"TURSO_DATABASE_URL": "libsql://fixture", "TURSO_AUTH_TOKEN": "fixture-token", "RPG_ADMIN_TOKEN": "fixture-admin"}
    prepare(path, secrets)
    values = dotenv_values(path)
    assert all(values[key] == value for key, value in secrets.items())
    assert values["REDIS_URL"] == "redis://fixture"
    assert values["RPG_RUNTIME_REALMS"] == "1"
    assert values["RPG_RESET_TEST_PLAYERS"] == "0"
    assert "OTHER_SECRET" not in values
    assert "[SENSITIVE]" not in path.read_text()


@pytest.mark.parametrize("value", ["", "[SENSITIVE]"])
def test_missing_ci_secret_fails_before_rewriting_configuration(tmp_path, value):
    path = tmp_path / "production.local"
    path.write_text("REDIS_URL='redis://fixture'\n")
    with pytest.raises(ValueError, match="TURSO_DATABASE_URL"):
        prepare(path, {"TURSO_DATABASE_URL": value})
    assert path.read_text() == "REDIS_URL='redis://fixture'\n"
