import json
import statistics
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

from jeuxRPG.multiplayer import accounts, content, world
from jeuxRPG.multiplayer.catalogue import catalogue
from jeuxRPG.multiplayer.controller import Project
from jeuxRPG.multiplayer.realtime_store import RuntimeStore


def main():
    root = Path(__file__).resolve().parent.parent
    project = Project(root / 'jeuxRPG' / 'maps')
    assert project.validate()
    assert set(world.WORLD_MAP_DATA) == set(project.maps)
    classes = [item['id'] for item in catalogue()]
    assert len(classes) == 5
    env = {'VERCEL': '1', 'VERCEL_URL': 'localhost'}
    store = RuntimeStore(env, clock=SimpleNamespace(now=lambda: 0, ratio=3))
    original_hash = accounts.password_hash
    accounts.password_hash = lambda password, salt=None: 'scrypt$' + (salt or '00') + '$setup'
    tokens = []
    try:
        for index in range(40):
            class_name = classes[index % len(classes)]
            account = store.service.account_login(f'load_{index}', 'a-long-test-password', signup=True)
            token = account['token']
            store.service.account_character(token, 'create', name=f'Joueur {index}', class_name=class_name)
            store.service.command(token, uuid.uuid4().hex, 'tutorial')
            tokens.append(token)
    finally:
        accounts.password_hash = original_hash
    timings = []
    for _ in range(2):
        for token in tokens:
            started = time.perf_counter()
            state = store.request({'path': '/api/state', 'method': 'GET', 'host': 'localhost', 'peer': '127.0.0.1', 'scheme': 'https', 'headers': {'authorization': 'Bearer ' + token}})
            timings.append((time.perf_counter() - started) * 1000)
            assert state['status'] == 200
            assert all(player['hp'] > 0 for player in state['body']['session']['tutorial']['players'])
            assert state['body']['session']['state'] == 'running'
            assert state['headers']['X-RPG-Runtime'] == 'memory'
    store.tick()
    recovered = RuntimeStore(env, json.loads(store.snapshot()), clock=SimpleNamespace(now=lambda: 0, ratio=3))
    assert recovered.db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0] == 40
    assert recovered.db.execute('SELECT COUNT(*) FROM tutorials').fetchone()[0] == 40
    p95 = statistics.quantiles(timings, n=20)[18]
    assert p95 < 500, f'Régression du moteur : p95={p95:.1f} ms'
    print(json.dumps({'players': 40, 'classes': classes, 'maps': len(project.maps), 'quests': len(content.DATA['quests']), 'state_requests': len(timings), 'p95_ms': round(p95,2), 'max_ms': round(max(timings),2), 'recovered_tutorials': 40}))
    recovered.close()
    store.close()


if __name__ == '__main__':
    main()
