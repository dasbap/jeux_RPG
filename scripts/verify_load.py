import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import statistics
import tempfile
import threading
import time
import urllib.request
import urllib.error
import uuid

from jeuxRPG.multiplayer import tutorial, tactics
from jeuxRPG.multiplayer.service import GameService
from jeuxRPG.multiplayer.server import RPGServer


def run(seconds=30, users=30, combat_users=15):
    with tempfile.TemporaryDirectory() as directory:
        service = GameService(Path(directory) / "load.sqlite3", random_source=lambda: .5)
        clients = []
        for index in range(users):
            token = service.register(f"Charge{index}", "Knight")["token"]
            session = service.command(token, uuid.uuid4().hex, "tutorial")["session"]
            party = json.loads(service.db.execute("SELECT data FROM tutorials WHERE session_id=?", (session["id"],)).fetchone()[0])
            tutorial.migrate(party, service._now())
            combat = index < combat_users
            if combat:
                tutorial.spawn(party, service._now(), lambda: .2, [], origin="explore")
                for character in party["characters"].values():
                    character["stats"]["hp"].update(max=10000, current=10000)
            else:
                party.update(step="village", position="rosee", visited=["clearing", "rosee"])
            service.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), session["id"]))
            clients.append((token, combat))
        server = RPGServer(("127.0.0.1", 0), service, log_directory=Path(directory) / ".logs")
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        barrier = threading.Barrier(users)

        def client(item):
            token, combat = item
            hashes, values = {}, {}
            measurements, errors, rejections = [], [], []
            full_bytes = delta_bytes = full_count = delta_count = actions = 0
            barrier.wait()
            deadline = time.monotonic() + seconds
            cycle = 0
            while time.monotonic() < deadline:
                started = time.monotonic()
                try:
                    request = urllib.request.Request(origin + "/api/state", headers={"Authorization": "Bearer " + token, "X-RPG-Bundles": "1", "X-RPG-Bundle-Hashes": json.dumps(hashes)})
                    with urllib.request.urlopen(request, timeout=10) as response:
                        body = response.read()
                    data = json.loads(body)
                    for key in data["removed"]:
                        values.pop(key, None)
                    values.update(data["bundles"])
                    if cycle == 0:
                        full_bytes += len(body)
                        full_count += 1
                    else:
                        delta_bytes += len(body)
                        delta_count += 1
                    hashes = data["hashes"]
                    measurements.append((time.monotonic() - started) * 1000)
                    if combat and cycle % 4 == 0 and values.get("session/tutorial/battle"):
                        battle = values["session/tutorial/battle"]
                        me = values["session/me"]
                        unit = battle["players"][me]
                        destination = [2, 8] if cycle % 8 == 0 else [1, 8]
                        route = tactics.path(battle["map"], unit["position"], destination)
                        if route:
                            params = {"session_id": values["session/id"], "revision": values["session/revision"], "encounter": values["session/tutorial/encounter_number"], "x": destination[0], "y": destination[1], "path": route}
                            payload = json.dumps({"request_id": uuid.uuid4().hex, "action": "battle_move", "params": params}).encode()
                            request = urllib.request.Request(origin + "/api/commands", data=payload, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
                            try:
                                with urllib.request.urlopen(request, timeout=10) as response:
                                    response.read()
                                actions += 1
                            except urllib.error.HTTPError as error:
                                if error.code == 409:
                                    rejections.append(json.loads(error.read())["error"])
                                else:
                                    raise
                except Exception as error:
                    errors.append(str(error))
                cycle += 1
                time.sleep(max(0, 1 - (time.monotonic() - started)))
            return measurements, errors, rejections, full_bytes, delta_bytes, full_count, delta_count, actions

        started = time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=users) as executor:
                results = list(executor.map(client, clients))
            latencies = sorted(value for result in results for value in result[0])
            errors = [value for result in results for value in result[1]]
            full = sum(result[3] for result in results) / max(1, sum(result[5] for result in results))
            delta = sum(result[4] for result in results) / max(1, sum(result[6] for result in results))
            report = {"users": users, "combat_users": combat_users, "town_users": users - combat_users, "duration_seconds": round(time.monotonic() - started, 2), "state_requests": len(latencies), "successful_movement_actions": sum(result[7] for result in results), "expected_action_conflicts": [value for result in results for value in result[2]], "errors": errors, "latency_ms": {"p50": round(statistics.median(latencies), 2), "p95": round(latencies[int(len(latencies) * .95)], 2), "max": round(max(latencies), 2)}, "average_full_bytes": round(full), "average_delta_bytes": round(delta), "reduction_percent": round(100 * (1 - delta / full), 1), "server_alive": thread.is_alive(), "ticker_alive": server._ticker.is_alive(), "active_combats": sum(bool(service.state(token)["session"]["tutorial"]["battle"]) for token, combat in clients if combat), "fixture": f"{combat_users} independent combat sessions with real mob AI, boosted player HP to keep fighting; {users - combat_users} town sessions; 1 state request/second/user, movement every 4 seconds in combat; localhost"}
            return report
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
            service.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--output", default="test/load/30_users.json")
    parser.add_argument("--combat-users", type=int, choices=range(31), default=15)
    args = parser.parse_args()
    report = run(args.seconds, combat_users=args.combat_users)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(bool(report["errors"]) or not report["server_alive"] or not report["ticker_alive"])
