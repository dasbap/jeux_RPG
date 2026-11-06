"""Check the selected durable database before deployment."""

import os

from jeuxRPG.multiplayer.d1_client import D1Client
from jeuxRPG.multiplayer.realtime_store import RuntimeStore
from jeuxRPG.multiplayer.storage_configuration import database_backend


def check(environment):
    backend = database_backend(environment)
    if backend == "d1":
        client = D1Client(environment)
        client.health()
        store = RuntimeStore(environment, client.read_snapshot())
        try:
            if store.db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise RuntimeError("Relations D1 invalides")
        finally:
            store.close()
    else:
        from jeuxRPG.multiplayer.schema import initialize
        from jeuxRPG.multiplayer.turso import TursoConnection

        connection = TursoConnection(environment["TURSO_DATABASE_URL"], environment["TURSO_AUTH_TOKEN"])
        try:
            initialize(connection)
            if [row[0] for row in connection.execute("PRAGMA quick_check")] != ["ok"]:
                raise RuntimeError("Contrôle du stockage historique échoué")
        finally:
            connection.close()


if __name__ == "__main__":
    try:
        check(os.environ)
    except Exception:
        print("Base persistante indisponible ou schéma incompatible")
        raise SystemExit(1) from None
    print("Base persistante vérifiée")
