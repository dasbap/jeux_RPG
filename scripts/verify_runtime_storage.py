import os
from pathlib import Path

from dotenv import dotenv_values

from jeuxRPG.multiplayer.d1_client import D1Client, D1StorageError


class D1WorkerUpgradeRequired(RuntimeError):
    pass


def failure_code(error):
    if isinstance(error, D1WorkerUpgradeRequired):
        return "d1_worker_upgrade_required"
    return "d1_storage" if isinstance(error, D1StorageError) else "runtime_storage"


def verify(environment):
    client = D1Client(environment)
    result = client.health()
    if result.get("runtime_transactions") != 1:
        raise D1WorkerUpgradeRequired("Worker D1 sans transactions atomiques")
    client.runtime_snapshot()
    print("Stockage D1 transactionnel vérifié.")
    return "online"


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
