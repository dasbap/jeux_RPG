from copy import deepcopy

from .map_building import map_level, zone_of
from .map_assets import validate


CORE = {'clearing', 'rosee', 'lisiere', 'hunt', 'forest', 'cave_1', 'brume'}


def positions(maps):
    return {key: list(data.get('world_origin', [(index % 4) * 72, (index // 4) * 48])) for index, (key, data) in enumerate(maps.items())}


def align(maps, moving, anchor, direction, gap=0):
    if moving == anchor or direction not in ('est', 'ouest', 'nord', 'sud'):
        raise ValueError('Choisissez deux cartes différentes et une direction valide.')
    result = deepcopy(maps)
    origin = positions(maps)[anchor]
    a, b = maps[anchor], maps[moving]
    x, y = origin
    if direction == 'est':
        x += a['width'] + gap
    elif direction == 'ouest':
        x -= b['width'] + gap
    elif direction == 'sud':
        y += a['height'] + gap
    else:
        y -= b['height'] + gap
    result[anchor]['world_origin'] = origin
    result[moving]['world_origin'] = [x, y]
    return result


def merge(maps, target_id, source_id):
    if target_id == source_id or source_id in CORE:
        raise ValueError('La carte absorbée doit être différente et ne doit pas être une carte obligatoire du tutoriel.')
    target, source = maps[target_id], maps[source_id]
    if zone_of(maps, target_id) != zone_of(maps, source_id):
        raise ValueError('Rattachez les deux cartes à la même zone avant de fusionner.')
    layout = positions(maps)
    tx, ty = layout[target_id]
    sx, sy = layout[source_id]
    left, top = min(tx, sx), min(ty, sy)
    width = max(tx + target['width'], sx + source['width']) - left
    height = max(ty + target['height'], sy + source['height']) - top
    if width > 128 or height > 128:
        raise ValueError('La carte fusionnée dépasserait 128 × 128 cases. Rapprochez les blocs.')
    if target.get('cell_metres', 2) != source.get('cell_metres', 2):
        raise ValueError('Les deux cartes doivent avoir la même taille de case.')
    result = deepcopy(maps)
    offsets = {target_id: [tx-left, ty-top], source_id: [sx-left, sy-top]}
    merged = result[target_id]
    merged.update(width=width, height=height, world_origin=[left, top])
    merged.pop('overlap_columns', None)
    if zone_of(maps, target_id) == source_id:
        merged['zone_level'] = source.get('zone_level', 1)
    def shifted(point, key):
        dx, dy = offsets[key]
        return [point[0]+dx, point[1]+dy]
    def target_contains(point):
        return tx-left <= point[0] < tx-left+target['width'] and ty-top <= point[1] < ty-top+target['height']
    for field in ('cover', 'blocked', 'water', 'bridges', 'paths'):
        merged[field] = [shifted(p, target_id) for p in target.get(field, [])]
        merged[field] += [p for old in source.get(field, []) if not target_contains(p := shifted(old, source_id))]
    merged['bridge_rotations'] = [{**deepcopy(item), 'position': shifted(item['position'], key)} for key, data in ((target_id, target), (source_id, source)) for item in data.get('bridge_rotations', []) if key == target_id or not target_contains(shifted(item['position'], key))]
    merged['decorations'] = [{**deepcopy(item), 'position': shifted(item['position'], key)} for key, data in ((target_id, target), (source_id, source)) for item in data.get('decorations', []) if key == target_id or not target_contains(shifted(item['position'], key))]
    for field in ('spawns', 'sites', 'spawners', 'exits'):
        merged[field] = []
        for key, data in ((target_id, target), (source_id, source)):
            entries = data.get(field, [])
            if field == 'spawners':
                configured = {tuple(item['position']): item for item in entries}
                entries = [configured.get(tuple(point), {'position': point, 'mob_id': 'goblin'}) for point in data.get('spawns', [])]
            for old in entries:
                if field == 'spawns':
                    item = shifted(old, key)
                    if item in merged[field]:
                        raise ValueError('Deux spawners se superposent. Déplacez-les avant la fusion.')
                else:
                    if field == 'exits' and old.get('destination') in offsets:
                        continue
                    item = deepcopy(old)
                    item['position'] = shifted(old['position'], key)
                    if field == 'spawners':
                        item['patrol'] = [shifted(p, key) for p in old.get('patrol', [])]
                        item['level'] = old.get('level') or map_level(maps, key)
                    if field == 'sites' and any(site['id'] == item['id'] for site in merged[field]):
                        raise ValueError('Deux PNJ ont le même identifiant. Renommez-en un avant la fusion.')
                    if field == 'exits' and any(g['position'] == item['position'] for g in merged[field]):
                        raise ValueError('Deux passages se superposent. Déplacez-en un avant la fusion.')
                merged[field].append(item)
    for data in result.values():
        for gate in data['exits']:
            destination = gate.get('destination')
            if destination in offsets:
                gate['entry'] = shifted(gate['entry'], destination)
                gate['destination'] = target_id
            if gate.get('fast_destination') == source_id:
                gate['fast_destination'] = target_id
        for route in data.get('travel_routes', []):
            for endpoint in ('from', 'to'):
                if route[endpoint] == source_id:
                    route[endpoint] = target_id
        for field in ('zone_id', 'world_zone', 'fast_travel_origin'):
            if data.get(field) == source_id:
                data[field] = target_id
    del result[source_id]
    return validate(result)


class AssemblyWindow:
    def __init__(self, editor):
        import tkinter as tk
        from tkinter import ttk, messagebox
        self.editor, self.tk, self.messagebox = editor, tk, editor.messages
        from .editor_ui import EditorPanel
        self.panel = EditorPanel(editor.root)
        self.window = self.panel.content
        self.panel.title('Assemblage des cartes')
        self.panel.geometry('1150x760')
        self.selected = editor.selected.get()
        self.scale = 8
        self.dragging = None
        self.link_source = None
        self.bounds = None
        self.info = tk.StringVar(value='Glissez un bloc pour le déplacer sur la grille. Molette : zoom. Double clic : éditer.')
        bar = ttk.Frame(self.window, padding=5)
        bar.pack(fill='x')
        for index, (label, command) in enumerate((('Coller / espacer', self.place), ('Créer une zone', self.new_zone), ('Raccorder', self.connect), ('Supprimer un raccord', self.disconnect), ('Annuler raccord', self.cancel_connect), ('Fusionner dans la sélection', self.fuse), ('Annuler', self.undo), ('Enregistrer', editor.save))):
            ttk.Button(bar, text=label, command=command).grid(row=index//5, column=index%5, padx=3, pady=3, sticky='w')
        selector = ttk.Frame(self.window, padding=4)
        selector.pack(fill='x')
        ttk.Label(selector, text='Bloc sélectionné').pack(side='left')
        self.selection = tk.StringVar(value=self.selected)
        self.choice = ttk.Combobox(selector, textvariable=self.selection, values=list(editor.maps), state='readonly', width=30)
        self.choice.pack(side='left', padx=5)
        self.choice.bind('<<ComboboxSelected>>', self.choose)
        ttk.Label(self.window, textvariable=self.info, wraplength=1100).pack(fill='x')
        frame = ttk.Frame(self.window)
        frame.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(frame, background='#101721')
        self.canvas.grid(row=0, column=0, sticky='nsew')
        xs = ttk.Scrollbar(frame, orient='horizontal', command=self.canvas.xview)
        ys = ttk.Scrollbar(frame, orient='vertical', command=self.canvas.yview)
        xs.grid(row=1, column=0, sticky='ew')
        ys.grid(row=0, column=1, sticky='ns')
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.canvas.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        self.canvas.bind('<Button-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Double-Button-1>', self.edit)
        self.canvas.bind('<MouseWheel>', lambda e: self.zoom(1 if e.delta > 0 else -1, e))
        self.canvas.bind('<Button-4>', lambda e: self.zoom(1, e))
        self.canvas.bind('<Button-5>', lambda e: self.zoom(-1, e))
        self.canvas.bind('<Button-2>', lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind('<B2-Motion>', lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.window.bind('<Escape>', lambda e: self.cancel_connect())
        self.draw()

    def choose(self, event=None):
        self.selected = self.selection.get()
        self.draw()

    def draw(self):
        self.choice.configure(values=list(self.editor.maps))
        self.selection.set(self.selected)
        self.canvas.delete('all')
        layout = positions(self.editor.maps)
        self.offset = [0, 0]
        for key, data in self.editor.maps.items():
            x, y = layout[key]
            for gate in data['exits']:
                destination = gate.get('destination')
                if destination not in layout or destination == key:
                    continue
                dx, dy = layout[destination]
                other = self.editor.maps[destination]
                self.canvas.create_line((x+data['width']/2-self.offset[0])*self.scale, (y+data['height']/2-self.offset[1])*self.scale, (dx+other['width']/2-self.offset[0])*self.scale, (dy+other['height']/2-self.offset[1])*self.scale, fill='#8bcdbc', width=2, arrow='last')
        for key, data in self.editor.maps.items():
            x, y = layout[key]
            x, y = (x-self.offset[0])*self.scale, (y-self.offset[1])*self.scale
            tag = 'map:'+key
            ground, cover = {'cave': ('#374250', '#48505a'), 'village': ('#667356', '#344934')}.get(data.get('biome'), ('#294b35', '#344934'))
            colors = {'water': '#286779', 'paths': '#ad9369', 'cover': cover, 'bridges': '#d7b785'}
            self.canvas.create_rectangle(x, y, x+data['width']*self.scale, y+data['height']*self.scale, fill=ground, outline='#ffdc83' if key == self.selected else '#849bb5', width=3 if key == self.selected else 1, tags=(tag,))
            for field, color in colors.items():
                for px, py in data.get(field, []):
                    self.canvas.create_rectangle(x+px*self.scale, y+py*self.scale, x+(px+1)*self.scale, y+(py+1)*self.scale, fill=color, outline='', tags=(tag,))
            self.canvas.create_text(x+4, y+4, text=f"{data['name']}\n[{key}] {layout[key]}", anchor='nw', fill='white', width=max(50, data['width']*self.scale-8), tags=(tag,))
        from . import world
        for route in self.editor.maps['clearing'].get('travel_routes', world.ROUTES) if 'clearing' in self.editor.maps else []:
            if route['from'] not in layout or route['to'] not in layout:
                continue
            source, target = self.editor.maps[route['from']], self.editor.maps[route['to']]
            x, y = layout[route['from']]
            dx, dy = layout[route['to']]
            start = ((x+source['width']/2)*self.scale, (y+source['height']/2)*self.scale)
            end = ((dx+target['width']/2)*self.scale, (dy+target['height']/2)*self.scale)
            self.canvas.create_line(*start, *end, fill='#ffe080', dash=(6, 4), width=2, arrow='both' if route.get('bidirectional', True) else 'last')
        from .map_viewport import assembly_bounds
        self.bounds = assembly_bounds(self.editor.maps, layout, getattr(self, 'bounds', None))
        self.canvas.configure(scrollregion=tuple(value*self.scale for value in self.bounds))

    def press(self, event):
        items = self.canvas.find_overlapping(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y), self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if not items:
            return
        tags = self.canvas.gettags(items[-1])
        key = next((tag[4:] for tag in tags if tag.startswith('map:')), None)
        if key:
            if getattr(self, "link_source", None):
                if key != self.link_source:
                    self.finish_connect(key)
                return
            self.selected = key
            self.dragging = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y), positions(self.editor.maps)[key], False)
            self.info.set(f"{key} : glissez pour déplacer. Coller / espacer règle une distance exacte ; fusion conserve ce bloc.")

    def drag(self, event):
        if not self.dragging:
            return
        x, y, origin, remembered = self.dragging
        dx = round((self.canvas.canvasx(event.x)-x)/self.scale)
        dy = round((self.canvas.canvasy(event.y)-y)/self.scale)
        if not remembered and (dx or dy):
            self.editor.remember()
            remembered = True
        if remembered:
            self.editor.maps[self.selected]['world_origin'] = [origin[0]+dx, origin[1]+dy]
            self.dragging = (x, y, origin, remembered)
            tag = 'map:'+self.selected
            self.canvas.move(tag, dx*self.scale-getattr(self, 'last_dx', 0), dy*self.scale-getattr(self, 'last_dy', 0))
            self.last_dx, self.last_dy = dx*self.scale, dy*self.scale

    def release(self, event):
        self.dragging = None
        self.last_dx = self.last_dy = 0
        self.draw()

    def zoom(self, amount, event=None):
        from .map_viewport import zoom_canvas
        previous = self.scale
        self.scale = max(2, min(32, self.scale+amount))
        zoom_canvas(self.canvas, previous, self.scale, self.draw, event.x if event else None, event.y if event else None)

    def edit(self, event=None):
        self.editor.selected.set(self.selected)
        self.editor.refresh_choice()
        self.editor.draw()
        self.panel.destroy()

    def undo(self):
        self.editor.undo()
        if self.selected not in self.editor.maps:
            self.selected = self.editor.selected.get()
        self.draw()

    def apply(self, maps):
        self.editor.remember()
        self.editor.maps = maps
        self.editor.selected.set(self.selected)
        self.editor.refresh_choice()
        self.editor.draw()
        self.draw()

    def place(self):
        values = self.editor.form('Coller / espacer la sélection', {'anchor': '', 'direction': 'est', 'gap': 0})
        if not values:
            return
        try:
            self.apply(align(self.editor.maps, self.selected, values['anchor'], values['direction'], int(values['gap'])))
        except (ValueError, KeyError) as exc:
            self.messagebox.showerror('Assemblage', str(exc), parent=self.window)

    def new_zone(self):
        from .map_links import create_zone
        values = self.editor.form('Créer une zone', {'map_id': '', 'name': 'Nouvelle zone', 'width': 30, 'height': 20, 'biome': 'forest', 'zone_level': 1})
        if not values:
            return
        try:
            anchor = self.editor.maps[self.selected]
            origin = positions(self.editor.maps)[self.selected]
            result = create_zone(self.editor.maps, values['map_id'], values['name'], int(values['width']), int(values['height']), values['biome'], int(values['zone_level']), [origin[0]+anchor['width']+8, origin[1]])
            self.selected = values['map_id']
            self.apply(result)
        except (ValueError, KeyError) as exc:
            self.messagebox.showerror('Zone', str(exc), parent=self.window)

    def connect(self):
        self.link_source = self.selected
        self.dragging = None
        self.info.set(f"Raccorder {self.selected} : cliquez le bloc destination. Échap pour annuler.")

    def cancel_connect(self):
        self.link_source = None
        self.info.set('Glissez un bloc pour le déplacer. Molette : zoom au pointeur. Bouton central : déplacer la vue.')

    def finish_connect(self, destination):
        from .map_objects import pick_cell
        from .map_links import connect_maps
        source = self.link_source
        self.cancel_connect()
        values = self.editor.form('Type de raccord', {'link_mode': 'trajet', 'name': 'Chemin'})
        if not values:
            return
        mode = values['link_mode']
        point = entry = reverse = returning = None
        if mode != 'rapide':
            first = pick_cell(self.editor, '1 · Départ sur '+self.editor.maps[source]['name'], source)
            if not first:
                return
            second = pick_cell(self.editor, '2 · Arrivée sur '+self.editor.maps[destination]['name'], destination)
            if not second:
                return
            point, entry = first[1], second[1]
        both = self.messagebox.askyesno('Sens du raccord', 'Créer aussi le trajet de retour ?', parent=self.window)
        if both and mode != 'rapide':
            third = pick_cell(self.editor, '3 · Départ du retour sur '+self.editor.maps[destination]['name'], destination)
            if not third:
                return
            fourth = pick_cell(self.editor, '4 · Arrivée du retour sur '+self.editor.maps[source]['name'], source)
            if not fourth:
                return
            reverse, returning = third[1], fourth[1]
        minutes = 0
        if mode != 'passage':
            timing = self.editor.form('Durée du trajet', {'travel_minutes': 1})
            if not timing:
                return
            try:
                minutes = float(timing['travel_minutes'])
            except ValueError:
                self.messagebox.showerror('Raccord', 'Durée numérique requise.', parent=self.window)
                return
        try:
            self.apply(connect_maps(self.editor.maps, source, destination, values['name'], minutes, mode, point, entry, reverse, returning, both))
            self.info.set('Raccord créé. Enregistrez pour le conserver ; redémarrez le serveur pour appliquer les chemins rapides.')
        except (ValueError, KeyError, TypeError) as exc:
            self.messagebox.showerror('Raccord', str(exc), parent=self.window)

    def disconnect(self):
        from .map_links import links_from, remove_link
        links = links_from(self.editor.maps, self.selected)
        if not links:
            self.info.set('Aucun raccord sortant pour ce bloc.')
            return
        self.editor.object_choices = {f"{index+1} · {name} → {destination} ({kind})": (kind, item) for index, (kind, item, destination, name) in enumerate(links)}
        values = self.editor.form('Supprimer un raccord', {'object_choice': next(iter(self.editor.object_choices)), 'remove_reverse': False})
        if not values:
            return
        try:
            kind, index = self.editor.object_choices[values['object_choice']]
            self.apply(remove_link(self.editor.maps, self.selected, kind, index, values['remove_reverse']))
        except (ValueError, KeyError) as exc:
            self.messagebox.showerror('Raccord', str(exc), parent=self.window)

    def fuse(self):
        values = self.editor.form('Fusionner dans la sélection', {'source_map': ''})
        if not values:
            return
        try:
            updated = merge(self.editor.maps, self.selected, values['source_map'])
            if self.messagebox.askyesno('Fusion', 'La carte absorbée sera supprimée. Le bloc sélectionné conserve son identité et son décor dans les chevauchements. Les passages internes disparaissent, les passages externes sont recalculés. Continuer ?', parent=self.window):
                self.apply(updated)
        except (ValueError, KeyError) as exc:
            self.messagebox.showerror('Fusion impossible', str(exc), parent=self.window)
