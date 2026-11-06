"""Prepare the full schema for a new, empty D1 preview database."""

import argparse
from pathlib import Path

from jeuxRPG.multiplayer.schema import available_migrations


def schema_sql():
    migrations = available_migrations()
    guard = Path(__file__).resolve().parents[1] / "cloudflare/0004_fence_guard.sql"
    return "\n".join([
        "CREATE TABLE schema_version (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL);",
        *(path.read_text(encoding="utf-8") for _, path in migrations),
        f"INSERT INTO schema_version VALUES(1,{migrations[-1][0]});",
        guard.read_text(encoding="utf-8"),
    ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    with args.destination.open("x", encoding="utf-8") as output:
        output.write(schema_sql())
