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


def parse_field(key, value, initial):
    if type(initial) is bool:
        return value == 'Oui'
    if key in DECIMAL_FIELDS or key.endswith(('_base','_growth')) or type(initial) is float:
        return float(value.strip().replace(',','.'))
    if type(initial) is int:
        return int(value)
    return value


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


class Controller:
    def __init__(self, root, project):
        import tkinter as tk
        from tkinter import ttk, messagebox, simpledialog
        self.tk, self.ttk, self.messagebox, self.simpledialog = tk, ttk, messagebox, simpledialog
        self.root, self.project = root, project
        self.history = []
        self.future = []
        self.filters = {}
        root.title('RPG — Contrôleur du projet')
        root.geometry('1120x780')
        root.protocol('WM_DELETE_WINDOW', self.close)
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill='x')
        for name, action in [('Builder', self.builder), ('Projet complet (JSON)', self.edit_project_document), ('Valider', self.validate), ('Enregistrer le projet', self.save), ('Annuler modification', self.undo), ('Rétablir', self.redo)]:
            ttk.Button(bar, text=name, command=action).pack(side='left', padx=4)
        self.status = tk.StringVar(value=f'{project.directory} · Modifiez puis enregistrez. Redémarrez le serveur pour appliquer.')
        ttk.Label(root, textvariable=self.status, wraplength=1080).pack(fill='x', padx=8)
        notebook = ttk.Notebook(root)
        notebook.pack(fill='both', expand=True, padx=8, pady=8)
        self.tables = {}
        for section, title in [('maps', 'Cartes / zones'), ('quests', 'Quêtes'), ('mobs', 'Mobs'), ('achievements', 'Succès et titres'), ('npcs', 'PNJ'), ('world', 'Monde'), ('classes','Classes / modèles'), ('skills','Compétences simples'), ('skill_models','Compétences moteur')]:
            page = ttk.Frame(notebook, padding=8)
            notebook.add(page, text=title)
            search = ttk.Frame(page)
            search.pack(fill='x', pady=(0,8))
            ttk.Label(search, text='Rechercher').pack(side='left')
            self.filters[section] = tk.StringVar()
            ttk.Entry(search, textvariable=self.filters[section]).pack(side='left', fill='x', expand=True, padx=8)
            self.filters[section].trace_add('write', lambda *args: self.refresh())
            table_frame = ttk.Frame(page)
            table_frame.pack(fill='both', expand=True)
            table = ttk.Treeview(table_frame, columns=('name', 'details'), show='tree headings', selectmode='browse')
            table.heading('#0', text='Identifiant')
            table.heading('name', text='Nom')
            table.heading('details', text='Détails')
            table.column('#0', width=190)
            table.column('name', width=240)
            table.column('details', width=540)
            table.pack(side='left', fill='both', expand=True)
            scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=table.yview)
            scrollbar.pack(side='left', fill='y')
            table.configure(yscrollcommand=scrollbar.set)
            table.bind('<Double-1>', lambda e, s=section: self.edit(s))
            self.tables[section] = table
            actions = ttk.Frame(page)
            actions.pack(fill='x', pady=8)
            for label, action in [('Modifier', lambda s=section:self.edit(s))] + ([] if section == 'world' else [('Ajouter', lambda s=section:self.edit(s, True)), ('Supprimer', lambda s=section:self.delete(s))]):
                ttk.Button(actions, text=label, command=action).pack(side='left', padx=4)
            ttk.Button(actions, text='Aperçu / références', command=lambda s=section:self.inspect(s)).pack(side='left', padx=4)
            if section not in ('world','maps','npcs'):
                ttk.Button(actions, text='Dupliquer', command=lambda s=section:self.duplicate(s)).pack(side='left', padx=4)
            if section != 'world':
                ttk.Button(actions, text='Renommer identifiant', command=lambda s=section:self.rename(s)).pack(side='left', padx=4)
            if section == 'mobs':
                ttk.Button(actions, text='Créer une sous-espèce', command=self.subspecies).pack(side='left', padx=4)
            if section == 'maps':
                ttk.Button(actions, text='Éditer la carte dans le builder', command=self.builder).pack(side='left')
            if section == 'world':
                ttk.Label(page, text='Trajets, rues, raccords et placements : bouton Builder → Assemblage / Trajets et rues.\nLe ratio de temps reste 1:3 ; les déplacements à pied restent à 6 km/h.').pack(anchor='w')
        self.refresh()

    def remember(self, state=None):
        self.future = []
        self.history.append(self.project.state() if state is None else state)
        self.history = self.history[-30:]

    def undo(self):
        if self.history:
            self.future.append(self.project.state())
            self.project.maps, self.project.mobs, self.project.content, self.project.encounters = self.history.pop()
            self.refresh()

    def redo(self):
        if self.future:
            self.history.append(self.project.state())
            self.project.maps, self.project.mobs, self.project.content, self.project.encounters = self.future.pop()
            self.refresh()

    def inspect(self, section):
        from .controller_tools import preview, references
        selected = self.tables[section].selection()
        if not selected:
            return
        level = player_level = 1
        if section in ('mobs','classes'):
            level = self.simpledialog.askinteger('Aperçu', 'Niveau à simuler (1–100)', initialvalue=1, minvalue=1, maxvalue=100, parent=self.root)
            if level is None:
                return
        if section == 'mobs':
            player_level = self.simpledialog.askinteger('Récompense XP', 'Niveau du joueur (1–100)', initialvalue=level, minvalue=1, maxvalue=100, parent=self.root)
            if player_level is None:
                return
        try:
            self.show_report('Aperçu et références', {'aperçu':preview(self.project,section,selected[0],level,player_level),'utilisé_par':references(self.project,section,selected[0])})
        except (ValueError,KeyError,TypeError) as exc:
            self.messagebox.showerror('Aperçu',str(exc),parent=self.root)

    def show_report(self, title, value):
        from .controller_tools import text
        window = self.tk.Toplevel(self.root)
        window.title(title)
        window.geometry('900x650')
        frame = self.ttk.Frame(window)
        frame.pack(fill='both',expand=True)
        area = self.tk.Text(frame,wrap='word')
        scrollbar = self.ttk.Scrollbar(frame,orient='vertical',command=area.yview)
        area.configure(yscrollcommand=scrollbar.set)
        area.pack(side='left',fill='both',expand=True)
        scrollbar.pack(side='right',fill='y')
        area.insert('1.0',text(value))
        area.configure(state='disabled')
        self.ttk.Button(window,text='Fermer',command=window.destroy).pack(pady=8)
        window.transient(self.root)

    def edit_project_document(self):
        window = self.tk.Toplevel(self.root)
        window.title('Projet complet — JSON')
        window.geometry('1100x760')
        frame = self.ttk.Frame(window, padding=8)
        frame.pack(fill='both', expand=True)
        area = self.tk.Text(frame, wrap='none', undo=True)
        yscroll = self.ttk.Scrollbar(frame, orient='vertical', command=area.yview)
        xscroll = self.ttk.Scrollbar(frame, orient='horizontal', command=area.xview)
        area.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        area.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        area.insert('1.0', json.dumps(self.project.document(), ensure_ascii=False, indent=2))
        actions = self.ttk.Frame(window, padding=8)
        actions.pack(fill='x')
        def apply():
            before = self.project.state()
            try:
                value = json.loads(area.get('1.0', 'end-1c'))
                self.project.replace_document(value)
                self.remember(before)
                self.refresh()
                self.status.set('Projet complet validé en mémoire. Enregistrez pour le conserver.')
                window.destroy()
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                self.messagebox.showerror('Projet complet', str(exc), parent=window)
        self.ttk.Button(actions, text='Appliquer et valider', command=apply).pack(side='left', padx=4)
        self.ttk.Button(actions, text='Annuler', command=window.destroy).pack(side='left', padx=4)
        window.transient(self.root)

    def duplicate(self, section):
        selected = self.tables[section].selection()
        if not selected:
            return
        identifier = self.simpledialog.askstring('Dupliquer', 'Identifiant de la copie', parent=self.root)
        if not identifier:
            return
        before = self.project.state()
        try:
            self.project.duplicate(section,selected[0],identifier)
            self.remember(before)
            self.filters[section].set('')
            self.refresh()
            self.tables[section].selection_set('ability:'+identifier if section == 'skill_models' else identifier)
            self.status.set('Copie indépendante créée. Enregistrez pour la conserver.')
        except (ValueError,KeyError,TypeError) as exc:
            self.messagebox.showerror('Duplication',str(exc),parent=self.root)

    def refresh(self):
        p = self.project
        from .controller_tools import catalog_rows, filter_rows
        for section, table in self.tables.items():
            selected = table.selection()
            query = self.filters[section].get() if hasattr(self, 'filters') else ''
            table.delete(*table.get_children())
            for key, name, details in filter_rows(catalog_rows(p, section), query):
                table.insert('', 'end', iid=key, text=key, values=(name, details))
            for key in selected:
                if table.exists(key):
                    table.selection_set(key)

    def label(self, key):
        if key.endswith('_base'):
            return key[:-5]+' · valeur au niveau 1'
        if key.endswith('_growth') and key != 'damage_growth':
            return key[:-7]+' · croissance par niveau'
        return {'id':'Identifiant', 'name':'Nom', 'npc':'PNJ donneur', 'kind':'Type d’objectif', 'target':'Espèce / recette cible', 'zone':'Zone requise (vide = toutes)', 'count':'Nombre requis', 'reward_xp':'Récompense XP par joueur', 'description':'Description', 'condition':'Condition', 'threshold':'Seuil', 'title':'Titre obtenu', 'class_name':'Classe de base', 'rank':'Rang', 'damage':'Dégâts', 'dialogue':'Dialogue', 'owner':'Joueur lié (vide = fixe)', 'map_id':'Carte', 'width':'Largeur', 'height':'Hauteur', 'zone_level':'Niveau de zone', 'biome':'Ambiance', 'repop_seconds':'Repop après absence (secondes en jeu)', 'mob_xp':'XP par mob', 'xp_base':'Base XP nécessaire', 'xp_exponent':'Exposant de progression XP', 'merchant_stay_hours':'Séjour du marchand (heures en jeu)', 'player_vision':'Vision joueur (cases)', 'xp_class':'Classe de récompense XP', 'xp_multiplier':'Multiplicateur XP', 'damage_growth':'Dégâts ajoutés par niveau', 'parent':'Espèce parente', 'item':'Matériau', 'chance':'Probabilité (0–1)', 'attempts':'Nombre de tirages indépendants', 'min':'Quantité minimale par réussite', 'max':'Quantité maximale par réussite', 'rare':'Matériau rare', 'power':'Puissance de base', 'growth':'Puissance par niveau', 'cooldown':'Cooldown (secondes réelles)', 'cast':'Incantation (secondes réelles)', 'range':'Portée (cases)', 'duration':'Durée du stun (secondes réelles)', 'level':'Niveau de déblocage', 'concentration':'Interrompue par les dégâts', 'type':'Effet', 'base_class':'Modèle de classe humaine', 'energy_capacity':'Capacité des énergies ajoutées', 'skill_id':'Compétence existante', 'cost':'Coût d’énergie'}.get(key, key)

    def form(self, title, values, choices=None):
        window = self.tk.Toplevel(self.root)
        window.title(title)
        fields = {}
        labels = {}
        choices = choices or {}
        for row, (key, value) in enumerate(values.items()):
            labels[key] = self.ttk.Label(window, text=(self.label(key)+' (−1 : automatique)' if title in ('Compétences universelles','Compétence moteur') and key in ('range','cost') else self.label(key)))
            labels[key].grid(row=row, column=0, padx=8, pady=5, sticky='w')
            if type(value) is bool:
                choices[key] = ['Oui','Non']
            widget = self.ttk.Combobox(window, values=choices[key], state='readonly', width=55) if key in choices else self.ttk.Entry(window, width=58)
            if key in choices:
                widget.set('Oui' if value is True else 'Non' if value is False else value)
            else:
                widget.insert(0, str(value))
            widget.grid(row=row, column=1, padx=8, pady=5)
            fields[key] = widget
        def condition_changed(event=None):
            condition = fields['condition'].get()
            if 'target' in fields:
                from .forge import RECIPES
                targets = [''] + (list(RECIPES) if condition == 'craft' else [item['id'] for item in self.project.content['quests']] if condition == 'quests' else list(self.project.mobs))
                fields['target'].configure(values=targets)
                if fields['target'].get() not in targets or condition in ('level','discover'):
                    fields['target'].set('')
                for widget in (labels['target'], fields['target']):
                    widget.grid_remove() if condition in ('level','discover') else widget.grid()
                for key in ('zone','map'):
                    for widget in (labels[key], fields[key]):
                        widget.grid_remove() if condition == 'level' else widget.grid()
                    if condition == 'level':
                        fields[key].set('')
            labels['threshold'].configure(text='Temps maximum (secondes réelles)' if condition == 'fast' else 'Différence de niveau minimale' if condition == 'higher' else 'Niveau requis' if condition == 'level' else 'Nombre requis')
        if 'condition' in fields and 'threshold' in fields:
            fields['condition'].bind('<<ComboboxSelected>>', condition_changed)
            condition_changed()
        def kind_changed(event=None):
            from .forge import RECIPES
            targets = list(self.project.mobs) if fields['kind'].get() == 'kill' else list(RECIPES)
            fields['target'].configure(values=targets)
            if fields['target'].get() not in targets:
                fields['target'].set(targets[0] if targets else '')
        if 'kind' in fields and 'target' in fields:
            fields['kind'].bind('<<ComboboxSelected>>', kind_changed)
            kind_changed()
        result = []
        def accept():
            try:
                parsed = {key: parse_field(key, widget.get(), values[key]) for key, widget in fields.items()}
                if 'condition' in parsed and parsed['condition'] != 'fast':
                    if parsed['threshold'] != int(parsed['threshold']):
                        raise ValueError('Seuil entier requis.')
                    parsed['threshold'] = int(parsed['threshold'])
                result.append(parsed)
                window.destroy()
            except ValueError:
                self.messagebox.showerror('Valeur', 'Les champs numériques doivent contenir un nombre.', parent=window)
        self.ttk.Button(window, text='Appliquer', command=accept).grid(row=len(values), column=0, pady=10)
        self.ttk.Button(window, text='Annuler', command=window.destroy).grid(row=len(values), column=1)
        window.transient(self.root)
        window.grab_set()
        self.root.wait_window(window)
        return result[0] if result else None

    def edit(self, section, new=False):
        selected = self.tables[section].selection()
        if not new and not selected:
            return
        key = selected[0] if selected else None
        p = self.project
        before = p.state()
        try:
            if section == 'maps':
                self.builder(new=new)
                return
            if section == 'world':
                values = self.form('Paramètres du monde', p.content['world'])
                if values:
                    p.content['world'] = values
            elif section == 'skill_models':
                values = self.edit_skill_model(key,new)
                if values is None:
                    return
                identifier = values.pop('id')
                if new and identifier in p.content['templates']['skills']:
                    raise ValueError('Identifiant déjà utilisé.')
                if not new and identifier != key:
                    raise ValueError('Utilisez Renommer identifiant pour changer la référence.')
                p.content['templates']['skills'][identifier] = values
            elif section == 'classes' and (new or any(item['id'] == key for item in p.content['templates']['classes'])):
                values = self.edit_template(key,new)
                if values is None:
                    return
                if new and any(item['id'].lower() == values['id'].lower() for item in p.content['templates']['classes']):
                    raise ValueError('Identifiant déjà utilisé.')
                if not new and values['id'] != key:
                    p.rename('classes',key,values['id'])
                p.content['templates']['classes'] = [item for item in p.content['templates']['classes'] if item['id'] not in (key,values['id'])] + [values]
            elif section in ('classes','skills'):
                from .skill_catalog import BASE_CLASSES, library
                available = library(p.content,p.mobs)
                if section == 'classes':
                    old = next(item for item in p.content.get('classes',[]) if item['id'] == key)
                    values = self.form('Classe humaine',{k:v for k,v in old.items() if k not in ('stats','skills','previous_ids')},{'base_class':BASE_CLASSES})
                    if not values:
                        return
                    stats = self.edit_stats({'class_name':values['base_class'],'name':values['name'],'stats':old.get('stats',{})})
                    if stats is None:
                        return
                    assigned = self.edit_records('Compétences de classe',old.get('skills',[]),{'skill_id':next(iter(available)),'level':1,'range':6.0,'cost':5},{'skill_id':list(available)})
                    if assigned is None:
                        return
                    values.update(stats=stats,skills=assigned)
                else:
                    old = {'id':'','name':'Nouvelle compétence','type':'damage','level':1,'power':3.0,'growth':.5,'cooldown':5.0,'cast':.6,'range':1.5,'duration':2.0,'concentration':True} if new else next(item for item in p.content.get('skills',[]) if item['id'] == key)
                    values = self.form('Compétence réutilisable',old,{'type':['damage','heal','stun']})
                    if not values:
                        return
                if new and any(item['id'].lower() == values['id'].lower() for item in p.content['templates']['classes']):
                    raise ValueError('Identifiant déjà utilisé.')
                if not new and values['id'] != key:
                    p.rename(section,key,values['id'])
                elif new and any(item['id'] == values['id'] for item in p.content.get(section,[])):
                    raise ValueError('Identifiant déjà utilisé.')
                if section == 'classes' and not new:
                    current = next(item for item in p.content[section] if item['id'] == values['id'])
                    if current.get('previous_ids'):
                        values['previous_ids'] = current['previous_ids']
                p.content[section] = [item for item in p.content.get(section,[]) if item['id'] != values['id']] + [values]
            elif section == 'mobs':
                from . import forge
                old = resolve(p.mobs, key) if not new else {'name':'Nouvelle créature','class_name':next(item['id'] for item in p.content['templates']['classes'] if not item['playable'] and item['class_type'] != 'INVOCATION'),'rank':'D','damage':3,'loot':{'peau':1}}
                public = {'id':key or '', 'name':old['name'], 'class_name':old['class_name'], 'rank':old['rank'], 'damage':old['damage'], 'damage_growth':float(old.get('damage_growth',.5)), 'xp_class':old.get('xp_class', 'normal'), 'xp_multiplier':float(old.get('xp_multiplier',1)), 'parent':p.mobs[key].get('parent','') if not new else ''}
                values = self.form('Espèce / sous-espèce', public, {'class_name':[item['id'] for item in p.content['templates']['classes'] if item['class_type'] != 'INVOCATION'], 'rank':RANKS, 'xp_class':list(CLASS_XP), 'parent':['', *p.mobs]})
                if not values:
                    return
                stats = self.edit_stats(old)
                if stats is None:
                    return
                drops = self.edit_records('Drops', drop_rules(old, forge.RARE_DROPS), {'item':'peau','chance':1.0,'attempts':1,'min':1,'max':1,'rare':False})
                if drops is None:
                    return
                abilities = self.edit_records('Capacités', old.get('abilities',[]), {'name':'Frappe','type':'damage','level':1,'power':3.0,'growth':0.5,'cooldown':5.0,'cast':0.6,'range':1.5,'duration':2.0,'concentration':True}, {'type':['damage','heal','stun']})
                if abilities is None:
                    return
                identifier = values.pop('id')
                if identifier != key and identifier in p.mobs:
                    raise ValueError('Identifiant déjà utilisé.')
                if not new and identifier != key:
                    p.rename('mobs', key, identifier)
                if not values['parent']:
                    values.pop('parent')
                history = p.mobs.get(identifier,{}).get('previous_ids',[]) if not new else []
                p.mobs[identifier] = {**({'previous_ids':history} if history else {}), **values, 'stats':stats, 'drops':drops, 'loot':{}, 'abilities':abilities}
            elif section in ('quests', 'achievements'):
                default = {'id':'', 'name':'Nouvelle quête', 'npc':'mira', 'kind':'kill', 'target':'goblin', 'zone':'', 'map':'', 'count':1, 'reward_xp':50, 'description':'Objectif de quête'} if section == 'quests' else {'id':'', 'name':'Nouveau succès', 'condition':'kills', 'threshold':1, 'title':'Nouveau titre', 'target':'', 'zone':'', 'map':''}
                old = default if new else next(item for item in p.content[section] if item['id'] == key)
                choices = {'npc':sorted({site['id'] for data in p.maps.values() for site in data['sites']}), 'kind':['kill','craft'], 'target':list(p.mobs), 'zone':['', *p.maps], 'condition':CONDITIONS}
                if section == 'achievements':
                    old = {'target':'','zone':'','map':'',**old}
                else:
                    old = {'map':'',**old}
                choices['zone'] = ['', *p.maps] if section == 'quests' else ['', *sorted({zone_of(p.maps, identifier) for identifier in p.maps})]
                choices['map'] = ['', *p.maps]
                values = self.form('Quête' if section == 'quests' else 'Succès et titre', {k:v for k,v in old.items() if k not in ('role', 'previous_ids', 'requirements')}, choices)
                if values:
                    if section == 'quests':
                        requirements = self.edit_requirements(old.get('requirements',{}))
                        if requirements is None:
                            return
                        values['requirements'] = requirements
                    if not new and values['id'] != key:
                        p.rename(section, key, values['id'])
                    metadata = next((item for item in p.content[section] if item['id'] == values['id']), {}) if not new else {}
                    values.update({k:v for k,v in metadata.items() if k in ('role', 'previous_ids')})
                    p.content[section] = [item for item in p.content[section] if item['id'] != (values['id'] if not new else None)] + [values]
            else:
                map_id, index = key.rsplit(':',1) if key else (next(iter(p.maps)), None)
                old = {'id':'', 'name':'Nouveau PNJ', 'dialogue':'Bonjour !', 'owner':''} if new else {k:v for k,v in p.maps[map_id]['sites'][int(index)].items() if k != 'position'}
                values = self.form('PNJ', {'map_id':map_id, **old}, {'map_id':list(p.maps)})
                if not values:
                    return
                from .map_objects import pick_cell
                destination = values.pop('map_id')
                chosen = pick_cell(SimpleNamespace(root=self.root, maps=p.maps, selected=SimpleNamespace(get=lambda:destination)), 'Placer le PNJ', destination)
                if not chosen:
                    return
                if not new:
                    previous_id = p.maps[map_id]['sites'][int(index)]['id']
                    if values['id'] != previous_id:
                        p.rename('npcs', previous_id, values['id'])
                    p.maps[map_id]['sites'].pop(int(index))
                p.maps[destination]['sites'].append({**values, 'position':chosen[1]})
            p.validate()
            if p.state() != before:
                self.remember(before)
                self.status.set('Modification appliquée en mémoire. Enregistrez le projet pour la conserver.')
            self.refresh()
        except (ValueError, KeyError, TypeError) as exc:
            p.maps, p.mobs, p.content = before
            self.messagebox.showerror('Modification refusée', str(exc), parent=self.root)

    def rename(self, section):
        selected = self.tables[section].selection()
        if not selected:
            return
        key = selected[0]
        if section == 'npcs':
            map_id, index = key.rsplit(':', 1)
            key = self.project.maps[map_id]['sites'][int(index)]['id']
        replacement = self.simpledialog.askstring('Renommer identifiant', 'Nouvel identifiant (ex. mira_hunt_2)', initialvalue=key, parent=self.root)
        if not replacement or replacement == key:
            return
        before = self.project.state()
        try:
            self.project.rename(section, key, replacement)
            self.remember(before)
            self.refresh()
            self.status.set('Identifiant renommé, références mises à jour. Enregistrez puis redémarrez le serveur.')
        except (ValueError, KeyError) as exc:
            self.messagebox.showerror('Renommage refusé', str(exc), parent=self.root)

    def subspecies(self):
        selected = self.tables['mobs'].selection()
        if not selected:
            return
        parent = selected[0]
        identifier = self.simpledialog.askstring('Sous-espèce', 'Nouvel identifiant', parent=self.root)
        if not identifier:
            return
        before = self.project.state()
        try:
            if identifier in self.project.mobs:
                raise ValueError('Identifiant déjà utilisé.')
            self.project.mobs[identifier] = {'parent':parent, 'name':resolve(self.project.mobs,parent)['name']+' · sous-espèce'}
            self.project.validate()
            self.remember(before)
            self.refresh()
            self.tables['mobs'].selection_set(identifier)
            self.edit('mobs')
        except ValueError as exc:
            self.project.maps, self.project.mobs, self.project.content, self.project.encounters = before
            self.messagebox.showerror('Sous-espèce', str(exc), parent=self.root)

    def edit_skill_model(self,key,new):
        from jeuxRPG._class.res.classType import SkillType, DamageType
        from jeuxRPG._class.res.character.alteration.alteration import AlterationType
        from jeuxRPG._class.res.character.class_models import skill_from_data
        from .progression import casting
        models = self.project.content['templates']
        if new:
            choice = self.form('Copier une compétence moteur',{'source':next(iter(models['skills']))},{'source':list(models['skills'])})
            if not choice:
                return None
            result = deepcopy(models['skills'][choice['source']])
            identifier = 'ability:'
        else:
            result = deepcopy(models['skills'][key])
            identifier = key
        values = self.form('Compétence moteur',{'id':identifier,**{field:result[field] for field in ('name','type','energy','cost','cooldown','requires_target','can_target_others','handler')},'damage_type':result.get('damage_type') or '', 'description':result.get('description',''), 'range':result.get('range',-1.0)},{'type':list(SkillType.__members__),'damage_type':['',*DamageType.__members__],'energy':['Mana','Aura','Foie'],'handler':['default','damage_stun']})
        if not values:
            return None
        import re
        if new and not re.fullmatch(r'ability:[a-z0-9_]{1,64}',values['id']):
            raise ValueError('Nouvelle référence : ability:identifiant (lettres minuscules, chiffres, underscores).')
        result.update(values)
        result['damage_type'] = result['damage_type'] or None
        if result['range'] == -1:
            result.pop('range')
        timing = self.form('Incantation',casting(skill_from_data(result)))
        if timing is None:
            return None
        result['casting'] = timing
        balance = self.form('Coûts et scaling', {**result['balance'],'cost_fixed':result['balance'].get('cost_fixed') if result['balance'].get('cost_fixed') is not None else -1})
        if balance is None:
            return None
        balance['cost_fixed'] = None if balance['cost_fixed'] == -1 else balance['cost_fixed']
        result['balance'] = balance
        rows = [{'key':name,'name':effect.get('name') or '', 'value':float(effect['value']) if effect['value'] is not None else -1.0,'duration':float(effect['duration']),'stat_target':str(effect['stat_target']) if effect['stat_target'] is not None else '', 'alteration':effect['alteration'] or '', 'invocation_class':(effect.get('invocation') or {}).get('class',''),'invocation_level':(effect.get('invocation') or {}).get('level','BL')} for name,effect in result['effects'].items()]
        choices = {'stat_target':['','0','HP','Force','Endurance','Intelligence','Sagesse'],'alteration':['',*AlterationType.__members__],'invocation_class':['',*[model['id'] for model in models['classes'] if model['class_type'] == 'INVOCATION']]}
        effects = self.edit_records('Effets : valeur −1 = aucune valeur',rows,{'key':'damage','name':'','value':1.0,'duration':0.0,'stat_target':'','alteration':'','invocation_class':'','invocation_level':'BL'},choices)
        if effects is None:
            return None
        if len({entry['key'] for entry in effects}) != len(effects):
            raise ValueError('Les clés d’effets doivent être uniques.')
        result['effects'] = {entry['key']:{'name':None if not entry['name'] and result['effects'].get(entry['key'],{}).get('name') is None else entry['name'],'value':None if entry['value'] == -1 else entry['value'],'duration':entry['duration'],'stat_target':0 if entry['stat_target'] == '0' else entry['stat_target'] or None,'alteration':entry['alteration'] or None,'invocation':{**(result['effects'].get(entry['key'],{}).get('invocation') or {}),'class':entry['invocation_class'],'level':entry['invocation_level']} if entry['invocation_class'] else None} for entry in effects}
        return result

    def edit_template(self,key,new):
        from jeuxRPG._class.res.character.class_models import MODELS, STAT_NAMES, ENERGY_NAMES
        from jeuxRPG._class.res.classType import ClassType
        models = deepcopy(self.project.content['templates'])
        if new:
            choice = self.form('Créer une classe : copier une définition',{'template':next(item['id'] for item in models['classes'])},{'template':[item['id'] for item in models['classes']]})
            if not choice:
                return None
            result = deepcopy(next(item for item in models['classes'] if item['id'] == choice['template']))
            result.update(id='',name='Nouvelle classe')
            result.pop('previous_ids',None)
            result.pop('table_id',None)
        else:
            result = deepcopy(next(item for item in models['classes'] if item['id'] == key))
        values = self.form('Classe universelle',{'id':result['id'],'name':result['name'],'playable':result['playable'],'class_type':result['class_type']},{'class_type':list(ClassType.__members__)})
        if not values:
            return None
        result.update(values)
        stats = self.form('Statistiques initiales',result['base_stats'])
        if stats is None:
            return None
        result['base_stats'] = stats
        energies = self.edit_records('Énergies de classe',result['energies'],{'type':'Mana','value':30,'regen_rate':.3},{'type':ENERGY_NAMES})
        if energies is None:
            return None
        result['energies'] = energies
        growth = self.edit_growth(result['growth'])
        if growth is None:
            return None
        result['growth'] = growth
        from .skill_catalog import library, make_skill
        from jeuxRPG._class.res.character.class_models import skill_to_data
        for identifier,entry in library(self.project.content,self.project.mobs).items():
            if identifier not in models['skills']:
                models['skills'][identifier] = skill_to_data(make_skill(entry,{}))
        invocation = result['class_type'] == 'INVOCATION'
        rows = [{**entry,'level':entry['level'] if invocation and not entry['level'].startswith('level ') else 'BL' if invocation else int(entry['level'].split()[1]) if entry['level'].startswith('level ') else 1,'range':entry.get('range',-1.0),'cost':entry.get('cost',-1)} for entry in result['skills']]
        skills = self.edit_records('Compétences universelles',rows,{'skill_id':next(iter(models['skills'])),'level':'BL' if invocation else 1,'range':-1.0,'cost':-1},{'skill_id':list(models['skills'])})
        if skills is None:
            return None
        result['skills'] = [{**{key:value for key,value in entry.items() if key not in ('level','range','cost') or key in ('range','cost') and value != -1},'level':str(entry['level']) if invocation else 'level '+str(entry['level'])} for entry in skills]
        from jeuxRPG._class.res.character.class_models import skill_from_data
        energy_names = {entry['type'] for entry in result['energies']}
        for assignment in result['skills']:
            skill = skill_from_data(models['skills'][assignment['skill_id']])
            name = skill.energie_target.__name__
            level = 1 if invocation else int(assignment['level'].split()[1])
            available = name in energy_names or any(entry['level'] <= level and name in entry.get('unlock_energies',{}) for entry in result['growth'])
            if not available:
                result['energies'].append({'type':name,'value':max(30,skill.energie_cost),'regen_rate':.3})
                energy_names.add(name)
                for entry in result['growth']:
                    entry.get('unlock_energies',{}).pop(name,None)
        if result.get('formulas'):
            initial = {field:float(value) for stat,formula in result['formulas'].items() for field,value in [(stat+'_base',result['base_stats'][stat]),(stat+'_growth',formula['growth'])]}
            formulas = self.form('Formules de progression héritées',initial)
            if formulas is None:
                return None
            result['formulas'] = {stat:{'base':formulas[stat+'_base'],'growth':formulas[stat+'_growth']} for stat in result['formulas']}
        combat = self.form('Profil de combat',result['combat'],{'attack_stat':STAT_NAMES})
        if combat is None:
            return None
        result['combat'] = combat
        affinities = self.form('Affinités : types de dégâts séparés par des virgules',{'weaknesses':', '.join(result['weaknesses']),'resistances':', '.join(result['resistances'])})
        if affinities is None:
            return None
        result.update({key:[value.strip().upper() for value in text.split(',') if value.strip()] for key,text in affinities.items()})
        if not new and result['id'] != key:
            result['previous_ids'] = list(dict.fromkeys([*result.get('previous_ids',[]),key]))
        self.project.content['templates']['skills'].update({entry['skill_id']:models['skills'][entry['skill_id']] for entry in result['skills'] if entry['skill_id'] not in self.project.content['templates']['skills']})
        return result

    def edit_growth(self,initial):
        names = ('HP','Force','Endurance','Intelligence','Sagesse')
        energies = ('Mana','Aura','Foie')
        rows = []
        for entry in initial:
            rows.append({'level':entry['level'],**{name:entry.get('stats',{}).get(name,0) for name in names},**{'energy_'+name:entry.get('energies',{}).get(name,0) for name in energies},**{'unlock_'+name:entry.get('unlock_energies',{}).get(name,0) for name in energies}})
        default = {'level':1,**{name:0 for name in names},**{'energy_'+name:0 for name in energies},**{'unlock_'+name:0 for name in energies}}
        values = self.edit_records('Paliers cumulés de progression',rows,default)
        if values is None:
            return None
        return [{'level':entry['level'],'stats':{name:entry[name] for name in names if entry[name]},'energies':{name:entry['energy_'+name] for name in energies if entry['energy_'+name]},'unlock_energies':{name:entry['unlock_'+name] for name in energies if entry['unlock_'+name]}} for entry in values]

    def edit_requirements(self, initial):
        window = self.tk.Toplevel(self.root)
        window.title('Prérequis de quête : toutes les conditions sont requises')
        self.ttk.Label(window,text='Niveau minimum de chaque joueur du groupe').pack(padx=10,pady=5)
        level = self.ttk.Entry(window)
        level.insert(0,str(initial.get('level',1)))
        level.pack(padx=10,pady=5)
        boxes = {}
        for key, title in [('achievements','Succès obtenus'),('quests','Quêtes terminées')]:
            self.ttk.Label(window,text=title+' · sélection multiple').pack(padx=10,pady=5)
            box = self.tk.Listbox(window,selectmode='multiple',exportselection=False,width=65,height=8)
            definitions = self.project.content[key]
            for index, definition in enumerate(definitions):
                box.insert('end',definition['name']+' · '+definition['id'])
                if definition['id'] in initial.get(key,[]):
                    box.selection_set(index)
            box.pack(fill='both',expand=True,padx=10,pady=5)
            boxes[key] = (box,definitions)
        result = []
        def accept():
            try:
                minimum = int(level.get())
                if not 1 <= minimum <= 100:
                    raise ValueError()
                result.append({'level':minimum, **{key:[definitions[index]['id'] for index in box.curselection()] for key,(box,definitions) in boxes.items()}})
                window.destroy()
            except ValueError:
                self.messagebox.showerror('Prérequis','Niveau entier entre 1 et 100 requis.',parent=window)
        self.ttk.Button(window,text='Appliquer',command=accept).pack(pady=5)
        self.ttk.Button(window,text='Annuler',command=window.destroy).pack(pady=5)
        window.transient(self.root)
        window.grab_set()
        self.root.wait_window(window)
        return result[0] if result else None

    def edit_stats(self, definition):
        from jeuxRPG._class.character import Character
        actor = Character.create(definition['class_name'],'controller',definition['name'])
        bases = {stat:getattr(actor,stat).value for stat in STATS}
        actor.gain_exp(actor._required_exp_for_next_level()-actor.exp)
        values = {}
        for stat in STATS:
            current = definition.get('stats',{}).get(stat, {'base':bases[stat],'growth':getattr(actor,stat).value-bases[stat]})
            values[stat+'_base'] = float(current['base'])
            values[stat+'_growth'] = float(current['growth'])
        result = self.form('Stats : base + croissance × (niveau − 1)', values)
        return {stat:{'base':result[stat+'_base'],'growth':result[stat+'_growth']} for stat in STATS} if result else None

    def edit_records(self, title, initial, default, choices=None):
        window = self.tk.Toplevel(self.root)
        window.title(title)
        rows = deepcopy(initial)
        table = self.ttk.Treeview(window, columns=('details',), show='tree headings', height=12)
        table.heading('#0', text='Définition')
        table.heading('details', text='Paramètres')
        table.column('details', width=650)
        table.pack(fill='both',expand=True,padx=8,pady=8)
        def refresh():
            table.delete(*table.get_children())
            for index, item in enumerate(rows):
                table.insert('', 'end', iid=str(index), text=item.get('name',item.get('item',item.get('skill_id',''))), values=(str(item),))
        def edit(new=False):
            selected = table.selection()
            if not new and not selected:
                return
            index = int(selected[0]) if selected else None
            existing = {} if new else rows[index]
            if title == 'Capacités' and 'skill_id' in existing:
                from .skill_catalog import library
                value = self.form('Réutiliser une compétence',existing,{'skill_id':list(library(self.project.content,self.project.mobs))})
            else:
                value = self.form(title, {**default, **existing}, choices)
            if value:
                rows.append(value) if new else rows.__setitem__(index,value)
                refresh()
        def reuse():
            from .skill_catalog import library, make_skill
            from jeuxRPG._class.res.classType import SkillType
            available = library(self.project.content,self.project.mobs)
            choices = [key for key, entry in available.items() if not entry.get('native') or make_skill(entry,{}).skill_type not in (SkillType.INVOCATION,SkillType.RESURRECT)]
            if not choices:
                self.messagebox.showinfo('Compétences','Aucune compétence compatible.',parent=window)
                return
            values = self.form('Réutiliser une compétence',{'skill_id':choices[0],'level':1,'range':6.0},{'skill_id':choices})
            if values:
                rows.append(values)
                refresh()
        def delete():
            for index in sorted((int(value) for value in table.selection()), reverse=True):
                rows.pop(index)
            refresh()
        result = []
        def accept():
            result.append(rows)
            window.destroy()
        bar = self.ttk.Frame(window)
        bar.pack(fill='x')
        for label, action in [('Ajouter',lambda:edit(True)),('Modifier',edit),('Supprimer',delete),('Appliquer',accept),('Annuler',window.destroy)]:
            self.ttk.Button(bar,text=label,command=action).pack(side='left')
        if title == 'Capacités':
            self.ttk.Button(bar,text='Réutiliser une compétence',command=reuse).pack(side='left')
        refresh()
        window.transient(self.root)
        window.grab_set()
        self.root.wait_window(window)
        return result[0] if result else None

    def edit_loot(self, initial):
        window = self.tk.Toplevel(self.root)
        window.title('Matériaux donnés par la créature')
        loot = deepcopy(initial)
        table = self.ttk.Treeview(window, columns=('count',), show='tree headings', height=10)
        table.heading('#0', text='Matériau')
        table.heading('count', text='Quantité')
        table.pack(fill='both', expand=True, padx=8, pady=8)
        def refresh():
            table.delete(*table.get_children())
            for material, count in loot.items():
                table.insert('', 'end', iid=material, text=material, values=(count,))
        def edit():
            selected = table.selection()
            material = selected[0] if selected else 'peau'
            values = self.form('Matériau', {'material':material, 'quantity':loot.get(material, 1)})
            if values:
                if selected and values['material'] != material:
                    loot.pop(material)
                loot[values['material']] = values['quantity']
                refresh()
        def delete():
            for material in table.selection():
                loot.pop(material, None)
            refresh()
        result = []
        def accept():
            result.append(loot)
            window.destroy()
        bar = self.ttk.Frame(window)
        bar.pack(fill='x', padx=8, pady=8)
        for label, action in [('Ajouter / modifier',edit), ('Retirer',delete), ('Appliquer',accept), ('Annuler',window.destroy)]:
            self.ttk.Button(bar, text=label, command=action).pack(side='left')
        refresh()
        window.transient(self.root)
        window.grab_set()
        self.root.wait_window(window)
        return result[0] if result else None

    def delete(self, section):
        selected = self.tables[section].selection()
        if not selected:
            return
        if section == 'maps':
            self.builder()
            return
        key = selected[0]
        if not self.messagebox.askyesno('Supprimer', 'Supprimer cette définition ?', parent=self.root):
            return
        before = self.project.state()
        try:
            if section == 'skill_models':
                self.project.content['templates']['skills'].pop(key)
            elif section == 'classes' and any(item['id'] == key for item in self.project.content['templates']['classes']):
                self.project.content['templates']['classes'] = [item for item in self.project.content['templates']['classes'] if item['id'] != key]
            elif section == 'mobs':
                self.project.mobs.pop(key)
            elif section == 'npcs':
                map_id, index = key.rsplit(':',1)
                self.project.maps[map_id]['sites'].pop(int(index))
            else:
                self.project.content[section] = [item for item in self.project.content[section] if item['id'] != key]
            self.project.validate()
            self.remember(before)
            self.refresh()
        except (ValueError, KeyError) as exc:
            self.project.maps, self.project.mobs, self.project.content, self.project.encounters = before
            self.messagebox.showerror('Suppression refusée', str(exc), parent=self.root)

    def builder(self, new=False):
        from . import map_editor, map_building
        from tkinter import filedialog
        for name, value in [('tk',self.tk), ('ttk',self.ttk), ('messagebox',self.messagebox), ('simpledialog',self.simpledialog), ('filedialog',filedialog)]:
            setattr(map_editor, name, value)
        from .editor_ui import EditorPanel
        window = EditorPanel(self.root, "Builder")
        window.content.pack_forget()
        previous_mobs = map_building.MOBS
        previous_editor_mobs = map_editor.MOBS
        map_building.MOBS = map_editor.MOBS = self.project.mobs
        before = self.project.state()
        editor = map_editor.MapEditor(window, self.project.directory/'world.json')
        editor.maps = deepcopy(self.project.maps)
        editor.saved = deepcopy(editor.maps)
        chosen = self.tables['maps'].selection()
        if chosen:
            editor.selected.set(chosen[0])
        editor.refresh_choice()
        editor.draw()
        def sync_save(choose=False):
            old = self.project.maps
            self.project.maps = deepcopy(editor.maps)
            try:
                self.project.save()
                editor.saved = deepcopy(editor.maps)
                editor.status.set('Projet enregistré. Redémarrez le serveur pour appliquer.')
            except (ValueError, OSError) as exc:
                self.project.maps = old
                editor.messages.showerror('Projet', str(exc), parent=window)
        editor.on_save = sync_save
        window.transient(self.root)
        window.grab_set()
        if new:
            editor.new()
        def close_builder():
            if editor.maps != editor.saved:
                answer = editor.messages.askyesnocancel('Builder', 'Garder les modifications dans le contrôleur ? Elles pourront être enregistrées depuis celui-ci.', parent=window)
                if answer is None:
                    return
                if not answer:
                    editor.maps = deepcopy(editor.saved)
            window.destroy()
        window.protocol('WM_DELETE_WINDOW', close_builder)
        self.root.wait_window(window)
        map_building.MOBS = previous_mobs
        map_editor.MOBS = previous_editor_mobs
        self.project.maps = deepcopy(editor.maps)
        if self.project.state() != before:
            self.remember(before)
        self.refresh()

    def validate(self):
        from .controller_tools import report
        try:
            result = report(self.project)
            self.show_report('Diagnostic du projet', result)
            valid = not result['erreurs']
            self.status.set('Projet valide.' if valid else 'Corrigez les erreurs du diagnostic avant de sauvegarder.')
            return valid
        except (ValueError, KeyError, TypeError) as exc:
            self.messagebox.showerror('Validation', str(exc), parent=self.root)
            return False

    def save(self):
        try:
            self.project.save()
            self.status.set('Projet enregistré. Redémarrez le serveur pour appliquer. Sessions nouvelles recommandées après modification des objectifs.')
        except (ValueError, OSError) as exc:
            self.messagebox.showerror('Enregistrement', str(exc), parent=self.root)

    def close(self):
        if self.project.state() != self.project.snapshot:
            answer = self.messagebox.askyesnocancel('Fermer', 'Enregistrer les modifications avant de fermer ?', parent=self.root)
            if answer is None:
                return
            if answer:
                self.save()
                if self.project.state() != self.project.snapshot:
                    return
        self.root.destroy()


from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description='Contrôleur graphique du contenu RPG')
    parser.add_argument('directory', nargs='?', default='maps')
    args = parser.parse_args()
    import tkinter as tk
    root = tk.Tk()
    try:
        project = Project(args.directory)
        Controller(root, project)
    except (ValueError, OSError) as exc:
        root.destroy()
        raise SystemExit(str(exc)) from exc
    root.mainloop()


if __name__ == '__main__':
    main()
