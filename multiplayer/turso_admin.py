import argparse
import os
import sqlite3

from .schema import initialize
from .turso import TursoConnection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("connexion", "schema", "integrite", "initialiser"))
    operation = parser.parse_args().operation
    connection = None
    try:
        connection = TursoConnection(os.environ.get("TURSO_DATABASE_URL", ""), os.environ.get("TURSO_AUTH_TOKEN", ""), timeout=30)
        if operation == "initialiser":
            initialize(connection)
            print("Tables du jeu et de l’administration initialisées, données existantes conservées.")
        elif operation == "connexion":
            if connection.execute("SELECT 1").fetchone()[0] != 1:
                raise ValueError()
            print("Connexion Turso réussie.")
        elif operation == "integrite":
            if [row[0] for row in connection.execute("PRAGMA quick_check")] != ["ok"]:
                raise ValueError()
            print("Intégrité vérifiée.")
        else:
            for row in connection.execute("SELECT type,name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"):
                print(row[0], row[1])
        return 0
    except (ValueError, OSError, sqlite3.Error):
        print("Échec Turso : vérifier les secrets, les permissions et la disponibilité de la base.")
        return 1
    finally:
        if connection:
            try:
                connection.close()
            except sqlite3.Error:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
