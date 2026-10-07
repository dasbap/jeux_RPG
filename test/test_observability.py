import sqlite3

from jeuxRPG.multiplayer.observability import health, metrics, ready


class Service:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(
            """
            CREATE TABLE players(id TEXT);
            CREATE TABLE accounts(id TEXT);
            CREATE TABLE sessions(id TEXT, state TEXT);
            INSERT INTO players VALUES('p1');
            INSERT INTO accounts VALUES('a1');
            INSERT INTO sessions VALUES('s1','running');
            """
        )
        self.runtime_presence = {"p1": {"seen": 10**12, "realm": 1}}


def test_health_is_dependency_free():
    assert health() == {"status": "ok"}


def test_ready_checks_database():
    service = Service()
    assert ready(service) == {"status": "ready"}


def test_metrics_expose_core_gauges():
    service = Service()
    payload = metrics(service, tick_seconds=0.0125)
    assert "rpg_players_total 1" in payload
    assert "rpg_accounts_total 1" in payload
    assert "rpg_sessions_active 1" in payload
    assert "rpg_runtime_presence 1" in payload
    assert "rpg_tick_seconds_last 0.012500" in payload
