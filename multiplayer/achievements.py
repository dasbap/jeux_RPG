from . import progression, world, content


COMBAT_CONDITIONS = ('silent', 'untouched', 'fast', 'higher', 'superiority', 'inferiority', 'victories')
COUNTER_CONDITIONS = ('kills', 'craft', 'quests')


def record(party):
    stats = party.setdefault('achievements', {})
    if 'unlocked' not in stats:
        stats['legacy_titles'] = list(stats.get('titles', []))
    for key, value in [('kills', 0), ('max_level', 1), ('zones', []), ('best_seconds', None), ('titles', []), ('unlocked', []), ('counters', {}), ('victories', {}), ('maps', [])]:
        stats.setdefault(key, value)
    stats['max_level'] = max(stats['max_level'], *(c['level'] for c in party['characters'].values()))
    stats['zones'] = sorted(set(stats['zones']) | set(party.get('visited', [])))
    if party.get('field_map'):
        stats['maps'] = sorted(set(stats['maps']) | {party['field_map']})
    return stats


def context(party):
    identifier = party.get('field_map') or party['position']
    return world.zone_of(identifier), identifier


def matches(definition, target, zone, map_id):
    from .map_building import MOBS
    from .fields import MAPS
    targets = {definition.get('target')}
    if definition.get('target'):
        source = next((item for item in content.DATA['quests'] if item['id'] == definition['target']),{}) if definition['condition'] == 'quests' else MOBS.get(definition['target'],{}) if definition['condition'] != 'craft' else {}
        targets.update(source.get('previous_ids',[]))
    zones = {definition.get('zone'), *MAPS.get(definition.get('zone'),{}).get('previous_ids',[])}
    maps = {definition.get('map'), *MAPS.get(definition.get('map'),{}).get('previous_ids',[])}
    return (not definition.get('target') or target in targets) and (not definition.get('zone') or zone in zones) and (not definition.get('map') or map_id in maps)


def event(party, kind, target):
    if party.get('training'):
        return
    stats = record(party)
    zone, map_id = context(party)
    targets = stats['counters'].setdefault(kind, {}).setdefault(target, {}).setdefault(zone, {})
    targets[map_id] = targets.get(map_id, 0) + 1
    if kind == 'kills':
        stats['kills'] += 1
        if party.get('battle'):
            party['battle'].setdefault('defeated_targets', []).append({'target': target, 'zone': zone, 'map': map_id})


def progress(party, definition):
    stats = record(party)
    condition = definition['condition']
    if condition == 'level':
        return stats['max_level']
    if condition == 'quests' and not any(definition.get(key) for key in ('zone','map')):
        states = content.quest_states(party)
        completed = {item['id'] for item in content.DATA['quests'] if (party.get('quest') == 'completed' if content.is_hunt(item) else states.get(item['id'],{}).get('status') == 'completed')}
        history = stats['counters'].get('quests',{})
        for item in content.DATA['quests']:
            if any(key in history for key in [item['id'],*item.get('previous_ids',[])]):
                completed.add(item['id'])
        return int(definition['target'] in completed) if definition.get('target') else len(completed)
    if condition in COUNTER_CONDITIONS:
        if condition == 'kills' and not any(definition.get(key) for key in ('target', 'zone', 'map')):
            return stats['kills']
        return sum(count for target, zones in stats['counters'].get(condition, {}).items() for zone, maps in zones.items() for map_id, count in maps.items() if matches(definition, target, zone, map_id))
    if condition == 'discover':
        if definition.get('map'):
            return int(definition['map'] in stats['maps'])
        if definition.get('zone'):
            return int(definition['zone'] in stats['zones'])
        return len(stats['zones'])
    if condition in COMBAT_CONDITIONS:
        return max((stats['victories'].get(key, 0) for key in [definition['id'], *definition.get('previous_ids', [])]), default=0)
    return 0


def unlocked(party, definition):
    stats = record(party)
    identifiers = {definition['id'], *definition.get('previous_ids', [])}
    saved = any(identifier in stats['unlocked'] for identifier in identifiers)
    if not saved and definition['condition'] in COMBAT_CONDITIONS:
        saved = not any(definition.get(key) for key in ('target', 'zone', 'map')) and definition['title'] in stats.get('legacy_titles', [])
    required = 1 if definition['condition'] in ('fast', 'higher') else definition['threshold']
    acquired = saved or progress(party, definition) >= required
    if acquired and definition['id'] not in stats['unlocked']:
        stats['unlocked'].append(definition['id'])
    return acquired


def victory(party, now):
    battle = party['battle']
    if battle.get('arrivals') or party.get('training') or battle.get('awarded') or party['mobs'] or 'initial_mobs' not in battle:
        return
    battle['awarded'] = True
    stats = record(party)
    seconds = max(0, now - battle['started_at']) / progression.RATIO
    stats['best_seconds'] = seconds if stats['best_seconds'] is None else min(stats['best_seconds'], seconds)
    count = battle.get('initial_mobs', 1)
    players = battle.get('initial_players', 1)
    conditions = {'silent': not battle.get('enemy_alerted'), 'untouched': not battle.get('damage_received'), 'higher': players == count == 1 and battle.get('higher_level'), 'superiority': players > count, 'inferiority': players < count, 'victories': True}
    zone, map_id = context(party)
    targets = battle.get('defeated_targets', [])
    titles = set(stats['titles'])
    for definition in content.DATA['achievements']:
        condition = definition['condition']
        if condition not in COMBAT_CONDITIONS:
            continue
        eligible = conditions.get(condition, False)
        if condition == 'fast':
            eligible = seconds <= definition['threshold']
        if condition == 'higher':
            eligible = eligible and max(1, battle.get('level_difference', 0)) >= definition['threshold']
        if definition.get('target'):
            eligible = eligible and any(matches(definition, item['target'], item['zone'], item['map']) for item in targets)
        else:
            eligible = eligible and matches(definition, '', zone, map_id)
        if eligible:
            identifiers = [definition['id'], *definition.get('previous_ids', [])]
            previous = max((stats['victories'].get(key, 0) for key in identifiers), default=0)
            stats['victories'][definition['id']] = previous + 1
            if unlocked(party, definition):
                titles.add(definition['title'])
    if conditions['higher']:
        stats['level_difference'] = max(stats.get('level_difference', 0), battle.get('level_difference', 0))
    stats['titles'] = sorted(titles)


def scope_description(definition):
    parts = []
    if definition.get('target'):
        from .map_building import MOBS
        from .forge import RECIPES
        names = {**{key: value['name'] for key, value in MOBS.items()}, **{key: value['name'] for key, value in RECIPES.items()}, **{item['id']: item['name'] for item in content.DATA['quests']}}
        parts.append(names.get(definition['target'], definition['target']))
    for key in ('zone', 'map'):
        if definition.get(key):
            parts.append(world.point_name(definition[key]))
    return ' · '.join(parts)


def view(party):
    stats = record(party)
    rows = []
    for zone, definition in world.PLACES.items():
        rows.append({'name': 'Découvrir ' + definition['name'], 'progress': 'Découvert' if zone in stats['zones'] else 'À découvrir', 'title': 'Éclaireur de ' + definition['name'], 'unlocked': zone in stats['zones']})
    for definition in content.DATA['achievements']:
        condition = definition['condition']
        value = progress(party, definition)
        acquired = unlocked(party, definition)
        title = definition['title']
        if condition == 'higher':
            difference = stats.get('level_difference', 0)
            title += f' (+{difference} niveaux)' if difference else ' (différence de niveau)'
        name = definition['name']
        scope = scope_description(definition)
        if scope:
            name += ' · ' + scope
        numeric = condition not in ('fast', 'higher') and (condition in ('level', 'kills', 'craft', 'quests', 'discover', 'victories') or definition['threshold'] > 1)
        rows.append({'id': definition['id'], 'name': name, 'progress': f"{value}/{definition['threshold']:g}" if numeric else 'Accompli' if acquired else 'À accomplir', 'title': title, 'unlocked': acquired})
    visible = {key: value for key, value in stats.items() if key not in ('counters', 'victories', 'unlocked', 'maps', 'legacy_titles')}
    return {**visible, 'rows': rows, 'unlocked_titles': sorted({r['title'] for r in rows if r['unlocked']})}
