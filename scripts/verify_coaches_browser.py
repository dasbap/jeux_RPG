"""Exercise real coach commands against an isolated local game database."""

import json
import os
import secrets
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path


def main(passages=False, harvest=False):
    root = Path(__file__).resolve().parents[1]
    os.environ["RPG_MAPS_FILE"] = str(root / "jeuxRPG/maps")
    from jeuxRPG.multiplayer import content, fields, tutorial
    from jeuxRPG.multiplayer.distributed import PresenceRegistry
    from jeuxRPG.multiplayer.server import RPGServer
    from jeuxRPG.multiplayer.service import GameService

    with tempfile.TemporaryDirectory(prefix="rpg-coach-") as temporary:
        service = GameService(
            Path(temporary) / "test.sqlite3",
            presence_registry=PresenceRegistry(),
            log_directory=str(Path(temporary) / "logs"),
        )
        server = None
        try:
            account = service.account_login(
                "CoachLocalTest", secrets.token_urlsafe(24), signup=True
            )
            service.account_character(
                account["token"], "create", name="Voyageur", class_name="Knight"
            )
            session = service.command(account["token"], uuid.uuid4().hex, "tutorial")[
                "session"
            ]
            player = session["me"]
            party = tutorial.new_party(
                [{"id": player, "name": "Voyageur", "class_name": "Knight"}]
            )
            party["field_mode"] = True
            stop = content.gameplay()["coach_stations"]["coach_rosee"]
            fields.enter(
                party,
                "lisiere" if passages else stop["map"],
                [12, 2] if passages else stop["position"],
                service.clock.now(),
            )
            if harvest:
                position = stop["position"]
                party["battle"]["corpses"] = [
                    {
                        "id": "harvest-near",
                        "name": "Corps proche",
                        "position": [position[0] + 1, position[1]],
                        "loot": {"peau": 2},
                        "harvested": [],
                    },
                    {
                        "id": "harvest-far",
                        "name": "Corps distant",
                        "position": [position[0] + 4, position[1]],
                        "loot": {"peau": 3},
                        "harvested": [],
                    },
                ]
            service.db.execute(
                "UPDATE tutorials SET data=? WHERE session_id=?",
                (json.dumps(party), session["id"]),
            )
            server = RPGServer(
                ("127.0.0.1", 0), service, log_directory=str(Path(temporary) / "logs")
            )
            threading.Thread(target=server.serve_forever, daemon=True).start()
            result = subprocess.run(
                [
                    "node",
                    str(
                        root
                        / (
                            "scripts/verify_harvest_browser.cjs"
                            if harvest
                            else "scripts/verify_zone_passages_browser.cjs"
                            if passages
                            else "scripts/verify_coaches_browser.cjs"
                        )
                    ),
                ],
                input=json.dumps(
                    {
                        "url": f"http://127.0.0.1:{server.server_address[1]}",
                        "token": account["token"],
                    }
                ),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=90,
                env={
                    **os.environ,
                    "PLAYWRIGHT_BROWSERS_PATH": str(root / ".data/browser-binaries"),
                },
            )
            print(result.stdout)
            if result.returncode:
                raise RuntimeError(result.stderr)
            saved = json.loads(
                service.db.execute(
                    "SELECT data FROM tutorials WHERE session_id=?", (session["id"],)
                ).fetchone()[0]
            )
            if harvest:
                assert saved["inventory"][player]["peau"] == 5
                assert all(c["harvested"] for c in saved["battle"]["corpses"])
                print(
                    "Harvest hotkeys, position validation and saved inventory verified."
                )
                return
            assert (
                saved["field_map"] == ("cave_1" if passages else "lisiere")
                and saved["battle"]
                and not saved["transit"]
            )
            print(
                "Coach API, travel, physical arrival and SQLite persistence verified."
            )
        finally:
            if server:
                server.shutdown()
                server.server_close()
            service.close()


if __name__ == "__main__":
    import sys

    main(passages="--passages" in sys.argv, harvest="--harvest" in sys.argv)
