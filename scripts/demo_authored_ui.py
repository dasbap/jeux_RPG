import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time

root = Path(__file__).resolve().parent.parent
os.environ['RPG_MAPS_FILE'] = str(root / 'jeuxRPG' / 'maps')

from jeuxRPG.multiplayer.server import RPGServer
from jeuxRPG.multiplayer.service import GameService


class DemoClock:
    def __init__(self):
        self.origin = time.monotonic()
        self.speed = float(os.environ.get("RPG_DEMO_SPEED", "1"))

    def now(self):
        return (time.monotonic() - self.origin) * 3 * self.speed


def main():
    with tempfile.TemporaryDirectory() as directory:
        service = GameService(Path(directory) / 'demo.sqlite3', clock=DemoClock())
        server = RPGServer(('127.0.0.1', 0), service)
        worker = threading.Thread(target=server.serve_forever)
        worker.start()
        try:
            return subprocess.run(['node', str(root / 'scripts' / 'demo_authored_ui.cjs')], env={**os.environ, 'RPG_TEST_ORIGIN': f'http://127.0.0.1:{server.server_address[1]}'}, timeout=1800).returncode
        finally:
            server.shutdown()
            worker.join()
            server.server_close()
            service.close()


if __name__ == '__main__':
    raise SystemExit(main())
