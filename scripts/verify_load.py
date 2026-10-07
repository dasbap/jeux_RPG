import argparse
import http.client
from concurrent.futures import ThreadPoolExecutor
import json
import multiprocessing
from pathlib import Path
import statistics
import tempfile
import threading
import time
import uuid

from jeuxRPG.multiplayer import tutorial, tactics
from jeuxRPG.multiplayer.service import GameService
from jeuxRPG.multiplayer.server import RPGServer


def serve_load(database, tokens, connection):
    service = GameService(database, random_source=lambda: .5)
    server = RPGServer(("127.0.0.1", 0), service, log_directory=Path(database).parent / ".logs")
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    connection.send(server.server_address[1])
    try:
        while connection.recv() != "stop":
            connection.send({"server_alive": thread.is_alive(), "ticker_alive": server._ticker.is_alive(), "active_combats": sum(bool(service.state(token)["session"]["tutorial"]["battle"]) for token in tokens)})
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
        service.close()
        connection.close()


def run(seconds=30, users=30, combat_users=15, poll_interval=1, max_p95=None, fixed_zones=False):
    with tempfile.TemporaryDirectory() as directory:
        service = GameService(Path(directory) / "load.sqlite3", random_source=lambda: .5)
        clients = []
        for index in range(users):
            token = service.register(f"Charge{index}", "Knight")["token"]
            session = service.command(token, uuid.uuid4().hex, "tutorial")["session"]
            party = json.loads(service.db.execute("SELECT data FROM tutorials WHERE session_id=?", (session["id"],)).fetchone()[0])
            tutorial.migrate(party, service._now())
            combat = index < combat_users
            if fixed_zones:
                tutorial.fields.start(party, service._now())
                if not combat:
                    party["step"] = "village"
                tutorial.fields.enter(party, "hunt" if combat else "rosee", [1, 8] if combat else [32, 20], service._now())
            if combat and not fixed_zones:
                tutorial.spawn(party, service._now(), lambda: .2, [], origin="explore")
            if combat:
                for character in party["characters"].values():
                    character["stats"]["hp"].update(max=10000, current=10000)
                if fixed_zones:
                    for mob, position in zip(party["mobs"], ([4, 8], [5, 9], [6, 8])):
                        mob.update(position=list(position), home=list(position), alerted=True)
            elif not fixed_zones:
                party.update(step="village", position="rosee", visited=["clearing", "rosee"])
            service.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), session["id"]))
            clients.append((token, combat))
        service.close()
        context = multiprocessing.get_context("spawn")
        connection, child = context.Pipe()
        process = context.Process(target=serve_load, args=(str(Path(directory) / "load.sqlite3"), [token for token, combat in clients if combat], child))
        process.start()
        child.close()
        if not connection.poll(15):
            process.terminate()
            process.join()
            raise RuntimeError("Le serveur de test ne démarre pas")
        origin = f"http://127.0.0.1:{connection.recv()}"
        barrier = threading.Barrier(users)

        def client(item):
            token, combat = item
            transport = http.client.HTTPConnection("127.0.0.1", int(origin.rsplit(":", 1)[1]), timeout=10)
            hashes, values = {}, {}
            measurements, errors, rejections, server_times, action_times = [], [], [], [], []
            full_bytes = delta_bytes = full_count = delta_count = actions = 0
            barrier.wait()
            deadline = time.monotonic() + seconds
            cycle = 0
            while time.monotonic() < deadline:
                started = time.monotonic()
                try:
                    transport.request("GET", "/api/state", headers={"Authorization": "Bearer " + token, "X-RPG-Bundles": "1", "X-RPG-Bundle-Hashes": json.dumps(hashes)})
                    response = transport.getresponse()
                    body = response.read()
                    server_times.append(float(response.getheader("Server-Timing").split("=")[-1]))
                    if response.status != 200:
                        raise RuntimeError(f"HTTP {response.status}: {body.decode()}")
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
                    if combat and cycle % max(1, round(4 / poll_interval)) == 0 and values.get("session/tutorial/battle"):
                        battle = values["session/tutorial/battle"]
                        me = values["session/me"]
                        unit = battle["players"][me]
                        destination = [2, 8] if cycle % max(1, round(8 / poll_interval)) == 0 else [1, 8]
                        route = tactics.path(battle["map"], unit["position"], destination)
                        if route:
                            params = {"session_id": values["session/id"], "revision": values["session/revision"], "encounter": values["session/tutorial/encounter_number"], "x": destination[0], "y": destination[1], "path": route}
                            payload = json.dumps({"request_id": uuid.uuid4().hex, "action": "battle_move", "params": params}).encode()
                            action_started = time.monotonic()
                            transport.request("POST", "/api/commands", body=payload, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "X-RPG-Command-Ack": "1"})
                            response = transport.getresponse()
                            response_body = response.read()
                            if response.status == 200:
                                actions += 1
                                action_times.append((time.monotonic() - action_started) * 1000)
                            elif response.status == 409:
                                rejections.append(json.loads(response_body)["error"])
                            else:
                                raise RuntimeError(f"HTTP {response.status}: {response_body.decode()}")
                except Exception as error:
                    errors.append(str(error))
                    transport.close()
                cycle += 1
                time.sleep(max(0, poll_interval - (time.monotonic() - started)))
            transport.close()
            return measurements, errors, rejections, full_bytes, delta_bytes, full_count, delta_count, actions, server_times, action_times

        started = time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=users) as executor:
                results = list(executor.map(client, clients))
            latencies = sorted(value for result in results for value in result[0])
            errors = [value for result in results for value in result[1]]
            server_times = sorted(value for result in results for value in result[8])
            action_times = sorted(value for result in results for value in result[9])
            full = sum(result[3] for result in results) / max(1, sum(result[5] for result in results))
            delta = sum(result[4] for result in results) / max(1, sum(result[6] for result in results))
            connection.send("inspect")
            if not connection.poll(15):
                raise RuntimeError("Le serveur ne répond plus")
            health = connection.recv()
            report = {"fixed_zones": fixed_zones, "users": users, "combat_users": combat_users, "town_users": users - combat_users, "duration_seconds": round(time.monotonic() - started, 2), "state_requests": len(latencies), "successful_movement_actions": sum(result[7] for result in results), "expected_action_conflicts": [value for result in results for value in result[2]], "errors": errors, "latency_ms": {"p50": round(statistics.median(latencies), 2), "p95": round(latencies[int(len(latencies) * .95)], 2), "max": round(max(latencies), 2)}, "server_processing_ms": {"p50": round(statistics.median(server_times), 2), "p95": round(server_times[int(len(server_times) * .95)], 2), "max": round(max(server_times), 2)}, "movement_latency_ms": {"p50": round(statistics.median(action_times), 2), "p95": round(action_times[int(len(action_times) * .95)], 2), "max": round(max(action_times), 2)} if action_times else None, "latency_target_ms": max_p95, "latency_target_met": max_p95 is None or (latencies[int(len(latencies) * .95)] < max_p95 and (not action_times or action_times[int(len(action_times) * .95)] < max_p95)), "average_full_bytes": round(full), "average_delta_bytes": round(delta), "reduction_percent": round(100 * (1 - delta / full), 1), **health, "separate_server_process": True, "persistent_http_connections": True, "poll_interval_seconds": poll_interval, "fixture": f"{combat_users} independent combat sessions with real mob AI, boosted player HP to keep fighting; {users - combat_users} town sessions; {1 / poll_interval:g} state requests/second/user, movement every 4 seconds in combat; localhost"}
            return report
        finally:
            if process.is_alive():
                connection.send("stop")
                process.join(timeout=15)
            if process.is_alive():
                process.terminate()
                process.join()
            connection.close()



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--users", type=int, choices=range(1, 501), default=30)
    parser.add_argument("--output", default="test/load/30_users.json")
    parser.add_argument("--combat-users", type=int, choices=range(501), default=15)
    parser.add_argument("--poll-interval", type=float, choices=(.25, .5, 1), default=1)
    parser.add_argument("--max-p95", type=float)
    parser.add_argument("--fixed-zones", action="store_true")
    args = parser.parse_args()
    if args.combat_users > args.users:
        parser.error("--combat-users ne peut pas dépasser --users")
    report = run(args.seconds, users=args.users, combat_users=args.combat_users, poll_interval=args.poll_interval, max_p95=args.max_p95, fixed_zones=args.fixed_zones)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(bool(report["errors"]) or not report["server_alive"] or not report["ticker_alive"] or not report["latency_target_met"])
