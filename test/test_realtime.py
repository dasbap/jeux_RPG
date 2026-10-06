import asyncio
import json
import os
import time
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from jeuxRPG.multiplayer.realtime import Coordinator, create_app
from jeuxRPG.multiplayer.realtime_store import RuntimeStore, progress_signature
from jeuxRPG.multiplayer import realtime_store
from jeuxRPG.multiplayer.schema import initialize
from jeuxRPG.multiplayer.turso import TursoConnection
from test_serverless import Transport
from redis.asyncio import Redis


ENV = {'RPG_ADMIN_TOKEN': 'a' * 40}


def message(path, body=None, token=None):
    return {'path': path, 'method': 'POST' if body else 'GET', 'body': body,
            'host': 'localhost', 'peer': '127.0.0.1', 'scheme': 'http',
            'headers': {'authorization': 'Bearer ' + token} if token else {}}


def adventure(store):
    player = store.request(message('/api/register', {'name': 'Alice', 'class_name': 'Knight'}))['body']
    result = store.request(message('/api/commands', {'request_id': uuid.uuid4().hex, 'action': 'tutorial', 'params': {}}, player['token']))
    assert result['status'] == 200
    store.saved(store.pending_batch())
    return player, result['body']['session']['id']


def mutate(store, session_id, change):
    party = json.loads(store.db.execute('SELECT data FROM tutorials WHERE session_id=?', (session_id,)).fetchone()[0])
    change(party)
    store.db.execute('UPDATE tutorials SET data=? WHERE session_id=?', (json.dumps(party), session_id))
    return party


def test_refresh_and_combat_do_not_access_turso(monkeypatch):
    store = RuntimeStore(ENV)
    player, room = adventure(store)
    def blocked(*args, **kwargs):
        raise AssertionError('Accès distant pendant le jeu')
    monkeypatch.setattr(realtime_store, 'TursoConnection', blocked)
    for index in range(20):
        mutate(store, room, lambda party: party['characters'][player['player']['id']]['stats']['hp'].update(current=5))
        response = store.request(message('/api/state', token=player['token']))
        assert response['status'] == 200
        assert response['headers']['X-RPG-Runtime'] == 'memory'
    assert not store.pending
    store.close()


def test_rapid_progress_changes_are_coalesced_and_rooms_are_not_saved():
    store = RuntimeStore(ENV)
    player, room = adventure(store)
    identifier = player['player']['id']
    mutate(store, room, lambda party: party.update(position='rosee'))
    store.capture()
    store.saved(store.pending_batch())
    mutate(store, room, lambda party: party['characters'][identifier].update(exp=50))
    store.capture(now=100)
    assert store.due == 105
    mutate(store, room, lambda party: party['inventory'][identifier].update(wood=2))
    store.capture(now=102)
    assert store.due == 105
    saved = json.loads(store.pending[('tutorials', (room,))]['data'])
    mutate(store, room, lambda party: party.update(position=__import__('jeuxRPG.multiplayer.world', fromlist=['PLACES']).PLACES['rosee']['points'][0]['id'], combat_step='another-room'))
    store.capture(now=103)
    assert json.loads(store.pending[('tutorials', (room,))]['data']) == saved
    assert saved['characters'][identifier]['exp'] == 50
    assert saved['inventory'][identifier]['wood'] == 2
    store.close()


def test_completed_quests_and_level_trigger_checkpoint():
    store = RuntimeStore(ENV)
    player, room = adventure(store)
    mutate(store, room, lambda party: party.update(quest='completed'))
    store.capture()
    assert ('tutorials', (room,)) in store.pending
    store.saved(store.pending_batch())
    mutate(store, room, lambda party: party['characters'][player['player']['id']].update(level=2))
    store.capture()
    assert ('tutorials', (room,)) in store.pending
    store.close()


def test_accepting_mira_quest_is_saved_without_refresh_writes():
    store = RuntimeStore(ENV, clock=SimpleNamespace(now=lambda: 0, ratio=240))
    player, room = adventure(store)
    mutate(store, room, lambda party: party.update(step='village', position='mira'))
    store.capture()
    store.saved(store.pending_batch())
    state = store.request(message('/api/state', token=player['token']))['body']['session']
    result = store.request(message('/api/commands', {'request_id': uuid.uuid4().hex, 'action': 'talk',
                           'params': {'npc': 'mira', 'session_id': room, 'revision': state['revision']}}, player['token']))
    assert result['status'] == 200
    assert result['body']['session']['tutorial']['quest'] == 'active'
    assert json.loads(store.pending[('tutorials', (room,))]['data'])['quest'] == 'active'
    store.saved(store.pending_batch())
    for _ in range(5):
        assert store.request(message('/api/state', token=player['token']))['status'] == 200
    assert not store.pending
    store.close()


def test_mira_accepts_time_only_revision_and_rejects_changed_quest():
    store = RuntimeStore(ENV, clock=SimpleNamespace(now=lambda: 0, ratio=240))
    player, room = adventure(store)
    mutate(store, room, lambda party: party.update(step='village', position='mira'))
    state = store.request(message('/api/state', token=player['token']))['body']['session']
    params = {'npc': 'mira', 'session_id': room, 'revision': state['revision'],
              'world_context': state['tutorial']['world_context']}
    store.db.execute('UPDATE sessions SET revision=revision+100 WHERE id=?', (room,))
    def talk():
        return store.request(message('/api/commands', {'request_id': uuid.uuid4().hex, 'action': 'talk', 'params': params}, player['token']))
    accepted = talk()
    assert accepted['status'] == 200
    assert accepted['body']['session']['tutorial']['quest'] == 'active'
    stale = talk()
    assert stale['status'] == 409
    assert stale['body']['error'] == 'stale_revision'
    store.close()


def test_same_zone_room_does_not_change_signature():
    a = {'position': 'rosee', 'inventory': {}, 'characters': {}}
    from jeuxRPG.multiplayer.world import PLACES
    point = PLACES['rosee']['points'][0]['id']
    assert progress_signature(a) == progress_signature({**a, 'position': point})
    assert progress_signature(a) != progress_signature({**a, 'position': 'brume'})


def test_joystick_stop_cancels_route_without_checkpoint():
    from jeuxRPG.multiplayer import fields
    store = RuntimeStore(ENV, clock=SimpleNamespace(now=lambda: 0, ratio=240))
    player, room = adventure(store)
    identifier = player['player']['id']
    def prepare(party):
        fields.enter(party, 'rosee', [32,20], 0)
        party['battle']['players'][identifier]['route'] = [[33,20]]
    mutate(store, room, prepare)
    state = store.request(message('/api/state', token=player['token']))['body']['session']
    store.saved(store.pending_batch())
    store.db.execute('UPDATE sessions SET revision=revision+100 WHERE id=?', (room,))
    params = {'session_id':room, 'revision':state['revision'], 'encounter':state['tutorial']['encounter_number']}
    result = store.request(message('/api/commands', {'request_id':uuid.uuid4().hex, 'action':'stop_move', 'params':params}, player['token']))
    assert result['status'] == 200
    assert result['body']['session']['tutorial']['battle']['players'][identifier]['route'] == []
    assert not store.pending
    params['encounter'] += 100
    result = store.request(message('/api/commands', {'request_id':uuid.uuid4().hex, 'action':'stop_move', 'params':params}, player['token']))
    assert result['status'] == 409
    store.close()


def test_persistence_is_batched_and_fenced(monkeypatch):
    transport = Transport()
    initialize(transport.db)
    monkeypatch.setattr(realtime_store, 'TursoConnection', lambda *args: TursoConnection('https://test.invalid', 'test-token', transport=transport))
    store = RuntimeStore({**ENV, 'TURSO_DATABASE_URL': 'https://test.invalid', 'TURSO_AUTH_TOKEN': 'test-token'})
    player = store.request(message('/api/register', {'name': 'Alice', 'class_name': 'Knight'}))['body']
    batch = store.pending_batch()
    store.persist(10, batch)
    store.saved(batch)
    assert transport.db.execute('SELECT name FROM players').fetchone()[0] == 'Alice'
    assert not store.pending
    with pytest.raises(RuntimeError, match='remplacé'):
        store.persist(9, batch)
    assert not transport.db.in_transaction
    store.close()


def test_save_failure_keeps_changes_for_retry(monkeypatch):
    async def run():
        store = RuntimeStore(ENV)
        store.request(message('/api/register', {'name': 'Alice', 'class_name': 'Knight'}))
        calls = []
        def persist(fence, batch):
            calls.append(batch)
            if len(calls) == 1:
                raise OSError('Turso indisponible')
        monkeypatch.setattr(store, 'persist', persist)
        coordinator = Coordinator(ENV, store=store)
        await coordinator.save(store, store.pending_batch(), store.snapshot(), 1)
        assert store.pending and store.last_save_error
        await coordinator.save(store, store.pending_batch(), store.snapshot(), 1)
        assert not store.pending and store.save_count == 1
        store.close()
    asyncio.run(run())


def test_websocket_rpc_push_and_origin_protection():
    store = RuntimeStore(ENV)
    coordinator = Coordinator(ENV, store=store)
    reads = []
    original_rpc = coordinator.rpc
    async def counted_rpc(message):
        if message.get('path') == '/api/state':
            reads.append(message)
        return await original_rpc(message)
    coordinator.rpc = counted_rpc
    app = create_app(ENV, coordinator)
    with TestClient(app, base_url='http://localhost') as client:
        with pytest.raises(Exception):
            with client.websocket_connect('/api/ws', headers={'origin': 'https://evil.test'}):
                pass
        with client.websocket_connect('/api/ws', headers={'origin': 'http://localhost', 'host': 'localhost'}) as socket:
            socket.send_json({'id': 'register', 'path': '/api/register', 'method': 'POST', 'body': {'name': 'Alice', 'class_name': 'Knight'}})
            registered = socket.receive_json()['result']
            assert registered['status'] == 201
            socket.send_json({'id': 'state', 'path': '/api/state', 'headers': {'Authorization': 'Bearer ' + registered['body']['token']}})
            state = socket.receive_json()
            assert state['id'] == 'state' and state['result']['status'] == 200
            pushed = socket.receive_json()
            assert pushed['type'] == 'state' and pushed['subscription'] == 'state'
            assert pushed['result']['headers']['X-RPG-Runtime'] == 'memory'
            socket.send_json({'type':'visibility', 'active':False})
            while socket.receive_json().get('type') != 'visibility':
                pass
            before = len(reads)
            time.sleep(.7)
            socket.send_json({'type':'ping'})
            assert socket.receive_json()['type'] == 'pong'
            assert len(reads) == before
            socket.send_json({'type':'visibility', 'active':True})
            assert socket.receive_json()['type'] == 'visibility'
            assert socket.receive_json()['type'] == 'state'


def test_http_compatibility_reads_same_memory():
    store = RuntimeStore(ENV)
    app = create_app(ENV, Coordinator(ENV, store=store))
    with TestClient(app, base_url='http://localhost') as client:
        registered = client.post('/api/register', json={'name': 'Alice', 'class_name': 'Knight'})
        assert registered.status_code == 201
        token = registered.json()['token']
        state = client.get('/api/state', headers={'authorization': 'Bearer ' + token})
        assert state.status_code == 200
        assert state.headers['x-rpg-runtime'] == 'memory'
        assert client.get('/api/admin/accounts').status_code == 401


@pytest.mark.skipif(not os.environ.get('RPG_TEST_REDIS_URL'), reason='Redis réel disponible dans le workflow de publication')
def test_two_instances_share_one_engine_and_recover_checkpoint(monkeypatch):
    async def run():
        persisted = []
        monkeypatch.setattr(RuntimeStore, 'load', classmethod(lambda cls, environment: RuntimeStore(environment)))
        monkeypatch.setattr(RuntimeStore, 'persist', lambda self, fence, batch: persisted.append((fence, batch)))
        a = Coordinator(ENV, redis=Redis.from_url(os.environ['RPG_TEST_REDIS_URL'], decode_responses=True))
        b = Coordinator(ENV, redis=Redis.from_url(os.environ['RPG_TEST_REDIS_URL'], decode_responses=True))
        prefix = 'test:jeux-rpg:' + uuid.uuid4().hex + ':'
        a.prefix = b.prefix = prefix
        try:
            await a.start()
            await b.start()
            assert a.owner() and not b.owner()
            registered = await a.rpc(message('/api/register', {'name': 'Alice', 'class_name': 'Knight'}))
            token = registered['body']['token']
            mirrored = await b.rpc(message('/api/state', token=token))
            assert mirrored['body']['player']['id'] == registered['body']['player']['id']
            deadline = asyncio.get_running_loop().time() + 5
            while a.outgoing or not a.received.empty():
                assert asyncio.get_running_loop().time() < deadline
                await asyncio.sleep(.05)
            for _ in range(30):
                assert (await a.rpc(message('/api/state', token=token)))['status'] == 200
            assert not a.outgoing and not a.pending
            await a.flush()
            assert len(persisted) == 1
            old_fence = a.fence
            await a.release()
            await b.elect()
            assert b.owner() and b.fence > old_fence
            assert not b.store.pending
            recovered = await b.rpc(message('/api/state', token=token))
            assert recovered['body']['player']['id'] == registered['body']['player']['id']
            stale = await a.execute(message('/api/state', token=token))
            assert stale['status'] == 503
        finally:
            await a.close()
            await b.redis.delete(prefix + 'lease', prefix + 'fence', prefix + 'checkpoint')
            await b.close()
    asyncio.run(run())


def test_catalogue_does_not_start_a_database_or_coordinator(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Le catalogue ne doit pas démarrer le moteur')
    monkeypatch.setattr(RuntimeStore, 'load', blocked)
    app = create_app(ENV)
    with TestClient(app, base_url='http://localhost') as client:
        response = client.get('/api/classes')
        assert response.status_code == 200
        assert any(item['id'] == 'Knight' for item in response.json())
        assert not app.state.coordinator.started
        home = client.get('/')
        assert home.status_code == 200
        assert '{{CLASS_OPTIONS}}' not in home.text
        assert 'value="Knight"' in home.text
