"""Render the authored cave through the real local client and WebGL shaders."""

import json
import os
import secrets
import subprocess
import tempfile
import threading
import uuid
from copy import deepcopy
from pathlib import Path


def main(keyboard=False):
    root = Path(__file__).resolve().parents[1]
    os.environ["RPG_MAPS_FILE"] = str(root / "jeuxRPG/maps")
    for key in list(os.environ):
        if any(
            part in key.upper()
            for part in ("REDIS", "UPSTASH", "TURSO", "VERCEL", "RPG_D1", "KV_REST")
        ):
            os.environ.pop(key)
    from jeuxRPG.multiplayer import fields, tutorial
    from jeuxRPG.multiplayer.distributed import PresenceRegistry
    from jeuxRPG.multiplayer.server import RPGServer
    from jeuxRPG.multiplayer.service import GameService

    with tempfile.TemporaryDirectory(prefix="rpg-cave-") as temporary:
        logs = str(Path(temporary) / "logs")
        service = GameService(
            Path(temporary) / "game.sqlite3",
            presence_registry=PresenceRegistry(),
            log_directory=logs,
        )
        server = None
        try:
            account = service.account_login(
                "CaveLocalTest", secrets.token_urlsafe(24), signup=True
            )
            service.account_character(
                account["token"], "create", name="Exploratrice", class_name="Knight"
            )
            session = service.command(account["token"], uuid.uuid4().hex, "tutorial")[
                "session"
            ]
            player = session["me"]
            party = tutorial.new_party(
                [{"id": player, "name": "Exploratrice", "class_name": "Knight"}]
            )
            fields.start(party, 0)
            party['visited'] = list(fields.MAPS)
            snapshots = {}
            for map_id, point in (
                ("cave_1", [11, 7]),
                ("cave_2", [30, 9]),
                ("cave_8", [14, 9]),
                ("forest", [8, 7]),
                ("rosee", [31, 20]),
            ):
                fields.enter(party, map_id, point, 0)
                definition = fields.MAPS[map_id]
                party["battle"]["explored"] = [
                    [x, y]
                    for y in range(definition["height"])
                    for x in range(definition["width"])
                ]
                snapshots[map_id] = deepcopy(tutorial.view(party, player, 0))
            fields.enter(party, "cave_1", [11, 7], 0)
            service.db.execute(
                "UPDATE tutorials SET data=? WHERE session_id=?",
                (json.dumps(party), session["id"]),
            )
            server = RPGServer(("127.0.0.1", 0), service, log_directory=logs)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            result = subprocess.run(
                ["node", str(root / "scripts" / ("verify_keybindings_browser.cjs" if keyboard else "verify_cave_browser.cjs"))],
                input=json.dumps(
                    {
                        "url": f"http://127.0.0.1:{server.server_address[1]}",
                        "token": account["token"],
                        "snapshots": snapshots,
                    }
                ),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=60,
                env={
                    **os.environ,
                    "PLAYWRIGHT_BROWSERS_PATH": str(root / ".data/browser-binaries"),
                },
            )
            print(result.stdout)
            if result.returncode:
                raise RuntimeError(result.stderr)
        finally:
            if server:
                server.shutdown()
                server.server_close()
            service.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--keyboard", action="store_true", help="Verify keyboard controls instead of the cave atlas.")
    main(keyboard=parser.parse_args().keyboard)
