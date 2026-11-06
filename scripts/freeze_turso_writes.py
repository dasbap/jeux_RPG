"""Fence off legacy runtime writers after traffic has been paused and drained."""

import argparse
import json
import os

from jeuxRPG.multiplayer.turso import TursoConnection

FROZEN_FENCE = 8_000_000_000_000_000


def freeze(connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute("SELECT value FROM meta WHERE key='runtime_fence'").fetchone()
        previous = int(row[0]) if row else 0
        if previous > FROZEN_FENCE:
            raise RuntimeError("Génération inattendue : gel refusé")
        connection.execute(
            "INSERT INTO meta(key,value) VALUES('runtime_fence',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(FROZEN_FENCE),),
        )
        connection.execute("COMMIT")
        return {"frozen": True, "previous_fence": previous, "fence": FROZEN_FENCE}
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def restore(connection, previous):
    if not 0 <= previous < FROZEN_FENCE:
        raise ValueError("Génération de retour invalide")
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute("SELECT value FROM meta WHERE key='runtime_fence'").fetchone()
        if row is None or int(row[0]) != FROZEN_FENCE:
            raise RuntimeError("La source ne porte plus le verrou de migration")
        connection.execute("UPDATE meta SET value=? WHERE key='runtime_fence'", (str(previous),))
        connection.execute("COMMIT")
        return {"frozen": False, "fence": previous}
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore-fence", type=int)
    args = parser.parse_args()
    source = TursoConnection(os.environ["TURSO_DATABASE_URL"], os.environ["TURSO_AUTH_TOKEN"], timeout=30)
    try:
        print(json.dumps(freeze(source) if args.restore_fence is None else restore(source, args.restore_fence)))
    finally:
        source.close()
