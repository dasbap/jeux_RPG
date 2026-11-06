"""Generate an import of data rows for a freshly initialized Cloudflare D1 database.

Input is a private SQLite backup created by scripts/export_turso_backup.py.
Never commit the exported SQL: it contains account and player data.
"""

import argparse
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from jeuxRPG.multiplayer.realtime_store import TABLES
from jeuxRPG.multiplayer.schema import REQUIRED_TABLES, available_migrations


def sql_literal(db, value):
    return db.execute("SELECT quote(?)", (value,)).fetchone()[0]


def generate_import(source, destination):
    source = Path(source).resolve(strict=True)
    destination = Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("La destination doit être différente de la sauvegarde")
    if not source.is_file():
        raise FileNotFoundError(source)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        check = db.execute("PRAGMA quick_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError("Sauvegarde source non intègre")
        table_names = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        missing = REQUIRED_TABLES - table_names
        if missing:
            raise RuntimeError("Tables absentes de la sauvegarde : " + ", ".join(sorted(missing)))
        if "schema_version" not in table_names:
            raise RuntimeError("Version de schéma absente de la sauvegarde")
        version = db.execute("SELECT version FROM schema_version WHERE id=1").fetchone()
        expected = available_migrations()[-1][0]
        if version is None or version[0] != expected:
            raise RuntimeError(f"Version de schéma incompatible, attendu {expected}")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("Relations invalides dans la sauvegarde")
        tables = [t for t in TABLES if t in table_names]
        count = {table: db.execute("SELECT count(*) FROM " + table).fetchone()[0] for table in tables}
        if destination.exists():
            raise FileExistsError(destination)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(destination, flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
                output.write("PRAGMA defer_foreign_keys=ON;\n")
                for table in tables:
                    columns = [row[1] for row in db.execute("PRAGMA table_info(" + table + ")")]
                    quoted_cols = ",".join('"' + col.replace('"', '""') + '"' for col in columns)
                    quoted_table = '"' + table + '"'
                    for row in db.execute("SELECT * FROM " + quoted_table):
                        values = ",".join(sql_literal(db, v) for v in row)
                        output.write(f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES ({values});\n")
                for name, seq in db.execute("SELECT name,seq FROM sqlite_sequence"):
                    if name in tables:
                        literal = sql_literal(db, name)
                        output.write(f"DELETE FROM sqlite_sequence WHERE name={literal};\n")
                        output.write(f"INSERT INTO sqlite_sequence(name,seq) VALUES({literal},{int(seq)});\n")
            return {"rows": count, "total": sum(count.values()), "file": str(destination)}
        except BaseException:
            destination.unlink(missing_ok=True)
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    print(json.dumps(generate_import(args.source, args.destination)))
