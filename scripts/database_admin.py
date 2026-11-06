"""Read-only administration checks for the selected database backend."""

import argparse
import json
import os

from jeuxRPG.multiplayer.d1_client import D1Client
from jeuxRPG.multiplayer.realtime_store import TABLES, RuntimeStore
from jeuxRPG.multiplayer.storage_configuration import database_backend


def inspect(environment, operation):
    if operation not in ("connexion", "schema", "integrite"):
        raise ValueError("Opération d'administration invalide")
    backend = database_backend(environment)
    report = {"backend": backend, "operation": operation, "ok": True}
    if backend == "d1":
        client = D1Client(environment)
        report["version"] = client.health()["version"]
        if operation == "schema":
            report["durable_tables"] = list(TABLES)
        elif operation == "integrite":
            store = RuntimeStore(environment, client.read_snapshot())
            try:
                if store.db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise RuntimeError("Relations invalides")
            finally:
                store.close()
    else:
        from jeuxRPG.multiplayer.turso import TursoConnection

        connection = TursoConnection(environment["TURSO_DATABASE_URL"], environment["TURSO_AUTH_TOKEN"])
        try:
            if operation == "connexion":
                if connection.execute("SELECT 1").fetchone()[0] != 1:
                    raise RuntimeError("Connexion invalide")
            elif operation == "schema":
                report["tables"] = [row[0] for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            elif [row[0] for row in connection.execute("PRAGMA quick_check")] != ["ok"]:
                raise RuntimeError("Intégrité invalide")
            elif connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise RuntimeError("Relations invalides")
        finally:
            connection.close()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("connexion", "schema", "integrite"))
    args = parser.parse_args()
    try:
        report = inspect(os.environ, args.operation)
    except Exception:
        print("Contrôle du stockage impossible : vérifier les accès et le schéma")
        raise SystemExit(1) from None
    print(json.dumps(report))
