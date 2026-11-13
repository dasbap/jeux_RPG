"""Select durable storage: production uses explicit D1; Turso is legacy."""

import hashlib

DATABASE_VARIABLES = {
    "turso": ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN"),
    "d1": ("RPG_D1_WORKER_URL", "RPG_D1_SERVICE_TOKEN"),
}


def database_backend(environment):
    # Production sets d1 explicitly; keep the historical default for compatibility.
    backend = environment.get("RPG_DATABASE_BACKEND") or "turso"
    if backend not in DATABASE_VARIABLES:
        raise ValueError("RPG_DATABASE_BACKEND doit valoir d1 ou turso")
    return backend


def database_variables(environment):
    return DATABASE_VARIABLES[database_backend(environment)]


def runtime_prefix(environment):
    if database_backend(environment) == "turso":
        return "jeux-rpg:runtime:v2:accounts:"
    endpoint = environment.get("RPG_D1_WORKER_URL", "").rstrip("/")
    if not endpoint:
        raise ValueError("RPG_D1_WORKER_URL requis pour isoler le moteur D1")
    identity = hashlib.sha256(endpoint.encode()).hexdigest()[:16]
    return f"jeux-rpg:runtime:v2:d1:{identity}:accounts:"
