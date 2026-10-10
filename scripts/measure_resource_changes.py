import argparse
import ast
import json
import statistics
import subprocess
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from jeuxRPG.multiplayer import accounts, realtime_store, tactics
from jeuxRPG.multiplayer.distributed import PresenceRegistry
from jeuxRPG.multiplayer.realtime_store import RuntimeStore


def previous_method(revision, file, class_name, method, namespace):
    source = subprocess.check_output(['git', 'show', f'{revision}:{file}'], text=True)
    model = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == class_name)
    function = next(node for node in model.body if isinstance(node, ast.FunctionDef) and node.name == method)
    module = ast.Module(body=[function], type_ignores=[])
    scope = dict(namespace)
    exec(compile(ast.fix_missing_locations(module), file, 'exec'), scope)
    return scope[method]


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', default='f27dabee1b4b886ea117debf18d9cb6322c03356')
    parser.add_argument('--sessions', type=int, default=40)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.sessions < 1:
        parser.error('--sessions doit être positif')
    store = RuntimeStore({}, clock=type('Clock', (), {'ratio': 3, 'now': lambda self: 0})())
    try:
        rooms = []
        for index in range(args.sessions):
            player = store.service.register(f'Bench{index}', 'Knight')
            rooms.append(store.service.command(player['token'], uuid.uuid4().hex, 'tutorial')['session']['id'])
        report = {'baseline_commit': args.baseline, 'sessions': len(rooms), 'scope': 'local SQLite and counted presence operations; no remote services'}
        old_admit = previous_method(args.baseline, 'jeuxRPG/multiplayer/accounts.py', 'AccountMixin', '_admit', accounts.__dict__)
        old_signatures = previous_method(args.baseline, 'jeuxRPG/multiplayer/realtime_store.py', 'RuntimeStore', 'session_signatures', realtime_store.__dict__)
        for label, admit, signatures in [('before', old_admit, old_signatures), ('after', type(store.service)._admit, RuntimeStore.session_signatures)]:
            registry = store.service.runtime_presence = CountedPresence()
            store.service.realm_count = 3
            now = [100.0]
            with patch.object(accounts.time, 'time', lambda: now[0]):
                for _ in range(100):
                    assert admit(store.service, 'player') == 1
                    now[0] += .05
            queries = []
            store.db.set_trace_callback(queries.append)
            assert signatures(store, set()) == {}
            idle_queries = len(queries)
            store.db.set_trace_callback(None)
            durations = []
            for _ in range(100):
                started = time.perf_counter()
                assert set(signatures(store, {rooms[0]})) == {rooms[0]}
                durations.append((time.perf_counter() - started) * 1000)
            report[label] = {'presence_admissions': 100, 'presence_values_reads': registry.reads, 'presence_renewals': registry.writes,
                             'idle_signature_sql_queries': idle_queries, 'one_session_signature_median_ms': round(statistics.median(durations), 5)}
        source = subprocess.check_output(['git', 'show', f'{args.baseline}:jeuxRPG/multiplayer/tactics.py'], text=True)
        definitions = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in ('path', 'cached_path', 'valid_step', 'walkable')]
        scope = dict(tactics.__dict__)
        exec(compile(ast.fix_missing_locations(ast.Module(body=definitions, type_ignores=[])), 'baseline_tactics.py', 'exec'), scope)
        cases = []
        for preset in tactics.PRESETS.values():
            source = next(([x, y] for y in range(preset['height']) for x in range(preset['width']) if tactics.walkable(preset, [x, y])), None)
            if source:
                for destination in ([preset['width'] - 1, preset['height'] - 1], [preset['width'] // 2, preset['height'] // 2]):
                    if tactics.walkable(preset, destination):
                        cases.append((preset, source, destination))
        old_results = None
        for label, pathfinder, cached in [('before', scope['path'], scope['cached_path']), ('after', tactics.path, tactics.cached_path)]:
            durations = []
            for _ in range(3):
                cached.cache_clear()
                started = time.process_time()
                results = [pathfinder(*case) for case in cases]
                durations.append(time.process_time() - started)
            if old_results is None:
                old_results = results
            else:
                assert results == old_results
            report[label]['uncached_paths_cpu_median_seconds'] = round(statistics.median(durations), 5)
        report['path_cases'] = len(cases)
        report['identical_paths'] = True
        if args.output:
            Path(args.output).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, indent=2))
    finally:
        store.close()


if __name__ == '__main__':
    main()
