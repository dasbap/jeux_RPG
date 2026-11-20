import os
from pathlib import Path

from dotenv import dotenv_values

from jeuxRPG.multiplayer.d1_client import D1Client
from jeuxRPG.multiplayer.realtime_store import RuntimeStore
from jeuxRPG.multiplayer.redis_configuration import redis_url
from jeuxRPG.multiplayer.storage_configuration import database_backend


class D1WorkerUpgradeRequired(RuntimeError):
    pass


def failure_code(error):
    if isinstance(error, D1WorkerUpgradeRequired):
        return "d1_worker_upgrade_required"
    if not type(error).__module__.startswith("redis"):
        return "d1_storage" if type(error).__module__.endswith("d1_client") else "runtime_storage"
    from redis.exceptions import (
        AuthenticationError,
        ConnectionError,
        ResponseError,
        TimeoutError,
    )

    if isinstance(error, AuthenticationError):
        return "redis_authentication"
    if isinstance(error, TimeoutError):
        return "redis_timeout"
    if isinstance(error, ConnectionError):
        return "redis_connection"
    if isinstance(error, ResponseError):
        message = str(error).lower()
        if "limit" in message or "quota" in message:
            return "redis_quota"
        return "redis_command"
    return "runtime_storage"


def verify(environment):
    mode = "online"
    if environment.get("RPG_RUNTIME_MODE") == "d1":
        client = D1Client(environment)
        result = client.health()
        if result.get("runtime_transactions") != 1:
            raise D1WorkerUpgradeRequired("Worker D1 sans transactions atomiques")
        client.runtime_snapshot()
        print("Stockage D1 transactionnel verifie, sans Redis.")
        return mode
    from redis import Redis
    from redis.exceptions import ResponseError

    url = redis_url(environment)
    if not url:
        raise RuntimeError("missing_configuration")
    print("Vérification de la connexion Redis.", flush=True)
    try:
        with Redis.from_url(url, decode_responses=True, socket_connect_timeout=5, socket_timeout=5) as redis:
            redis.ping()
            redis.eval("return 1", 0)
            with redis.pubsub() as pubsub:
                pubsub.subscribe("jeux-rpg:runtime:v2:accounts:diagnostic")
                pubsub.get_message(timeout=5)
    except ResponseError as error:
        if environment.get("RPG_ALLOW_SOLO_RELEASE") != "1" or failure_code(error) != "redis_quota":
            raise
        mode = "solo"
        print("Quota Redis épuisé : publication du mode solo uniquement.", flush=True)
    backend = database_backend(environment)
    print("Vérification de la restauration du stockage " + backend + ".", flush=True)
    if backend == "d1":
        client = D1Client(environment)
        client.health()
        store = RuntimeStore(environment, client.read_snapshot())
    else:
        store = RuntimeStore.load(environment)
    store.close()
    return mode


def main():
    environment = {**dotenv_values(Path(".vercel/.env.production.local")), **os.environ}
    environment["RPG_RESET_TEST_PLAYERS"] = "0"
    try:
        mode = verify(environment)
    except Exception as error:
        print("Stockage du moteur indisponible : " + failure_code(error))
        if isinstance(error, D1WorkerUpgradeRequired):
            print("Mettre a jour le Worker cible avec cloudflare/d1-worker.mjs "
                  "avant de relancer la publication ; consulter docs/VERCEL.md.")
        return 1
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write(f"mode={mode}\n")
    print("Restauration du moteur vérifiée ; mode de publication : " + mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
