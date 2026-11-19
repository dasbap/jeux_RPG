"""Configure only the jeux-rpg preview, using the fictitious D1 database."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

from dotenv import set_key

TEAM = "team_qde9V6kikwwSvLtNrjAsAkRY"
PROJECT = "prj_fVH6vG7RCXf5OP3MIfTngxeCN8U2"
WORKER = "https://jeux-rpg-d1-preview.dasbap-jeux-rpg.workers.dev"


def configuration(environment):
    if environment.get("RPG_D1_WORKER_URL", "").rstrip("/") != WORKER:
        raise ValueError("La recette exige le Worker D1 fictif jeux-rpg-d1-preview")
    values = {key: environment.get(key, "") for key in (
        "RPG_D1_SERVICE_TOKEN", "RPG_ADMIN_TOKEN", "REDIS_URL", "RPG_RELEASE_SHA"
    )}
    for key, value in values.items():
        if not value or value == "[SENSITIVE]":
            raise ValueError("Configuration de recette absente : " + key)
    if len(values["RPG_ADMIN_TOKEN"]) < 32:
        raise ValueError("Le secret administrateur de recette doit avoir 32 caracteres")
    if not re.fullmatch(r"[0-9a-f]{40}", values["RPG_RELEASE_SHA"]):
        raise ValueError("Commit de recette invalide")
    from jeuxRPG.multiplayer.redis_configuration import redis_url

    redis_url(values)
    return {
        **values, "RPG_D1_WORKER_URL": WORKER, "RPG_DATABASE_BACKEND": "d1",
        "RPG_RUNTIME_MODE": "distributed", "RPG_RUNTIME_REALMS": "1",
        "RPG_RESET_TEST_PLAYERS": "0",
    }


def link(root):
    folder = root / ".vercel"
    folder.mkdir(exist_ok=True)
    (folder / "project.json").write_text(json.dumps({
        "projectId": PROJECT, "orgId": TEAM, "projectName": "jeux-rpg",
    }), encoding="utf-8")


def prepare(root, environment):
    values = configuration(environment)
    link(root)
    path = root / ".vercel/.env.preview.local"
    # Discard pulled settings: neither production credentials nor placeholders
    # belong in a preview build. Runtime values are synced to Preview only.
    path.write_text("", encoding="utf-8")
    path.chmod(0o600)
    for key, value in values.items():
        set_key(path, key, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("link", "prepare", "sync"))
    parser.add_argument("--cli", default="vercel")
    args = parser.parse_args()
    root = Path.cwd()
    if args.action == "link":
        link(root)
    elif args.action == "prepare":
        prepare(root, os.environ)
    else:
        values = configuration(os.environ)
        link(root)
        for key, value in values.items():
            if key == "RPG_RELEASE_SHA":
                continue  # Bound to the exact deployment by --env.
            subprocess.run([
                args.cli, "env", "add", key, "preview", "--force", "--scope", TEAM,
                "--sensitive" if key in {"RPG_D1_SERVICE_TOKEN", "RPG_ADMIN_TOKEN", "REDIS_URL"} else "--no-sensitive",
            ], input=value, text=True, check=True)
    print("Configuration Vercel preview preparee, sans modifier la production.")


if __name__ == "__main__":
    main()
