"""Deploy the isolated D1 preview Worker using the existing Wrangler login."""

import json
import os
import secrets
import subprocess
from pathlib import Path

from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "cloudflare/wrangler.preview.json"
LOCAL_ENV = ROOT / ".data/d1-migration/preview.env"


def main():
    configuration = json.loads(CONFIG.read_text(encoding="utf-8"))
    if configuration["name"] != "jeux-rpg-d1-preview":
        raise RuntimeError("Ce script est réservé au Worker de préproduction")
    LOCAL_ENV.parent.mkdir(parents=True, exist_ok=True)
    if not LOCAL_ENV.exists():
        descriptor = os.open(LOCAL_ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
    token = dotenv_values(LOCAL_ENV).get("RPG_D1_SERVICE_TOKEN") or secrets.token_urlsafe(48)
    set_key(LOCAL_ENV, "RPG_D1_SERVICE_TOKEN", token)
    set_key(LOCAL_ENV, "RPG_DATABASE_BACKEND", "d1")
    command = ["npx.cmd" if os.name == "nt" else "npx", "--yes", "wrangler@4.76.0"]
    subprocess.run(command + ["secret", "put", "RPG_D1_SERVICE_TOKEN", "--config", str(CONFIG)], input=token, text=True, check=True)
    subprocess.run(command + ["deploy", "--config", str(CONFIG)], check=True)
    print("Worker de préproduction publié. Reporter son URL publique dans preview.env (RPG_D1_WORKER_URL).")


if __name__ == "__main__":
    main()
