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


DECIMAL_FIELDS = {'chance','threshold','xp_multiplier','damage_growth','power','growth','cooldown','cast','range','duration','repop_seconds','xp_base','xp_exponent','merchant_stay_hours','hp_multiplier','damage_multiplier'}


def parse_field(key, value, initial):
    if type(initial) is bool:
        return value == 'Oui'
    if key in DECIMAL_FIELDS or key.endswith(('_base','_growth')) or type(initial) is float:
        return float(value.strip().replace(',','.'))
    if type(initial) is int:
        return int(value)
    return value


class ControllerEditorsMixin:
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

