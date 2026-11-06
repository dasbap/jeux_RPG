"""Compare a private SQLite source and D1 without claiming engine ownership."""

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from dotenv import dotenv_values

from jeuxRPG.multiplayer.d1_client import D1Client
from jeuxRPG.multiplayer.realtime_store import TABLES, RuntimeStore


def normalized(rows):
    # D1's JSON transport represents SQLite REAL 0.0 as the JSON number 0.
    # Canonicalize integral reals without rounding fractional values or text.
    return sorted(json.dumps({
        key: int(value) if type(value) is float and value.is_integer() else value
        for key, value in dict(row).items()
    }, sort_keys=True, separators=(",", ":")) for row in rows)


def verify(source, environment, reset_runtime_fence=False):
    client = D1Client(environment)
    client.health()
    remote, sequences = client.backup_snapshot()
    source = Path(source).resolve(strict=True)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        counts = {}
        for table in TABLES:
            rows = db.execute(f"SELECT * FROM {table}").fetchall()
            if reset_runtime_fence and table == "meta":
                rows = [{**dict(row), "value": "0"} if row["key"] == "runtime_fence" else row for row in rows]
            if normalized(rows) != normalized(remote[table]):
                raise RuntimeError("Données différentes après import : " + table)
            counts[table] = len(rows)
        expected = {row["name"]: row["seq"] for row in db.execute("SELECT name,seq FROM sqlite_sequence") if row["name"] in TABLES}
        actual = {row["name"]: row["seq"] for row in sequences if row["name"] in TABLES}
        if expected != actual:
            raise RuntimeError("Séquences différentes après import")
    store = RuntimeStore(environment, remote)
    try:
        if store.db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("Relations invalides après import")
    finally:
        store.close()
    return {"tables_match": True, "sequences_match": True, "engine_reopened": True, "rows": counts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--reset-runtime-fence", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.source, dotenv_values(args.env_file), args.reset_runtime_fence)))
