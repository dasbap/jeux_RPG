import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace

import jeuxRPG
from jeuxRPG.multiplayer import server as server_module
from jeuxRPG.multiplayer.service import GameService
from jeuxRPG.multiplayer.server import RPGServer


class TestClock:
    def __init__(self):
        self.start = time.monotonic()

    def now(self):
        return (time.monotonic() - self.start) * 300


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
