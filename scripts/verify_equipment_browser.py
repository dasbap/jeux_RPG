"""Verify equipment menus against a temporary local SQLite game."""

import json
import os
import secrets
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path


def main(weapons=False):
    root = Path(__file__).resolve().parents[1]
    os.environ["RPG_MAPS_FILE"] = str(root / "jeuxRPG/maps")
    for key in list(os.environ):
        if any(
            part in key.upper()
            for part in ("REDIS", "UPSTASH", "TURSO", "VERCEL", "RPG_D1", "KV_REST")
        ):
            os.environ.pop(key)
    from jeuxRPG.multiplayer import content, forge, narrative, tutorial
    from jeuxRPG.multiplayer.distributed import PresenceRegistry
    from jeuxRPG.multiplayer.server import RPGServer
    from jeuxRPG.multiplayer.service import GameService

    with tempfile.TemporaryDirectory(prefix="rpg-equipment-") as temporary:
        service = GameService(
            Path(temporary) / "test.sqlite3",
            presence_registry=PresenceRegistry(),
            log_directory=str(Path(temporary) / "logs"),
        )
        server = None
        try:
            account = service.account_login(
                "MenuLocalTest", secrets.token_urlsafe(24), signup=True
            )
            service.account_character(
                account["token"], "create", name="Aelys", class_name="Knight"
            )
            session = service.command(account["token"], uuid.uuid4().hex, "tutorial")[
                "session"
            ]
            player = session["me"]
            party = tutorial.new_party(
                [{"id": player, "name": "Aelys", "class_name": "Knight"}]
            )
            party.update(
                position="forge",
                step="travel",
                visited=["clearing", "rosee", "forest", "brume"],
                seen_mobs=[
                    "goblin",
                    "orc",
                    "dragon_whelp",
                    "luciole_cuirassee",
                    "sanglier_roncier",
                    "gardien_de_schiste",
                ],
            )
            gear = {
                forge.RECIPES[recipe]["slot"]: forge.piece(recipe, 2)
                for recipe in ("casque", "veste", "gants", "bottes")
            }
            party["equipment"][player] = gear
            for item in gear.values():
                for stat in forge.BONUS_STATS:
                    party["characters"][player]["stats"][stat]["max"] += item[stat]
                    party["characters"][player]["stats"][stat]["current"] += item[stat]
            party["stored_equipment"] = {
                player: {
                    recipe: forge.piece(recipe, 3)
                    for recipe in (
                        "manteau_veille",
                        "casque_schiste",
                        "bottes_lucioles",
                    )
                }
            }
            states = (
                narrative.state(party, player)["quests"]
                if narrative.enabled()
                else content.quest_states(party)
            )
            for index, quest in enumerate(content.DATA["quests"][:10]):
                states[quest["id"]] = {
                    "status": "completed" if index == 0 else "active",
                    "progress": quest["count"] if index < 3 else 0,
                }
            if weapons:
                party["inventory"][player] = {
                    item: 1000
                    for recipe in forge.RECIPES.values()
                    for item in recipe["cost"]
                }
            forge.migrate(party)
            if weapons:
                assert forge.rosee_unlocked(party, player)
                assert next(row for row in forge.catalogue(party, player) if row["recipe"] == "epee_lisiere")["affordable"]
            service.db.execute(
                "UPDATE tutorials SET data=? WHERE session_id=?",
                (json.dumps(party), session["id"]),
            )
            server = RPGServer(
                ("127.0.0.1", 0), service, log_directory=str(Path(temporary) / "logs")
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            process = subprocess.run(
                [
                    "node",
                    str(
                        root
                        / "scripts"
                        / (
                            "verify_weapons_browser.cjs"
                            if weapons
                            else "verify_equipment_browser.cjs"
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
            print(process.stdout)
            if process.returncode:
                raise RuntimeError(process.stderr)
            saved = json.loads(
                service.db.execute(
                    "SELECT data FROM tutorials WHERE session_id=?", (session["id"],)
                ).fetchone()[0]
            )
            assert saved["equipment"][player]["torso"]["recipe"] == "veste"
            assert saved["stored_equipment"][player]["manteau_veille"]["level"] == 3
            print(
                "Browser, API, SQLite and menu verified; inventory survives page reload."
            )
        finally:
            if server:
                server.shutdown()
                server.server_close()
            service.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--weapons", action="store_true")
    main(weapons=parser.parse_args().weapons)
