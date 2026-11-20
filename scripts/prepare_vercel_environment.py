import os
from pathlib import Path

from dotenv import dotenv_values, set_key

from jeuxRPG.multiplayer.runtime_configuration import runtime_environment
from jeuxRPG.multiplayer.storage_configuration import (
    DATABASE_VARIABLES,
    database_backend,
    database_variables,
)


def prepare(path, environment):
    pulled = dotenv_values(path)
    values = {key: value for key, value in pulled.items() if value and value != "[SENSITIVE]"}
    selection = {**pulled, **environment}
    backend = database_backend(selection)
    required = (*database_variables(selection), "RPG_ADMIN_TOKEN")
    for key in required:
        value = environment.get(key)
        if not value or value == "[SENSITIVE]":
            raise ValueError("Configuration CI requise absente : " + key)
        values[key] = value
    values["RPG_DATABASE_BACKEND"] = backend
    for inactive, names in DATABASE_VARIABLES.items():
        if inactive != backend:
            for key in names:
                values.pop(key, None)
    if backend == "d1":
        values["RPG_RUNTIME_MODE"] = "d1"
    values.update(RPG_RESET_TEST_PLAYERS="0", RPG_RUNTIME_REALMS="1")
    values = runtime_environment(values)
    path.write_text("", encoding="utf-8")
    path.chmod(0o600)
    for key, value in values.items():
        set_key(path, key, value)


def main():
    try:
        prepare(Path(".vercel/.env.production.local"), os.environ)
    except ValueError as error:
        print(str(error))
        return 1
    print("Configuration du build préparée avec les secrets CI et sans placeholders.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
