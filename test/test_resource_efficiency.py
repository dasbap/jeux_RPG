import time
import json
import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from jeuxRPG.multiplayer import accounts, realtime
from jeuxRPG.multiplayer.distributed import PresenceRegistry
from jeuxRPG.multiplayer.realtime import Coordinator, create_app
from jeuxRPG.multiplayer.realtime_store import RuntimeStore
from jeuxRPG.multiplayer.service import GameService
from test_accounts_social import Clock, account, start
from test_realtime import ENV, adventure, mutate


class CountedPresence(PresenceRegistry):
    def __init__(self):
        super().__init__()
        self.reads = self.writes = 0

    def values(self):
        self.reads += 1
        return super().values()

    def __setitem__(self, key, value):
        self.writes += 1
        super().__setitem__(key, value)


def test_presence_renewals_are_bounded_and_realm_changes_are_immediate(tmp_path, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(accounts.time, 'time', lambda: now[0])
    service = GameService(tmp_path / 'game.sqlite3')
    service.realm_count = 3
    registry = service.runtime_presence = CountedPresence()
    try:
        for _ in range(100):
            assert service._admit('player') == 1
            now[0] += .05
        assert registry.reads == 100
        assert registry.writes == 1
        assert service._admit('player', realm=2) == 2
        assert registry.writes == 2
        now[0] += 10
        assert service._admit('player') == 2
        assert registry.writes == 3
        now[0] += 61
        assert service._admit('player') == 1
        assert registry.writes == 4
    finally:
        service.close()


def test_team_presence_expires_on_the_same_clock_as_admission(monkeypatch):
    now = time.time()
    service = GameService.__new__(GameService)
    service.db = SimpleNamespace(execute=lambda *args: [('player',)])
    service.runtime_presence = PresenceRegistry()
    service.runtime_presence['player'] = {'realm': 1, 'seen': now - 61}
    service._character_location = lambda player: {'zone': 'rosee'}
    monkeypatch.setattr(accounts.time, 'time', lambda: now)
    assert service.social_view_for_team({'id': 'team'}) == []
    service.runtime_presence['player'] = {'realm': 1, 'seen': now - 5}
    assert service.social_view_for_team({'id': 'team'}) == [{'player_id': 'player', 'online': True, 'realm': 1, 'zone': 'rosee'}]


def test_hidden_websocket_renews_presence_without_sending_state(monkeypatch):
    monkeypatch.setattr(realtime, 'HIDDEN_REFRESH_SECONDS', .05)
    clock = Clock()
    store = RuntimeStore({}, clock=clock)
    store.service.legacy_auth = False
    player = account(store.service, 'Background')
    room = start(store.service, player, field=True)
    coordinator = Coordinator({}, store=store)
    with TestClient(create_app({}, coordinator), base_url='http://localhost') as client:
        with client.websocket_connect('/api/ws', headers={'origin': 'http://localhost', 'host': 'localhost'}) as socket:
            socket.send_json({'id': 'state', 'path': '/api/state', 'headers': {'Authorization': 'Bearer ' + player['token']}})
            assert socket.receive_json()['id'] == 'state'
            socket.send_json({'type': 'visibility', 'active': False})
            while socket.receive_json().get('type') != 'visibility':
                pass
            before = store.db.execute('SELECT data FROM tutorials WHERE session_id=?', (room,)).fetchone()[0]
            store.service.runtime_presence[player['player_id']]['seen'] = time.time() - 61
            clock.value = 20
            time.sleep(.5)
            socket.send_json({'type': 'ping'})
            assert socket.receive_json()['type'] == 'pong'
            assert time.time() - store.service.runtime_presence[player['player_id']]['seen'] < 10
            assert store.db.execute('SELECT data FROM tutorials WHERE session_id=?', (room,)).fetchone()[0] != before


def test_dirty_capture_preserves_other_sessions_and_avoids_idle_reads():
    store = RuntimeStore(ENV, clock=Clock())
    first, first_room = adventure(store)
    other = store.service.register('Other', 'Knight')
    other_room = store.service.command(other['token'], uuid.uuid4().hex, 'tutorial')['session']['id']
    store.capture()
    store.saved(store.pending_batch())
    before = json.loads(store.snapshot())
    mutate(store, first_room, lambda party: party['characters'][first['player']['id']].update(level=2))
    store.service.dirty_sessions.add(first_room)
    store.capture(dirty_only=True)
    restored = RuntimeStore(ENV, json.loads(store.snapshot()), clock=Clock())
    assert restored.db.execute('SELECT COUNT(*) FROM players').fetchone()[0] == 2
    saved = json.loads(restored.db.execute('SELECT data FROM tutorials WHERE session_id=?', (first_room,)).fetchone()[0])
    assert saved['characters'][first['player']['id']]['level'] == 2
    assert restored.db.execute('SELECT data FROM tutorials WHERE session_id=?', (other_room,)).fetchone()[0] == store.db.execute('SELECT data FROM tutorials WHERE session_id=?', (other_room,)).fetchone()[0]
    assert next(row for row in json.loads(store.snapshot())['players'] if row['name'] == 'Other') == next(row for row in before['players'] if row['name'] == 'Other')
    queries = []
    store.db.set_trace_callback(queries.append)
    assert store.session_signatures(set()) == {}
    assert queries == []
    assert set(store.session_signatures({first_room})) == {first_room}
    restored.close()
    store.close()
