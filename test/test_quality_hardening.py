import asyncio
import hashlib
import json
import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from jeuxRPG.multiplayer import accounts, admin, realtime_store
from jeuxRPG.multiplayer.realtime import Coordinator, create_app
from jeuxRPG.multiplayer.realtime_store import RuntimeStore
from jeuxRPG.multiplayer.turso import TursoConnection
from test_realtime import ENV, adventure, message
from test_serverless import Transport


def test_invalid_json_is_rejected_before_starting_engine():
    app = create_app(ENV)
    with TestClient(app, base_url='http://localhost') as client:
        for raw in ('{"username":"alice","username":"bob","password":"longpassword"}', '[]', 'null', '{"x":NaN}', '{'):
            response = client.post('/api/account/signup', content=raw, headers={'content-type': 'application/json'})
            assert response.status_code == 400
            assert response.json()['error'] == 'invalid_json'
            assert not app.state.coordinator.started


def test_anonymous_websocket_cannot_take_authenticated_slot():
    env = {'VERCEL': '1', 'VERCEL_URL': 'game.test'}
    store = RuntimeStore(env)
    coordinator = Coordinator(env, store=store)
    with TestClient(create_app(env, coordinator), base_url='https://game.test') as client:
        with client.websocket_connect('/api/ws', headers={'origin': 'https://game.test', 'host': 'game.test'}) as socket:
            assert coordinator.connections == 0
            socket.send_json({'type': 'ping'})
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()
        assert coordinator.connections == coordinator.handshakes == 0
        assert not coordinator.started


def test_authenticated_websocket_and_token_binding(monkeypatch):
    monkeypatch.setattr(accounts, 'password_hash', lambda password, salt=None: 'scrypt$' + (salt or '00') + '$hash')
    env = {'VERCEL': '1', 'VERCEL_URL': 'game.test'}
    store = RuntimeStore(env)
    token = store.service.account_login('alice', 'passwordpassword', signup=True)['token']
    coordinator = Coordinator(env, store=store)
    with TestClient(create_app(env, coordinator), base_url='https://game.test') as client:
        with client.websocket_connect('/api/ws', headers={'origin': 'https://game.test', 'host': 'game.test'}) as socket:
            socket.send_json({'type': 'authenticate', 'headers': {'Authorization': 'Bearer ' + token}})
            assert socket.receive_json()['type'] == 'authenticated'
            assert coordinator.connections == 1
            socket.send_json({'id': 'identity', 'path': '/api/account/me', 'headers': {'Authorization': 'Bearer ' + token}})
            assert socket.receive_json()['result']['status'] == 200
            socket.send_json({'id': 'other', 'path': '/api/account/me', 'headers': {'Authorization': 'Bearer ' + 'x' * 40}})
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()


def test_rename_survives_checkpoint():
    store = RuntimeStore(ENV)
    player, room = adventure(store)
    admin.update_account(store.service, {'player_id': player['player']['id'], 'action': 'rename', 'name': 'Après'})
    store.capture(dirty_only=True)
    assert ('tutorials', (room,)) in store.pending
    restored = RuntimeStore(ENV, json.loads(store.snapshot()))
    data = json.loads(restored.db.execute('SELECT data FROM tutorials WHERE session_id=?', (room,)).fetchone()[0])
    assert data['characters'][player['player']['id']]['name'] == 'Après'
    restored.close()
    store.close()


def test_receipt_retention_deletion_is_durable(monkeypatch):
    transport = Transport()
    connection = TursoConnection('https://db.test', 'secret', transport=transport)
    from jeuxRPG.multiplayer.schema import initialize
    initialize(connection)
    monkeypatch.setattr(connection, 'close', lambda: None)
    monkeypatch.setattr(realtime_store, 'TursoConnection', lambda *args: connection)
    store = RuntimeStore({**ENV, 'TURSO_DATABASE_URL': 'https://db.test', 'TURSO_AUTH_TOKEN': 'secret'})
    player, room = adventure(store)
    for table, rows in store.durable.items():
        for row in rows:
            store.pending[(table, tuple(row[key] for key in realtime_store.KEYS[table]))] = row
    expired = store.db.execute('SELECT player_id,request_id FROM receipts').fetchone()
    store.db.execute('UPDATE receipt_expiry SET expires=0')
    store.capture()
    store.persist(1, store.pending_batch())
    store.saved(store.pending_batch())
    assert connection.execute('SELECT COUNT(*) FROM receipts').fetchone()[0] == 1
    result = store.request(message('/api/commands', {'request_id': uuid.uuid4().hex, 'action': 'leave', 'params': {'session_id': room, 'revision': store.db.execute('SELECT revision FROM sessions WHERE id=?', (room,)).fetchone()[0]}}, player['token']))
    assert result['status'] == 200
    assert store.pending[('receipts', tuple(expired))] is None
    batch = store.pending_batch()
    store.persist(1, batch)
    store.saved(batch)
    store.saved(batch)
    assert connection.execute('SELECT COUNT(*) FROM receipts WHERE player_id=? AND request_id=?', tuple(expired)).fetchone()[0] == 0
    assert not store.pending
    store.close()


def test_password_work_does_not_block_game_requests(monkeypatch):
    started, finish = threading.Event(), threading.Event()
    def slow(password, salt=None):
        started.set()
        assert finish.wait(3)
        return 'scrypt$00$hash'
    monkeypatch.setattr(accounts, 'password_hash', slow)
    async def run():
        store = RuntimeStore(ENV)
        coordinator = Coordinator(ENV, store=store)
        task = asyncio.create_task(coordinator.execute(message('/api/account/signup', {'username': 'alice', 'password': 'passwordpassword'})))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            result = await asyncio.wait_for(coordinator.execute(message('/api/classes')), .5)
            assert result['status'] == 200
        finally:
            finish.set()
        assert (await task)['status'] == 201
        await coordinator.close()
    asyncio.run(run())


def test_static_assets_cache_and_security_headers():
    with TestClient(create_app(ENV), base_url='http://localhost') as client:
        home = client.get('/')
        asset = client.get('/app.js')
        digest = hashlib.sha256(asset.content).hexdigest()[:16]
        assert '/app.js?v=' + digest in home.text
        cached = client.get('/app.js?v=' + digest)
        assert 'immutable' in cached.headers['cache-control']
        assert client.get('/app.js', headers={'if-none-match': asset.headers['etag']}).status_code == 304
        classes = client.get('/api/classes')
        assert classes.headers['cache-control'] == 'no-store'
        assert classes.headers['x-content-type-options'] == 'nosniff'
        assert 'description' in home.text


def test_receipt_compression_and_legacy_compatibility():
    from jeuxRPG.multiplayer.command_journal import encode_receipt, decode_receipt
    payload = {'session': {'cells': [{'terrain': 'grass', 'position': [i, 0]} for i in range(10000)]}}
    compressed = encode_receipt(payload)
    assert compressed.startswith('zlib:')
    assert len(compressed) < len(json.dumps(payload)) / 2
    assert decode_receipt(compressed) == payload
    assert decode_receipt(json.dumps(payload)) == payload
