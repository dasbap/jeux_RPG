import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil

from .content import load_content, validate_content, CONDITIONS, is_hunt
from .map_assets import load, validate
from .map_building import zone_of


RANKS = ('SSS', 'SS', 'S', 'AA', 'A', 'B', 'C', 'D', 'E')


from .mob_rules import validate_mobs, resolve, CLASS_XP, drop_rules, STATS


DECIMAL_FIELDS = {'chance','threshold','xp_multiplier','damage_growth','power','growth','cooldown','cast','range','duration','repop_seconds','xp_base','xp_exponent','merchant_stay_hours'}


class Project:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        packaged = Path(__file__).resolve().parents[1] / 'maps'
        for source in packaged.glob('*.json'):
            target = self.directory/source.name
            if not target.exists():
                shutil.copyfile(source, target)
        self.content = load_content(self.directory/'content.json')
        self.mobs = validate_mobs(json.loads((self.directory/'mobs.json').read_text(encoding='utf-8'))['maps'],classes=[item['id'] for item in self.content['templates']['classes'] if item['class_type'] != 'INVOCATION'])
        from . import map_building
        previous = map_building.MOBS
        try:
            map_building.MOBS = self.mobs
            self.maps = load(self.directory/'world.json')
        finally:
            map_building.MOBS = previous
        from .map_assets import read_catalog
        self.encounters = read_catalog('encounters', self.directory)
        self.migrate_classes()
        self.snapshot = self.state()

    def migrate_classes(self):
        definitions = self.content.get('classes',[])
        if not definitions:
            return
        from .skill_catalog import install
        from .tutorial import blueprint
        from jeuxRPG._class.character import Character, CharacterMeta
        from jeuxRPG._class.res.character.class_models import model_from_actor
        old = CharacterMeta._classes.copy()
        try:
            install(self.content,self.mobs)
            for definition in definitions:
                actor = Character.create(definition['id'],'migration',definition['name'])
                model = model_from_actor(actor,definition['id'],definition['name'],self.content['templates'])
                model['formulas'] = deepcopy(definition.get('stats',{}))
                if definition.get('previous_ids'):
                    model['previous_ids'] = deepcopy(definition['previous_ids'])
                self.content['templates']['classes'].append(model)
            self.content['classes'] = []
        finally:
            CharacterMeta._classes.clear()
            CharacterMeta._classes.update(old)
            blueprint.cache_clear()

    def state(self):
        return deepcopy((self.maps, self.mobs, self.content, self.encounters))

    def document(self):
        return {'maps': deepcopy(self.maps), 'encounters': deepcopy(self.encounters), 'mobs': deepcopy(self.mobs), 'content': deepcopy(self.content)}

    def replace_document(self, document):
        roots = {'maps', 'encounters', 'mobs', 'content'}
        if not isinstance(document, dict) or set(document) != roots:
            raise ValueError('Le projet complet doit contenir exactement maps, encounters, mobs et content.')
        if not all(isinstance(document[key], dict) for key in roots):
            raise ValueError('Les racines du projet doivent être des objets JSON.')
        before = self.state()
        try:
            self.maps = deepcopy(document['maps'])
            self.encounters = deepcopy(document['encounters'])
            self.mobs = deepcopy(document['mobs'])
            self.content = deepcopy(document['content'])
            self.validate()
        except Exception:
            self.maps, self.mobs, self.content, self.encounters = before
            raise
        return self.document()

    def validate_encounters(self):
        import re
        from . import tactics
        if not isinstance(self.encounters, dict) or not self.encounters or len(self.encounters) > 100:
            raise ValueError('Le catalogue de rencontres doit contenir de 1 à 100 terrains.')
        required = {'clearing_1', 'clearing_2', 'clearing_3', 'lisiere_1', 'lisiere_2', 'lisiere_3', 'road_1', 'road_2', 'road_3', 'rosee_1', 'rosee_2', 'rosee_3', 'brume_1', 'brume_2', 'brume_3'}
        if not required <= self.encounters.keys():
            raise ValueError('Les quinze terrains de rencontre de base doivent être conservés.')
        for identifier, definition in self.encounters.items():
            if not isinstance(identifier, str) or not re.fullmatch(r'[a-z0-9_]{1,64}', identifier) or not isinstance(definition, dict):
                raise ValueError('Terrain de rencontre invalide.')
            width, height = definition.get('width'), definition.get('height')
            if type(width) is not int or type(height) is not int or not 4 <= width <= 128 or not 4 <= height <= 128:
                raise ValueError(f'{identifier} : dimensions invalides.')
            if definition.get('id') != identifier or not isinstance(definition.get('name'), str) or not definition['name']:
                raise ValueError(f'{identifier} : identifiant interne ou nom invalide.')
            def point(value):
                return isinstance(value, list) and len(value) == 2 and all(type(n) is int for n in value) and 0 <= value[0] < width and 0 <= value[1] < height
            for field in ('cover', 'blocked', 'water', 'bridges', 'paths'):
                values = definition.get(field, [])
                if not isinstance(values, list) or any(not point(value) for value in values):
                    raise ValueError(f'{identifier} : {field} invalide.')
            for item in definition.get('decorations', []):
                if not isinstance(item, dict) or not point(item.get('position')):
                    raise ValueError(f'{identifier} : décoration invalide.')
            route = tactics.patrol_route(definition, 0)
            if len(route) < 2 or any(not tactics.walkable(definition, value) for value in route) or any(tactics.path(definition, a, b) is None for a, b in zip(route, route[1:] + route[:1])):
                raise ValueError(f'{identifier} : terrain non parcourable.')
        return True

    def validate(self):
        validate_mobs(self.mobs,classes=[item['id'] for item in self.content['templates']['classes'] if item['class_type'] != 'INVOCATION'])
        from .skill_catalog import library, make_skill
        from jeuxRPG._class.res.character.class_models import skill_to_data
        available = library(self.content,self.mobs)
        definitions = self.content['templates']['skills']
        for identifier in list(definitions):
            if identifier.startswith(('skill:','mob:')):
                if identifier not in available:
                    if any(entry['skill_id'] == identifier for model in self.content['templates']['classes'] for entry in model['skills']):
                        raise ValueError('Compétence référencée introuvable : '+identifier)
                    del definitions[identifier]
                else:
                    definitions[identifier] = skill_to_data(make_skill(available[identifier],{}))
        validate_content(self.content)
        self.validate_encounters()
        from .skill_catalog import validate as validate_catalog
        validate_catalog(self.content,self.mobs)
        from . import map_building, forge
        previous = map_building.MOBS
        try:
            map_building.MOBS = self.mobs
            validate(self.maps)
        finally:
            map_building.MOBS = previous
        npcs = {site['id'] for data in self.maps.values() for site in data.get('sites', [])}
        for quest in self.content['quests']:
            if quest['npc'] not in npcs or quest.get('zone') and quest['zone'] not in self.maps or quest['kind'] == 'kill' and quest['target'] not in self.mobs or quest['kind'] == 'craft' and quest['target'] not in forge.RECIPES:
                raise ValueError(f"{quest['name']} : PNJ, zone ou cible introuvable.")
        from .content import validate_references
        validate_references(self.content, self.mobs, self.maps)
        return True

    def rename(self, section, identifier, replacement):
        import re
        if not isinstance(replacement, str) or not re.fullmatch(r'[a-zA-Z0-9_]{1,64}' if section == 'classes' else r'[a-z0-9_]{1,64}', replacement):
            raise ValueError('Identifiant : 1–64 lettres minuscules, chiffres ou underscores (ex. mira_hunt_2).')
        if identifier == replacement:
            return
        before = self.state()
        try:
            if section == 'classes' and any(item['id'] == identifier for item in self.content['templates']['classes']):
                item = next(item for item in self.content['templates']['classes'] if item['id'] == identifier)
                item['id'] = replacement
                item['previous_ids'] = list(dict.fromkeys([*item.get('previous_ids',[]),identifier]))
                for definition in self.content['templates']['skills'].values():
                    for effect in definition['effects'].values():
                        if effect.get('invocation',{} ) and effect['invocation'].get('class') == identifier:
                            effect['invocation']['class'] = replacement
                for species in self.mobs.values():
                    if species['class_name'] == identifier:
                        species['class_name'] = replacement
                for definition in self.content.get('classes',[]):
                    if definition['base_class'] == identifier:
                        definition['base_class'] = replacement
            elif section == 'skill_models':
                if replacement in self.content['templates']['skills']:
                    raise ValueError('Identifiant déjà utilisé.')
                self.content['templates']['skills'][replacement] = self.content['templates']['skills'].pop(identifier)
                for model in self.content['templates']['classes']:
                    for entry in model['skills']:
                        if entry['skill_id'] == identifier:
                            entry['skill_id'] = replacement
                for mob in self.mobs.values():
                    for entry in mob.get('abilities',[]):
                        if entry.get('skill_id') == identifier:
                            entry['skill_id'] = replacement
            elif section in ('classes','skills'):
                item = next(item for item in self.content.get(section,[]) if item['id'] == identifier)
                if any(other['id'] == replacement for other in self.content[section]):
                    raise ValueError('Identifiant déjà utilisé.')
                item['id'] = replacement
                if section == 'classes':
                    item['previous_ids'] = list(dict.fromkeys([*item.get('previous_ids',[]),identifier]))
                if section == 'skills':
                    cached = self.content['templates']['skills'].pop('skill:'+identifier,None)
                    if cached is not None:
                        self.content['templates']['skills']['skill:'+replacement] = cached
                    for definition in [*self.content.get('classes',[]), *self.content['templates']['classes'], *self.mobs.values()]:
                        for assignment in definition.get('skills',definition.get('abilities',[])):
                            if assignment.get('skill_id') == 'skill:'+identifier:
                                assignment['skill_id'] = 'skill:'+replacement
            elif section in ('quests', 'achievements'):
                item = next(item for item in self.content[section] if item['id'] == identifier)
                if any(other['id'] == replacement or replacement in other.get('previous_ids', []) for other in self.content[section] if other is not item):
                    raise ValueError('Identifiant déjà utilisé.')
                if section == 'quests' and is_hunt(item):
                    item['role'] = 'tutorial_hunt'
                item['previous_ids'] = list(dict.fromkeys([*item.get('previous_ids', []), identifier]))
                item['id'] = replacement
                if section == 'quests':
                    for success in self.content['achievements']:
                        if success['condition'] == 'quests' and success.get('target') == identifier:
                            success['target'] = replacement
                requirement_key = 'quests' if section == 'quests' else 'achievements'
                for quest in self.content['quests']:
                    requirements = quest.get('requirements', {})
                    if requirement_key in requirements:
                        requirements[requirement_key] = [replacement if value == identifier else value for value in requirements[requirement_key]]
            elif section == 'mobs':
                if identifier == 'goblin':
                    raise ValueError('goblin est une référence interne du tutoriel ; créez une nouvelle espèce pour un autre identifiant.')
                if replacement in self.mobs:
                    raise ValueError('Identifiant déjà utilisé.')
                self.mobs[replacement] = self.mobs.pop(identifier)
                self.mobs[replacement]['previous_ids'] = list(dict.fromkeys([*self.mobs[replacement].get('previous_ids',[]),identifier]))
                for species in self.mobs.values():
                    if species.get('parent') == identifier:
                        species['parent'] = replacement
                for definition in [*self.content.get('classes',[]), *self.content['templates']['classes'], *self.mobs.values()]:
                    for assignment in definition.get('skills',definition.get('abilities',[])):
                        reference = assignment.get('skill_id','')
                        if reference.startswith('mob:'+identifier+':'):
                            assignment['skill_id'] = 'mob:'+replacement+reference[len('mob:'+identifier):]
                for reference in list(self.content['templates']['skills']):
                    if reference.startswith('mob:'+identifier+':'):
                        self.content['templates']['skills']['mob:'+replacement+reference[len('mob:'+identifier):]] = self.content['templates']['skills'].pop(reference)
                for success in self.content['achievements']:
                    if success.get('target') == identifier and success['condition'] not in ('craft','quests'):
                        success['target'] = replacement
                for data in self.maps.values():
                    for spawn in data.get('spawners', []):
                        if spawn['mob_id'] == identifier:
                            spawn['mob_id'] = replacement
                for quest in self.content['quests']:
                    if quest['kind'] == 'kill' and quest['target'] == identifier:
                        quest['target'] = replacement
            elif section == 'npcs':
                if identifier in ('mira', 'forge'):
                    raise ValueError('Cet identifiant est une référence interne du tutoriel.')
                if any(site['id'] == replacement for data in self.maps.values() for site in data['sites']):
                    raise ValueError('Identifiant PNJ déjà utilisé.')
                for data in self.maps.values():
                    for site in data['sites']:
                        if site['id'] == identifier:
                            site['id'] = replacement
                for quest in self.content['quests']:
                    if quest['npc'] == identifier:
                        quest['npc'] = replacement
            elif section == 'maps':
                from .map_assembly import CORE
                if identifier in CORE:
                    raise ValueError('Cette carte est une référence interne du tutoriel.')
                if replacement in self.maps:
                    raise ValueError('Identifiant de carte déjà utilisé.')
                self.maps[replacement] = self.maps.pop(identifier)
                self.maps[replacement]['previous_ids'] = list(dict.fromkeys([*self.maps[replacement].get('previous_ids',[]),identifier]))
                self.maps[replacement]['id'] = 'field_'+replacement
                for data in self.maps.values():
                    points = data.get('world_view', {}).get('points', {})
                    if identifier in points:
                        points[replacement] = points.pop(identifier)
                    for key in ('zone_id', 'world_zone', 'fast_travel_origin'):
                        if data.get(key) == identifier:
                            data[key] = replacement
                    for gate in data['exits']:
                        for key in ('destination', 'fast_destination'):
                            if gate.get(key) == identifier:
                                gate[key] = replacement
                    for route in data.get('travel_routes', []):
                        for key in ('from', 'to'):
                            if route[key] == identifier:
                                route[key] = replacement
                for definition in [*self.content['quests'], *self.content['achievements']]:
                    for field in ('zone', 'map'):
                        if definition.get(field) == identifier:
                            definition[field] = replacement
            else:
                raise ValueError('Ce type de définition ne possède pas d’identifiant modifiable.')
            self.validate()
        except Exception:
            self.maps, self.mobs, self.content, self.encounters = before
            raise

    def duplicate(self, section, identifier, replacement):
        import re
        if section not in ('mobs','quests','achievements','classes','skills','skill_models'):
            raise ValueError('Ce catalogue se duplique depuis son éditeur spécialisé.')
        if not isinstance(replacement,str) or not re.fullmatch(r'[a-z0-9_]{1,64}',replacement):
            raise ValueError('Identifiant : lettres minuscules, chiffres et underscores.')
        before = self.state()
        try:
            if section == 'skill_models':
                key = 'ability:'+replacement
                if key in self.content['templates']['skills']:
                    raise ValueError('Identifiant déjà utilisé.')
                self.content['templates']['skills'][key] = deepcopy(self.content['templates']['skills'][identifier])
                self.content['templates']['skills'][key]['name'] += ' · copie'
            elif section == 'mobs':
                if replacement in self.mobs:
                    raise ValueError('Identifiant déjà utilisé.')
                value = deepcopy(self.mobs[identifier])
                value['name'] += ' · copie'
                value.pop('previous_ids',None)
                self.mobs[replacement] = value
            else:
                values = self.content['templates']['classes'] if section == 'classes' else self.content.setdefault(section,[])
                if any(item['id'].lower() == replacement.lower() or replacement in item.get('previous_ids',[]) for item in values):
                    raise ValueError('Identifiant déjà utilisé.')
                value = deepcopy(next(item for item in values if item['id'] == identifier))
                value.update(id=replacement,name=value['name']+' · copie')
                for key in ('previous_ids','table_id','role'):
                    value.pop(key,None)
                if section == 'quests' and is_hunt(value):
                    value.pop('role',None)
                values.append(value)
            self.validate()
        except Exception:
            self.maps, self.mobs, self.content, self.encounters = before
            raise

    def save(self):
        self.validate()
        payloads = {'world.json': self.maps, 'encounters.json': {'kind': 'encounters', 'maps': self.encounters}, 'mobs.json': {'kind': 'mobs', 'maps': self.mobs}, 'content.json': {'kind': 'content', 'maps': {}, 'content': {key:value for key,value in self.content.items() if key != 'templates'}}, 'classes.json':self.content['templates']}
        originals, staged, replaced = {}, {}, []
        try:
            for name, value in payloads.items():
                target = self.directory/name
                originals[name] = target.read_bytes() if target.exists() else None
                temporary = self.directory/(name+'.controller.tmp')
                temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
                staged[name] = temporary
            for name, temporary in staged.items():
                os.replace(temporary, self.directory/name)
                replaced.append(name)
        except Exception:
            for name in replaced:
                if originals[name] is None:
                    (self.directory/name).unlink(missing_ok=True)
                else:
                    (self.directory/name).write_bytes(originals[name])
            raise
        finally:
            for temporary in staged.values():
                temporary.unlink(missing_ok=True)
        self.snapshot = self.state()


