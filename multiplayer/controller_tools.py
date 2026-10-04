from copy import deepcopy
import json

from . import content, mob_rules, map_building


def catalog_rows(project, section):
    p = project
    if section == 'maps':
        return [(key, data['name'], f"{data['width']} × {data['height']} · zone {map_building.zone_of(p.maps, key)}") for key, data in p.maps.items()]
    if section == 'mobs':
        return [(key, mob_rules.resolve(p.mobs, key)['name'], f"{mob_rules.resolve(p.mobs, key)['class_name']} · rang {mob_rules.resolve(p.mobs, key)['rank']} · parent {item.get('parent') or 'aucun'}") for key, item in p.mobs.items()]
    if section == 'quests':
        return [(q['id'], q['name'], f"{q['npc']} · {q['kind']} {q['target']} × {q['count']} · {q.get('zone') or 'toutes zones'} · {q['reward_xp']} XP") for q in p.content[section]]
    if section == 'achievements':
        return [(a['id'], a['name'], f"{a['condition']} · {a['threshold']} · cible {a.get('target') or 'toutes'} · zone {a.get('zone') or 'toutes'} · carte {a.get('map') or 'toutes'} → {a['title']}") for a in p.content[section]]
    if section == 'npcs':
        return [(f'{key}:{index}', site['name'], f"{key} · {site['id']} · case {site['position']}") for key, data in p.maps.items() for index, site in enumerate(data.get('sites', []))]
    if section == 'classes':
        return [(item['id'], item['name'], ('Jouable' if item['playable'] else item['class_type']) + ' · ' + str(len(item['skills'])) + ' compétences') for item in p.content['templates']['classes']]
    if section == 'skill_models':
        return [(key,item['name'],item['type']+' · '+item['energy']+' · coût '+str(item['cost'])) for key,item in p.content['templates']['skills'].items() if not key.startswith(('skill:','mob:'))]
    if section == 'skills':
        return [(item['id'], item['name'], item['type'] + ' · portée ' + str(item['range'])) for item in p.content.get('skills', [])]
    if section == 'world':
        return [(key, key, str(value)) for key, value in p.content['world'].items()]
    raise ValueError('Catalogue inconnu.')


def filter_rows(rows, query):
    words = query.casefold().split()
    return [row for row in rows if all(word in ' '.join(str(value) for value in row).casefold() for word in words)]


def references(project, section, identifier):
    tokens = {identifier}
    if section == 'skills':
        tokens = {'skill:' + identifier}
    if section == 'npcs' and ':' in identifier:
        map_id, index = identifier.rsplit(':', 1)
        tokens = {project.maps[map_id]['sites'][int(index)]['id']}
    result = []
    relevant = {'maps': {'zone_id','world_zone','fast_travel_origin','destination','fast_destination','from','to','zone','map'}, 'mobs': {'mob_id','parent','target','skill_id'}, 'classes': {'class_name','base_class','class'}, 'skills': {'skill_id'}, 'skill_models': {'skill_id'}, 'quests': {'quests','target'}, 'achievements': {'achievements'}, 'npcs': {'npc'}}.get(section, set())
    def visit(value, path, field=''):
        if isinstance(value, dict):
            for key, nested in value.items():
                visit(nested, path + '/' + str(key), key)
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                visit(nested, path + '/' + str(index), field)
        elif isinstance(value, str) and field in relevant:
            if value in tokens or section == 'mobs' and field == 'skill_id' and value.startswith('mob:' + identifier + ':'):
                result.append(path)
    visit(project.maps, 'cartes')
    visit(project.mobs, 'mobs')
    visit(project.content, 'contenu')
    return sorted(set(result))


def preview(project, section, identifier, level=1, player_level=1):
    if type(level) is not int or not 1 <= level <= 100 or type(player_level) is not int or not 1 <= player_level <= 100:
        raise ValueError('Niveaux entiers entre 1 et 100.')
    if section == 'mobs':
        definition = mob_rules.resolve(project.mobs, identifier)
        from .forge import RARE_DROPS
        rules = mob_rules.drop_rules(definition, RARE_DROPS)
        class_view = preview(project,'classes',definition['class_name'],level)
        stats = deepcopy(class_view['stats'])
        if identifier == 'goblin':
            from .world import GOBLIN
            base = preview(project,'classes',definition['class_name'],1)['stats']['hp']
            stats['hp'] = GOBLIN['hp_hunt'] + max(0,stats['hp']-base)
        stats.update({key:round(value['base']+value['growth']*(level-1)) for key,value in definition.get('stats',{}).items()})
        return {'stats':stats, 'modèle_au_niveau':class_view, 'espèce': identifier, 'niveau': level, 'niveau_joueur': player_level, 'dégâts': round(definition['damage'] + (level - 1) * definition['damage_growth']) if 'damage_growth' in definition else definition['damage'] + (level - 1) // 2, 'stats_remplacées': {key: round(value['base'] + value['growth'] * (level - 1)) for key, value in definition.get('stats', {}).items()}, 'xp': mob_rules.experience({**definition, 'level': level}, player_level, project.content['world']['mob_xp'], project.content['templates']), 'drops': [{'matériau': rule['item'], 'rare': rule['rare'], 'chance_au_moins_un_drop': round(1 - (1 - rule['chance']) ** rule['attempts'], 8), 'quantité_moyenne': rule['attempts'] * rule['chance'] * (rule['min'] + rule['max']) / 2} for rule in rules], 'définition_résolue': definition}
    if section == 'classes':
        from jeuxRPG._class.universal_character import register_model
        from jeuxRPG._class.character import CharacterMeta
        from . import progression
        model = next(item for item in project.content['templates']['classes'] if item['id'] == identifier)
        if model['class_type'] == 'INVOCATION':
            return deepcopy(model)
        before = CharacterMeta._classes.copy()
        try:
            actor_type = register_model(model, project.content['templates'])
            actor = progression.configure(actor_type('preview', 'Aperçu'))
            if level > 1:
                actor.gain_exp(sum(progression.required(value) for value in range(1, level)))
            return {'classe': identifier, 'niveau': actor.level, 'stats': {name: getattr(actor, name).value for name in ('hp','force','endurance','intelligence','sagesse')}, 'énergies': [{'type': type(value).__name__, 'maximum': value.value, 'régénération': value.regen_rate} for value in actor.energie], 'attaque': progression.simple_damage(actor), 'portée': progression.attack_range(actor), 'compétences': [{'nom': skill.name, 'coût': skill.energie_cost, 'cooldown': skill.cooldown, 'incantation': progression.casting(skill)} for skill in actor.skills.values()]}
        finally:
            CharacterMeta._classes.clear()
            CharacterMeta._classes.update(before)
    if section == 'skill_models':
        return deepcopy(project.content['templates']['skills'][identifier])
    if section == 'maps':
        return deepcopy(project.maps[identifier])
    if section == 'npcs':
        map_id, index = identifier.rsplit(':', 1)
        return deepcopy(project.maps[map_id]['sites'][int(index)])
    if section == 'world':
        return {identifier: project.content['world'][identifier]}
    return deepcopy(next(item for item in project.content[section] if item['id'] == identifier))


def report(project):
    from .map_assets import validate as validate_maps
    from .skill_catalog import validate as validate_skills
    models = project.content['templates']
    classes = [item['id'] for item in models['classes'] if item['class_type'] != 'INVOCATION']
    checks = [('Contenu et classes', lambda: content.validate_content(project.content)), ('Espèces et drops', lambda: mob_rules.validate_mobs(project.mobs, classes)), ('Compétences et références', lambda: validate_skills(project.content, project.mobs)), ('Succès et lieux', lambda: content.validate_references(project.content, project.mobs, project.maps))]
    previous = map_building.MOBS
    errors = []
    try:
        map_building.MOBS = project.mobs
        checks.append(('Cartes et placements', lambda: validate_maps(project.maps)))
        for name, check in checks:
            try:
                check()
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(name + ' : ' + str(exc))
    finally:
        map_building.MOBS = previous
    npcs = {site['id'] for data in project.maps.values() for site in data.get('sites', [])}
    for quest in project.content['quests']:
        if quest['npc'] not in npcs:
            errors.append(quest['name'] + ' : PNJ donneur introuvable.')
    warnings = []
    for identifier, species in project.mobs.items():
        for drop in mob_rules.resolve(project.mobs, identifier).get('drops', []):
            if drop['chance'] == 0:
                warnings.append(identifier + ' : drop désactivé pour ' + drop['item'])
    for key, definition in project.maps.items():
        if not definition.get('exits'):
            warnings.append(key + ' : aucune sortie ; vérifier que cette impasse est voulue.')
    return {'erreurs': errors, 'avertissements': warnings, 'catalogues': {key: len(catalog_rows(project, key)) for key in ('maps','quests','mobs','achievements','npcs','classes','skills','skill_models')}}


def text(value):
    return json.dumps(value, ensure_ascii=False, indent=2)
