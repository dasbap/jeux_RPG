"""Deploy only the Oracle test Worker onto the existing fictitious D1 database."""

import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path

from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "cloudflare/wrangler.oracle-test.json"
LOCAL_ENV = ROOT / ".data/oracle-test/runtime.env"
TEST_URL = "https://jeux-rpg-oracle-test.dasbap-jeux-rpg.workers.dev"


def validate_target(configuration):
    databases = configuration.get("d1_databases", [])
    if (
        configuration.get("name") != "jeux-rpg-oracle-test"
        or len(databases) != 1
        or databases[0].get("database_name") != "jeux-rpg-preview"
        or databases[0].get("database_id") != "bf29ab72-c4a8-440b-a106-da6badde250c"
    ):
        raise ValueError("Cible Oracle de test invalide ; déploiement refusé")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wrangler-js", type=Path, required=True)
    args = parser.parse_args()
    validate_target(json.loads(CONFIG.read_text(encoding="utf-8")))
    command = ["node", str(args.wrangler_js)]
    # Read every durable table before deploying; never rebind the import preview.
    from jeuxRPG.multiplayer.realtime_store import TABLES

    queries = ";".join(
        f"SELECT '{table}' AS table_name,count(*) AS count FROM {table}"
        for table in TABLES
        if table != "meta"
    )
    result = subprocess.run(
        command
        + [
            "d1",
            "execute",
            "jeux-rpg-preview",
            "--config",
            str(CONFIG),
            "--remote",
            "--command",
            queries,
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    if any(
        row["count"] for item in json.loads(result.stdout) for row in item["results"]
    ):
        raise RuntimeError("La base fictive contient des données ; déploiement refusé")
    LOCAL_ENV.parent.mkdir(parents=True, exist_ok=True)
    if not LOCAL_ENV.exists():
        descriptor = os.open(LOCAL_ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
    token = dotenv_values(LOCAL_ENV).get(
        "RPG_D1_SERVICE_TOKEN"
    ) or secrets.token_urlsafe(48)
    for key, value in {
        "RPG_RUNTIME_MODE": "single",
        "RPG_DATABASE_BACKEND": "d1",
        "RPG_D1_WORKER_URL": TEST_URL,
        "RPG_D1_SERVICE_TOKEN": token,
        "RPG_ADMIN_TOKEN": dotenv_values(LOCAL_ENV).get("RPG_ADMIN_TOKEN")
        or secrets.token_urlsafe(48),
        "RPG_RUNTIME_REALMS": "1",
    }.items():
        set_key(LOCAL_ENV, key, value)
    subprocess.run(
        command + ["secret", "put", "RPG_D1_SERVICE_TOKEN", "--config", str(CONFIG)],
        input=token,
        text=True,
        check=True,
    )
    subprocess.run(command + ["deploy", "--config", str(CONFIG)], check=True)
    print("Worker Oracle de test déployé ; secrets dans .data/oracle-test/runtime.env")


if __name__ == "__main__":
    main()
