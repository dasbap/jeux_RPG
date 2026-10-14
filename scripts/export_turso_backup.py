"""Read a consistent Turso snapshot into a private local SQLite file.

The export contains account data: never commit or upload it unencrypted.
"""

import argparse
import json
import os
import sqlite3
from pathlib import Path

from jeuxRPG.multiplayer.turso import TursoConnection
from scripts.verify_backup import verify_backup


def export_backup(source, destination):
    destination = Path(destination)
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        source.execute("BEGIN")
        schema = [
            dict(row)
            for row in source.execute(
                "SELECT type,name,sql FROM sqlite_schema WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END,name"
            )
        ]
        with sqlite3.connect(destination) as restored:
            for item in schema:
                kind, name, sql = item["type"], item["name"], item["sql"]
                if kind == "table":
                    restored.execute(sql)
                    quoted = '"' + name.replace('"', '""') + '"'
                    rows = source.execute("SELECT * FROM " + quoted)
                    for row in rows:
                        values = tuple(row[key] for key in row)
                        restored.execute(
                            "INSERT INTO "
                            + quoted
                            + " VALUES ("
                            + ",".join("?" for _ in values)
                            + ")",
                            values,
                        )
                else:
                    restored.execute(sql)
            if source.execute(
                "SELECT 1 FROM sqlite_schema WHERE name='sqlite_sequence'"
            ).fetchone():
                restored.execute("DELETE FROM sqlite_sequence")
                for row in source.execute("SELECT name,seq FROM sqlite_sequence"):
                    restored.execute(
                        "INSERT INTO sqlite_sequence VALUES (?,?)",
                        (row["name"], row["seq"]),
                    )
        source.execute("ROLLBACK")
    except BaseException:
        try:
            if source.in_transaction:
                source.execute("ROLLBACK")
        finally:
            destination.unlink(missing_ok=True)
        raise
    report = verify_backup(destination)
    report["private_export"] = True
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    args = parser.parse_args()
    connection = TursoConnection(
        os.environ["TURSO_DATABASE_URL"], os.environ["TURSO_AUTH_TOKEN"], timeout=30
    )
    try:
        print(json.dumps(export_backup(connection, args.destination)))
    finally:
        connection.close()
