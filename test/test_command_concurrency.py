import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from jeuxRPG.multiplayer.service import GameService


def test_twenty_identical_commands_are_idempotent(tmp_path):
    game = GameService(tmp_path / "concurrency.sqlite3", random_source=lambda: 0.5)
    try:
        token = game.register("Concurrent", "Knight")["token"]
        request_id = uuid.uuid4().hex
        barrier = threading.Barrier(20)

        def execute(_):
            barrier.wait()
            return game.command(token, request_id, "tutorial")

        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(execute, range(20)))

        assert all(result == results[0] for result in results)
        assert game.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
        assert game.db.execute("SELECT COUNT(*) FROM tutorials").fetchone()[0] == 1
        assert game.db.execute(
            "SELECT COUNT(*) FROM receipts WHERE request_id=?", (request_id,)
        ).fetchone()[0] == 1
    finally:
        game.close()
