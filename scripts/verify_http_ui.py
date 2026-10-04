import os
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace

reference_world = Path(__file__).resolve().parent.parent / "test" / "fixtures" / "reference_world"
if reference_world.is_dir():
    os.environ.setdefault("RPG_MAPS_FILE", str(reference_world))

import jeuxRPG
from jeuxRPG.multiplayer import server as server_module, tutorial
from jeuxRPG.multiplayer.service import GameService, GameError
from jeuxRPG.multiplayer.server import RPGServer


class TestClock:
    def __init__(self):
        self.start = time.monotonic()

    def now(self):
        return (time.monotonic() - self.start) * 60


def main():
    if os.environ.get("RPG_REQUIRE_INSTALLED") == "1":
        assert "site-packages" in jeuxRPG.__file__, jeuxRPG.__file__
    root = Path(__file__).resolve().parent.parent
    original_time = server_module.time
    server_module.time = SimpleNamespace(monotonic=lambda: time.monotonic() * 100)
    try:
        with tempfile.TemporaryDirectory() as directory:
            draws = iter([.5, .2, .05, .04, 0, .25, .5])
            service = GameService(Path(directory) / "test.sqlite3", TestClock(), random_source=lambda: next(draws, .5))
            server = RPGServer(("127.0.0.1", 0), service)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                modules = str(root / ".ui-test" / "node_modules")
                if os.environ.get("NODE_PATH"):
                    modules += os.pathsep + os.environ["NODE_PATH"]
                fixture = tutorial.new_party([{"id": "p0", "name": "Test", "class_name": "Knight"}])
                tutorial.migrate(fixture, 0)
                tutorial.spawn(fixture, 0, lambda: 0, [], origin="explore")
                fixture["mobs"] = fixture["mobs"][:3]
                tutorial.sync_mobs(fixture)
                fixture["battle"]["players"]["p0"].update(position=[9, 5], hidden=False)
                for mob, position in zip(fixture["mobs"], ([9, 4], [10, 5], [12, 5])):
                    mob["position"] = position
                fixture_path = Path(directory) / "ui-fixture.json"
                necromancer = tutorial.new_party([{"id": "p0", "name": "Nécromancien", "class_name": "Necromancien"}])
                tutorial.migrate(necromancer, 0)
                tutorial.spawn(necromancer, 0, lambda: .5, [], origin="explore")
                initial_necromancer = tutorial.view(necromancer, "p0", 0)
                tutorial.execute(necromancer, "p0", "skill", {"skill_name": "Low Skull", "target": "p0"}, 0, GameError, lambda: .5)
                tutorial.tactics.complete_casts(necromancer, 6, lambda: .5)
                for energy in necromancer["characters"]["p0"]["energies"]:
                    energy["current"] = energy["max"]
                necromancer["battle"]["players"]["p0"]["position"] = [0, 9]
                necromancer["mobs"][0]["position"] = [12, 1]
                next(iter(necromancer["battle"]["summons"].values()))["position"] = [10, 1]
                field_village = tutorial.new_party([{ "id": "p0", "name": "Test", "class_name": "Knight"}])
                tutorial.fields.start(field_village, 0)
                field_village["step"] = "road"
                tutorial.fields.enter(field_village, "rosee", [32, 20], 0)
                fixture_path.write_text(json.dumps({"combat": tutorial.view(fixture, "p0", 0), "necromancer": initial_necromancer,
                                                  "control": tutorial.view(necromancer, "p0", 6), "field_village": tutorial.view(field_village, "p0", 0)}), encoding="utf-8")
                from jeuxRPG.multiplayer.map_preview import preview_html
                from jeuxRPG.multiplayer.fields import MAPS
                from copy import deepcopy
                preview_maps = deepcopy(MAPS)
                preview_maps["clearing"]["bridge_rotations"] = [{"position": preview_maps["clearing"]["bridges"][0], "rotation": 90}]
                preview_path = Path(directory) / "preview.html"
                preview_path.write_text(preview_html(preview_maps, "clearing"), encoding="utf-8")
                checked = subprocess.run(["node", str(root / "scripts" / "verify_map_preview.cjs"), str(preview_path)], env={**os.environ, "NODE_PATH": modules}, timeout=30)
                if checked.returncode:
                    return checked.returncode
                checked = subprocess.run(["node", str(root / "scripts" / "verify_tactical_ui.cjs"), str(fixture_path)],
                                         env={**os.environ, "NODE_PATH": modules}, timeout=30)
                if checked.returncode:
                    return checked.returncode
                checked = subprocess.run(["node", str(root / "scripts" / "verify_demo_driver.cjs"), str(fixture_path)], env={**os.environ, "NODE_PATH": modules}, timeout=30)
                if checked.returncode:
                    return checked.returncode
                result = subprocess.run(["node", str(root / "scripts" / "verify_ui.cjs")],
                                        env={**os.environ, "NODE_PATH": modules,
                                             "RPG_TEST_ORIGIN": f"http://127.0.0.1:{server.server_address[1]}"},
                                        timeout=180)
            finally:
                server.shutdown()
                thread.join()
                server.server_close()
                service.close()
            return result.returncode
    finally:
        server_module.time = original_time


if __name__ == "__main__":
    raise SystemExit(main())
