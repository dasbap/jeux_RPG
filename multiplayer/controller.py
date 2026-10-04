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


class Project:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        packaged = Path(__file__).resolve().parents[1] / 'maps'
        for source in packaged.glob('*.json'):
            target = self.directory/source.name
            if not target.exists():
                shutil.copyfile(source, target)
        self.mobs = validate_mobs(json.loads((self.directory/'mobs.json').read_text(encoding='utf-8'))['maps'])
        from . import map_building
        previous = map_building.MOBS
        try:
            map_building.MOBS = self.mobs
            self.maps = load(self.directory/'world.json')
        finally:
            map_building.MOBS = previous
        self.content = load_content(self.directory/'content.json')
        self.snapshot = self.state()

    def state(self):
        return deepcopy((self.maps, self.mobs, self.content))

    def validate(self):
        validate_mobs(self.mobs)
        validate_content(self.content)
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
        return True

    def rename(self, section, identifier, replacement):
        import re
        if not isinstance(replacement, str) or not re.fullmatch(r'[a-z0-9_]{1,64}', replacement):
            raise ValueError('Identifiant : 1–64 lettres minuscules, chiffres ou underscores (ex. mira_hunt_2).')
        if identifier == replacement:
            return
        before = self.state()
        try:
            if section in ('quests', 'achievements'):
                item = next(item for item in self.content[section] if item['id'] == identifier)
                if any(other['id'] == replacement or replacement in other.get('previous_ids', []) for other in self.content[section] if other is not item):
                    raise ValueError('Identifiant déjà utilisé.')
                if section == 'quests' and is_hunt(item):
                    item['role'] = 'tutorial_hunt'
                item['previous_ids'] = list(dict.fromkeys([*item.get('previous_ids', []), identifier]))
                item['id'] = replacement
            elif section == 'mobs':
                if identifier == 'goblin':
                    raise ValueError('goblin est une référence interne du tutoriel ; créez une nouvelle espèce pour un autre identifiant.')
                if replacement in self.mobs:
                    raise ValueError('Identifiant déjà utilisé.')
                self.mobs[replacement] = self.mobs.pop(identifier)
                for species in self.mobs.values():
                    if species.get('parent') == identifier:
                        species['parent'] = replacement
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
                self.maps[replacement]['id'] = 'field_'+replacement
                for data in self.maps.values():
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
                for quest in self.content['quests']:
                    if quest.get('zone') == identifier:
                        quest['zone'] = replacement
            else:
                raise ValueError('Ce type de définition ne possède pas d’identifiant modifiable.')
            self.validate()
        except Exception:
            self.maps, self.mobs, self.content = before
            raise

    def save(self):
        self.validate()
        payloads = {'world.json': self.maps, 'mobs.json': {'kind': 'mobs', 'maps': self.mobs}, 'content.json': {'kind': 'content', 'maps': {}, 'content': self.content}}
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
        root.title('RPG — Contrôleur du projet')
        root.geometry('1120x780')
        root.protocol('WM_DELETE_WINDOW', self.close)
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill='x')
        for name, action in [('Builder', self.builder), ('Valider', self.validate), ('Enregistrer le projet', self.save), ('Annuler modification', self.undo)]:
            ttk.Button(bar, text=name, command=action).pack(side='left', padx=4)
        self.status = tk.StringVar(value=f'{project.directory} · Modifiez puis enregistrez. Redémarrez le serveur pour appliquer.')
        ttk.Label(root, textvariable=self.status, wraplength=1080).pack(fill='x', padx=8)
        notebook = ttk.Notebook(root)
        notebook.pack(fill='both', expand=True, padx=8, pady=8)
        self.tables = {}
        for section, title in [('maps', 'Cartes / zones'), ('quests', 'Quêtes'), ('mobs', 'Mobs'), ('achievements', 'Succès et titres'), ('npcs', 'PNJ'), ('world', 'Monde')]:
            page = ttk.Frame(notebook, padding=8)
            notebook.add(page, text=title)
            table = ttk.Treeview(page, columns=('name', 'details'), show='tree headings', selectmode='browse')
            table.heading('#0', text='Identifiant')
            table.heading('name', text='Nom')
            table.heading('details', text='Détails')
            table.column('#0', width=190)
            table.column('name', width=240)
            table.column('details', width=540)
            table.pack(fill='both', expand=True)
            table.bind('<Double-1>', lambda e, s=section: self.edit(s))
            self.tables[section] = table
            actions = ttk.Frame(page)
            actions.pack(fill='x', pady=8)
            for label, action in [('Modifier', lambda s=section:self.edit(s))] + ([] if section == 'world' else [('Ajouter', lambda s=section:self.edit(s, True)), ('Supprimer', lambda s=section:self.delete(s))]):
                ttk.Button(actions, text=label, command=action).pack(side='left', padx=4)
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
        self.history.append(self.project.state() if state is None else state)
        self.history = self.history[-30:]

    def undo(self):
        if self.history:
            self.project.maps, self.project.mobs, self.project.content = self.history.pop()
            self.refresh()

    def refresh(self):
        p = self.project
        rows = {
            'maps': [(key, data['name'], f"{data['width']} × {data['height']} · zone {zone_of(p.maps, key)}") for key, data in p.maps.items()],
            'mobs': [(key, resolve(p.mobs,key)['name'], f"{resolve(p.mobs,key)['class_name']} · rang {resolve(p.mobs,key)['rank']} · parent {mob.get('parent') or 'aucun'}") for key, mob in p.mobs.items()],
            'quests': [(q['id'], q['name'], f"{q['npc']} · {q['kind']} {q['target']} × {q['count']} · {q['reward_xp']} XP") for q in p.content['quests']],
            'achievements': [(a['id'], a['name'], f"{a['condition']} · {a['threshold']} → {a['title']}") for a in p.content['achievements']],
            'npcs': [(f'{key}:{index}', site['name'], f"{key} · {site['id']} · case {site['position']}") for key, data in p.maps.items() for index, site in enumerate(data.get('sites', []))],
            'world': [(key, self.label(key), str(value)) for key, value in p.content['world'].items()],
        }
        for section, table in self.tables.items():
            table.delete(*table.get_children())
            for key, name, details in rows[section]:
                table.insert('', 'end', iid=key, text=key, values=(name, details))

    def label(self, key):
        if key.endswith('_base'):
            return key[:-5]+' · valeur au niveau 1'
        if key.endswith('_growth') and key != 'damage_growth':
            return key[:-7]+' · croissance par niveau'
        return {'id':'Identifiant', 'name':'Nom', 'npc':'PNJ donneur', 'kind':'Type d’objectif', 'target':'Espèce / recette cible', 'zone':'Zone requise (vide = toutes)', 'count':'Nombre requis', 'reward_xp':'Récompense XP par joueur', 'description':'Description', 'condition':'Condition', 'threshold':'Seuil', 'title':'Titre obtenu', 'class_name':'Classe de base', 'rank':'Rang', 'damage':'Dégâts', 'dialogue':'Dialogue', 'owner':'Joueur lié (vide = fixe)', 'map_id':'Carte', 'width':'Largeur', 'height':'Hauteur', 'zone_level':'Niveau de zone', 'biome':'Ambiance', 'repop_seconds':'Repop après absence (secondes en jeu)', 'mob_xp':'XP par mob', 'xp_base':'Base XP nécessaire', 'xp_exponent':'Exposant de progression XP', 'merchant_stay_hours':'Séjour du marchand (heures en jeu)', 'player_vision':'Vision joueur (cases)', 'xp_class':'Classe de récompense XP', 'xp_multiplier':'Multiplicateur XP', 'damage_growth':'Dégâts ajoutés par niveau', 'parent':'Espèce parente', 'item':'Matériau', 'chance':'Probabilité (0–1)', 'attempts':'Nombre de tirages indépendants', 'min':'Quantité minimale par réussite', 'max':'Quantité maximale par réussite', 'rare':'Matériau rare', 'power':'Puissance de base', 'growth':'Puissance par niveau', 'cooldown':'Cooldown (secondes réelles)', 'cast':'Incantation (secondes réelles)', 'range':'Portée (cases)', 'duration':'Durée du stun (secondes réelles)', 'level':'Niveau de déblocage', 'concentration':'Interrompue par les dégâts', 'type':'Effet'}.get(key, key)

    def form(self, title, values, choices=None):
        window = self.tk.Toplevel(self.root)
        window.title(title)
        fields = {}
        labels = {}
        choices = choices or {}
        for row, (key, value) in enumerate(values.items()):
            labels[key] = self.ttk.Label(window, text=self.label(key))
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
            numeric = fields['condition'].get() in ('fast', 'higher', 'level', 'kills')
            for widget in (labels['threshold'], fields['threshold']):
                widget.grid() if numeric else widget.grid_remove()
        if 'condition' in fields and 'threshold' in fields:
            fields['condition'].bind('<<ComboboxSelected>>', condition_changed)
            condition_changed()
        def kind_changed(event=None):
            from .forge import RECIPES
            targets = list(self.project.mobs) if fields['kind'].get() == 'kill' else list(RECIPES)
            fields['target'].configure(values=targets)
            if fields['target'].get() not in targets:
                fields['target'].set(targets[0])
        if 'kind' in fields and 'target' in fields:
            fields['kind'].bind('<<ComboboxSelected>>', kind_changed)
            kind_changed()
        result = []
        def accept():
            try:
                parsed = {key: widget.get() == 'Oui' if type(values[key]) is bool else float(widget.get()) if key == 'threshold' else int(widget.get()) if type(values[key]) is int else float(widget.get()) if type(values[key]) is float else widget.get() for key, widget in fields.items()}
                if 'condition' in parsed and parsed['condition'] not in ('fast', 'higher', 'level', 'kills'):
                    parsed['threshold'] = 1
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
            elif section == 'mobs':
                from . import forge
                old = resolve(p.mobs, key) if not new else {'name':'Nouvelle créature','class_name':'Goblin','rank':'D','damage':3,'loot':{'peau':1}}
                public = {'id':key or '', 'name':old['name'], 'class_name':old['class_name'], 'rank':old['rank'], 'damage':old['damage'], 'damage_growth':float(old.get('damage_growth',.5)), 'xp_class':old.get('xp_class', 'normal' if old['class_name'] == 'Goblin' else 'warrior' if old['class_name'] == 'Orc' else 'elite'), 'xp_multiplier':float(old.get('xp_multiplier',1)), 'parent':p.mobs[key].get('parent','') if not new else ''}
                values = self.form('Espèce / sous-espèce', public, {'class_name':['Goblin','Orc','DragonWhelp'], 'rank':RANKS, 'xp_class':list(CLASS_XP), 'parent':['', *p.mobs]})
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
                p.mobs[identifier] = {**values, 'stats':stats, 'drops':drops, 'loot':{}, 'abilities':abilities}
            elif section in ('quests', 'achievements'):
                default = {'id':'', 'name':'Nouvelle quête', 'npc':'mira', 'kind':'kill', 'target':'goblin', 'zone':'', 'count':1, 'reward_xp':50, 'description':'Objectif de quête'} if section == 'quests' else {'id':'', 'name':'Nouveau succès', 'condition':'kills', 'threshold':1, 'title':'Nouveau titre'}
                old = default if new else next(item for item in p.content[section] if item['id'] == key)
                choices = {'npc':sorted({site['id'] for data in p.maps.values() for site in data['sites']}), 'kind':['kill','craft'], 'target':list(p.mobs), 'zone':['', *p.maps], 'condition':CONDITIONS}
                values = self.form('Quête' if section == 'quests' else 'Succès et titre', {k:v for k,v in old.items() if k not in ('role', 'previous_ids')}, choices)
                if values:
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
            self.project.maps, self.project.mobs, self.project.content = before
            self.messagebox.showerror('Sous-espèce', str(exc), parent=self.root)

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
                table.insert('', 'end', iid=str(index), text=item.get('name',item.get('item','')), values=(str(item),))
        def edit(new=False):
            selected = table.selection()
            if not new and not selected:
                return
            index = int(selected[0]) if selected else None
            value = self.form(title, {**default, **({} if new else rows[index])}, choices)
            if value:
                rows.append(value) if new else rows.__setitem__(index,value)
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
            if section == 'mobs':
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
            self.project.maps, self.project.mobs, self.project.content = before
            self.messagebox.showerror('Suppression refusée', str(exc), parent=self.root)

    def builder(self, new=False):
        from . import map_editor, map_building
        from tkinter import filedialog
        for name, value in [('tk',self.tk), ('ttk',self.ttk), ('messagebox',self.messagebox), ('simpledialog',self.simpledialog), ('filedialog',filedialog)]:
            setattr(map_editor, name, value)
        window = self.tk.Toplevel(self.root)
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
                self.messagebox.showerror('Projet', str(exc), parent=window)
        editor.on_save = sync_save
        window.transient(self.root)
        window.grab_set()
        if new:
            editor.new()
        def close_builder():
            if editor.maps != editor.saved:
                answer = self.messagebox.askyesnocancel('Builder', 'Garder les modifications dans le contrôleur ? Elles pourront être enregistrées depuis celui-ci.', parent=window)
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
        try:
            self.project.validate()
            self.status.set('Projet valide : cartes, espèces, quêtes, PNJ et succès cohérents.')
            return True
        except (ValueError, KeyError) as exc:
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
