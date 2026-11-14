"""Local browser integration check. Uses a temporary SQLite DB and loopback only."""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import uuid
from contextlib import ExitStack
from pathlib import Path


def advance_guard_clock(service, town, clock, action):
    for _ in range(16 if action == "recover" else 1):
        clock.value += 3 if action != "wound" else 0.6
        service.tick()
        if action == "recover":
            current = service.world_life.load(1, clock.value)
            squad = next(
                group["squad"]
                for group in current["patrols"].values()
                if group["kind"] == "guards" and group["map"] == town
            )
            if squad["mode"] == "patrol":
                break


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    guard_scenario = "--guards" in sys.argv
    for key in list(os.environ):
        if any(
            part in key.upper()
            for part in ("REDIS", "UPSTASH", "TURSO", "VERCEL", "RPG_D1", "KV_REST")
        ):
            os.environ.pop(key)
    connect = socket.socket.connect

    def loopback_only(sock, address):
        if address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError("External network forbidden in this local check")
        return connect(sock, address)

    socket.socket.connect = loopback_only
    from jeuxRPG.multiplayer import fields, map_building, tactics
    from jeuxRPG.multiplayer.distributed import PresenceRegistry
    from jeuxRPG.multiplayer.server import RPGServer
    from jeuxRPG.multiplayer.service import GameService

    class Clock:
        value = 0
        ratio = 3

        def now(self):
            return self.value

    environment = {
        **os.environ,
        "PLAYWRIGHT_BROWSERS_PATH": str(root / ".data/browser-binaries"),
    }
    with (
        tempfile.TemporaryDirectory(prefix="rpg-world-local-") as temporary,
        ExitStack() as cleanup,
    ):
        clock = Clock()
        service = GameService(
            Path(temporary) / "test.sqlite3",
            clock=clock,
            living_world=True,
            presence_registry=PresenceRegistry(),
            log_directory=str(Path(temporary) / "logs"),
        )
        cleanup.callback(service.close)
        password = secrets.token_urlsafe(24)
        account = service.account_login("WorldLocalTest", password, signup=True)
        selected = service.account_character(
            account["token"], "create", name="TestLocal", class_name="Knight"
        )
        player_id = selected["selected"]
        if isinstance(player_id, dict):
            player_id = player_id["id"]
        session = service.command(account["token"], uuid.uuid4().hex, "tutorial")[
            "session"
        ]
        town = sorted(service.world_life.simulation.catalog["towns"])[0]
        anchor = service.world_life.simulation.catalog["maps"][town]["route"][0]
        if guard_scenario:
            route = service.world_life.simulation.catalog["maps"][town]["route"]
            anchor = route[len(route) // 2]
        with service._transaction():
            party = json.loads(
                service.db.execute(
                    "SELECT data FROM tutorials WHERE session_id=?", (session["id"],)
                ).fetchone()[0]
            )
            fields.enter(party, town, anchor, 0)
            if guard_scenario:
                mob = map_building.create_mob(
                    fields.MAPS,
                    town,
                    {
                        "mob_id": "goblin",
                        "level": 1,
                        "name": "Assaillant de recette locale",
                    },
                    0,
                )
                mob.update(combat_id="guard-browser-enemy", next_attack=10000)
                mob["stats"]["hp"] = {"max": 100, "current": 100}
                mob["stats"]["endurance"] = {"max": 0, "current": 0}
                party["mobs"] = [mob]
                tactics.begin(party, 0, "explore")
                mob.update(
                    position=tactics.free_position(
                        fields.MAPS[town], [anchor[0], anchor[1] + 1]
                    ),
                    next_move=10000,
                    needs_call=False,
                )
                party["battle"]["players"][player_id]["position"] = (
                    tactics.free_position(fields.MAPS[town], [anchor[0], anchor[1] + 4])
                )
            party["gold"][player_id] = 1000
            service.db.execute(
                "UPDATE tutorials SET data=? WHERE session_id=?",
                (json.dumps(party), session["id"]),
            )
        server = RPGServer(("127.0.0.1", 0), service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        process = None
        try:
            process = subprocess.Popen(
                [
                    "node",
                    str(
                        root
                        / (
                            "scripts/verify_guard_patrols_browser.cjs"
                            if guard_scenario
                            else "scripts/verify_living_world_browser.cjs"
                        )
                    ),
                ],
                cwd=root,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            process.stdin.write(
                json.dumps(
                    {
                        "url": f"http://127.0.0.1:{server.server_address[1]}",
                        "password": password,
                        "town": town,
                    }
                )
                + "\n"
            )
            process.stdin.flush()
            for line in process.stdout:
                message = json.loads(line)
                if "guard_action" in message:
                    from copy import deepcopy

                    action = message["guard_action"]
                    with service._transaction():
                        state = deepcopy(service.world_life.load(1, clock.value))
                        group = next(
                            group
                            for group in state["patrols"].values()
                            if group["kind"] == "guards" and group["map"] == town
                        )
                        squad = group["squad"]
                        if action == "wound":
                            next(iter(squad["members"].values()))["character"]["stats"][
                                "hp"
                            ]["current"] = 5
                            occupied = []
                            for member in squad["members"].values():
                                member["position"] = tactics.free_position(
                                    fields.MAPS[town],
                                    [member["position"][0] + 4, member["position"][1]],
                                    occupied,
                                )
                                occupied.append(member["position"])
                        elif action == "safe":
                            for member in squad["members"].values():
                                member["position"] = member["home"][:]
                            row = service.db.execute(
                                "SELECT data FROM tutorials WHERE session_id=?",
                                (session["id"],),
                            ).fetchone()
                            data = json.loads(row[0])
                            data["mobs"] = []
                            data["mob"] = None
                            service.db.execute(
                                "UPDATE tutorials SET data=? WHERE session_id=?",
                                (json.dumps(data), session["id"]),
                            )
                        service.world_life.save(1, state)
                    advance_guard_clock(service, town, clock, action)
                    process.stdin.write("{}\n")
                    process.stdin.flush()
                elif "advance" in message:
                    with service._transaction():
                        clock.value = message["advance"]
                    service.tick()
                    process.stdin.write("{}\n")
                    process.stdin.flush()
                else:
                    print(json.dumps(message, ensure_ascii=True), flush=True)
            code = process.wait(timeout=10)
            assert code == 0, f"Browser verification failed ({code})"
            saved = service.world_life.load(1, clock.value)
            assert saved["towns"][town]["raid"] is None
            if guard_scenario:
                squad = next(
                    group["squad"]
                    for group in saved["patrols"].values()
                    if group["kind"] == "guards" and group["map"] == town
                )
                assert squad["mode"] == "patrol"
                print(
                    "Guard combat, group retreat, recovery and local SQLite persistence verified."
                )
            else:
                assert saved["processed"] > 0
                print("Local SQLite, browser actions and scheduled siege verified.")
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            server.shutdown()
            server.server_close()
            socket.socket.connect = connect


if __name__ == "__main__":
    main()
