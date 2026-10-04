from . import progression, world, content


def record(party):
    stats = party.setdefault("achievements", {"kills": 0, "max_level": 1, "zones": [], "best_seconds": None, "titles": []})
    stats["max_level"] = max(stats["max_level"], *(c["level"] for c in party["characters"].values()))
    stats["zones"] = sorted(set(stats["zones"]) | set(party.get("visited", [])))
    return stats


def victory(party, now):
    battle = party["battle"]
    if battle.get("arrivals") or party.get("training") or battle.get("awarded") or party["mobs"] or "initial_mobs" not in battle:
        return
    battle["awarded"] = True
    stats = record(party)
    seconds = max(0, now - battle["started_at"]) / progression.RATIO
    stats["best_seconds"] = seconds if stats["best_seconds"] is None else min(stats["best_seconds"], seconds)
    titles = set(stats["titles"])
    count = battle.get("initial_mobs", 1)
    players = battle.get("initial_players", 1)
    conditions = {'silent': not battle.get('enemy_alerted'), 'untouched': not battle.get('damage_received'), 'higher': players == count == 1 and battle.get('higher_level'), 'superiority': players > count, 'inferiority': players < count}
    for definition in content.DATA['achievements']:
        condition = definition['condition']
        if (conditions.get(condition) and (condition != 'higher' or max(1, battle.get('level_difference', 0)) >= definition['threshold'])) or condition == 'fast' and seconds <= definition['threshold']:
            titles.add(definition['title'])
    if conditions['higher']:
        stats['level_difference'] = max(stats.get('level_difference', 0), battle.get('level_difference', 0))
    stats["titles"] = sorted(titles)


def view(party):
    stats = record(party)
    rows = []
    for zone, definition in world.PLACES.items():
        rows.append({"name": "Découvrir " + definition["name"], "progress": "Découvert" if zone in stats["zones"] else "À découvrir", "title": "Éclaireur de " + definition["name"], "unlocked": zone in stats["zones"]})
    for definition in content.DATA['achievements']:
        condition = definition['condition']
        value = stats['max_level'] if condition == 'level' else stats['kills'] if condition == 'kills' else None
        unlocked = value >= definition['threshold'] if value is not None else definition['title'] in stats['titles']
        title = definition['title']
        if condition == 'higher':
            difference = stats.get('level_difference', 0)
            title += f" (+{difference} niveaux)" if difference else " (différence de niveau)"
        rows.append({'name': definition['name'], 'progress': f"{value}/{definition['threshold']:g}" if value is not None else 'Accompli' if unlocked else 'À accomplir', 'title': title, 'unlocked': unlocked})
    return {**stats, "rows": rows, "unlocked_titles": [r["title"] for r in rows if r["unlocked"]]}
