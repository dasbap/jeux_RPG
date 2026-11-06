"""Export the selected durable database to a private verified SQLite backup."""

import argparse
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from jeuxRPG.multiplayer.d1_client import D1Client
from jeuxRPG.multiplayer.realtime_store import TABLES
from jeuxRPG.multiplayer.schema import initialize
from jeuxRPG.multiplayer.storage_configuration import database_backend
from scripts.verify_backup import verify_backup


def export_d1_backup(environment, destination):
    client = D1Client(environment)
    client.health()
    data, sequences = client.backup_snapshot()
    destination = Path(destination)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    try:
        with closing(sqlite3.connect(destination)) as db:
            initialize(db)
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                db.execute("BEGIN")
                db.execute("PRAGMA defer_foreign_keys=ON")
                for table in TABLES:
                    for row in data[table]:
                        # Only columns belonging to the known local schema are accepted.
                        allowed = {column[1] for column in db.execute(f"PRAGMA table_info({table})")}
                        if not row or not set(row) <= allowed:
                            raise ValueError("Colonnes de sauvegarde D1 invalides")
                        columns = list(row)
                        db.execute(
                            f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                            tuple(row.values()),
                        )
                for row in sequences:
                    if row["name"] in TABLES:
                        db.execute("DELETE FROM sqlite_sequence WHERE name=?", (row["name"],))
                        db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES(?,?)", (row["name"], row["seq"]))
        return {**verify_backup(destination), "private_export": True, "backend": "d1"}
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def export_backup(environment, destination):
    if database_backend(environment) == "d1":
        return export_d1_backup(environment, destination)
    # Legacy dependency is used only during migration or an explicit rollback.
    from jeuxRPG.multiplayer.turso import TursoConnection
    from scripts.export_turso_backup import export_backup as export_turso

    source = TursoConnection(environment["TURSO_DATABASE_URL"], environment["TURSO_AUTH_TOKEN"], timeout=30)
    try:
        return {**export_turso(source, destination), "backend": "turso"}
    finally:
        source.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(export_backup(os.environ, args.destination)))
