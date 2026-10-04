from collections import deque


def issues(maps):
    result = []
    incoming = {key: [] for key in maps}
    for source, definition in maps.items():
        for gate in definition.get('exits', []):
            if gate.get('destination') in incoming:
                incoming[gate['destination']].append((source, tuple(gate['entry'])))
    for key, definition in maps.items():
        blocked = {tuple(p) for field in ('cover', 'blocked') for p in definition.get(field, [])}
        blocked.update(tuple(p) for p in definition.get('water', []) if p not in definition.get('bridges', []))
        def walkable(point):
            return 0 <= point[0] < definition['width'] and 0 <= point[1] < definition['height'] and point not in blocked
        exits = [(gate.get('name', 'Sortie'), tuple(gate['position'])) for gate in definition.get('exits', [])]
        starts = list(incoming[key] or exits[:1])
        if key == 'clearing':
            cells = [(x, y) for x in range(definition['width']) for y in range(definition['height']) if walkable((x, y))]
            if cells:
                start = min(cells, key=lambda p: ((p[0] - 1) ** 2 + (p[1] - 10) ** 2, p[1], p[0]))
                starts.append(('apparition initiale', start))
        for name, start in starts:
            if not walkable(start):
                result.append(f'{key} : arrivée {name} impraticable en {start}.')
                continue
            reached = {start}
            queue = deque([start])
            while queue:
                x, y = queue.popleft()
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        point = (x + dx, y + dy)
                        if point in reached or not walkable(point) or dx and dy and (not walkable((x + dx, y)) or not walkable((x, y + dy))):
                            continue
                        reached.add(point)
                        queue.append(point)
            for label, point in exits:
                if point not in reached:
                    result.append(f'{key} : {label} en {point} inaccessible depuis {name}.')
            for site in definition.get('sites', []):
                x, y = site['position']
                if not any((x + dx, y + dy) in reached for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                    result.append(f"{key} : PNJ/atelier {site['name']} inaccessible depuis {name}.")
            for point in definition.get('spawns', []):
                if tuple(point) not in reached:
                    result.append(f'{key} : spawner {point} inaccessible depuis {name}.')
        if not exits:
            result.append(f'{key} : aucune sortie ; le joueur ne peut pas quitter cette carte.')
    return list(dict.fromkeys(result))


def validate(maps):
    errors = issues(maps)
    if errors:
        raise ValueError('\n'.join(errors))
    return maps
