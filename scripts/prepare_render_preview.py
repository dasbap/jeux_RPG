"""Prepare an ignored runtime env from existing isolated D1 credentials."""

import argparse
import os
from pathlib import Path

from dotenv import dotenv_values, set_key

from jeuxRPG.multiplayer.container_host import configuration
from jeuxRPG.multiplayer.d1_client import D1Client

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".data/oracle-test/runtime.env"
DESTINATION = ROOT / ".data/render/runtime.env"


def prepare(origin, source=SOURCE, destination=DESTINATION):
    source_environment = dotenv_values(source, interpolate=False)
    # Do not copy unrelated credentials, Redis URLs or local configuration.
    environment = {
        key: source_environment.get(key, "")
        for key in (
            "RPG_RUNTIME_MODE",
            "RPG_DATABASE_BACKEND",
            "RPG_D1_WORKER_URL",
            "RPG_D1_SERVICE_TOKEN",
            "RPG_ADMIN_TOKEN",
            "RPG_RUNTIME_REALMS",
        )
    }
    environment.update(
        RPG_DEPLOYMENT_STAGE="preview", RPG_PUBLIC_ORIGIN=origin, WEB_CONCURRENCY="1"
    )
    configuration(environment)
    # Read-only health: no generation claim, import or database mutation.
    D1Client(environment).health()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    for key, value in environment.items():
        set_key(destination, key, value)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    destination = prepare(args.origin)
    print(
        f"Configuration privée créée : {destination.relative_to(ROOT)} ; aucun secret affiché"
    )


if __name__ == "__main__":
    main()
