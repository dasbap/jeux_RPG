from copy import deepcopy
import math
import re


def world_metadata(maps, streets, routes):
    streets, routes = deepcopy(streets), deepcopy(routes)
    for key, data in maps.items():
        if 'village_streets' in data:
            layout = data['village_streets']
            if not isinstance(layout, dict) or not isinstance(layout.get('square'), str) or not re.fullmatch(r'[a-z0-9_]{1,64}', layout['square']) or not isinstance(layout.get('streets'), list) or len(layout['streets']) > 64:
                raise ValueError(f'{key} : plan de rues invalide.')
            seen = {layout['square']}
            for street in layout['streets']:
                if not isinstance(street, dict) or not isinstance(street.get('id'), str) or not re.fullmatch(r'[a-z0-9_]{1,64}', street['id']) or street['id'] in seen or not isinstance(street.get('name'), str) or not 1 <= len(street['name']) <= 100 or not isinstance(street.get('buildings'), list) or len(street['buildings']) > 64:
                    raise ValueError(f'{key} : rue invalide ou dupliquée.')
                seen.add(street['id'])
                for point in street['buildings']:
                    if not isinstance(point, str) or not re.fullmatch(r'[a-z0-9_]{1,64}', point) or point in seen:
                        raise ValueError(f'{key} : bâtiment invalide ou dupliqué.')
                    seen.add(point)
            streets[key] = deepcopy(layout)
    if 'travel_routes' in maps['clearing']:
        routes = deepcopy(maps['clearing']['travel_routes'])
    if not isinstance(routes, list) or not 3 <= len(routes) <= 100:
        raise ValueError('De 3 à 100 chemins rapides requis.')
    seen = set()
    for route in routes:
        if not isinstance(route, dict) or not isinstance(route.get('id'), str) or not re.fullmatch(r'[a-z0-9_]{1,64}', route['id']) or route['id'] in seen or route.get('from') not in maps or route.get('to') not in maps or route['from'] == route['to'] or not isinstance(route.get('name'), str) or not 1 <= len(route['name']) <= 100:
            raise ValueError('Chemin rapide invalide ou dupliqué.')
        if 'bidirectional' in route and type(route['bidirectional']) is not bool:
            raise ValueError('Sens de chemin invalide.')
        distance = route.get('distance_km')
        if type(distance) not in (int, float) or not math.isfinite(distance) or not .0001 <= distance <= 1000:
            raise ValueError('Distance de chemin comprise entre 0.0001 et 1000 km.')
        seen.add(route['id'])
    if not {'clearing_rosee','rosee_lisiere','rosee_brume'} <= seen:
        raise ValueError('Les trois chemins du tutoriel doivent être conservés.')
    return streets, routes


class WorldEditor:
    def __init__(self, editor):
        import tkinter as tk
        from tkinter import ttk, messagebox
        from . import world
        self.editor, self.tk, self.messagebox = editor, tk, messagebox
        self.window = tk.Toplevel(editor.root)
        self.window.title('Trajets et rues')
        self.window.geometry('850x580')
        self.streets, self.routes = world_metadata(editor.maps, world.VILLAGE_STREETS, world.ROUTES)
        self.zone = tk.StringVar(value=editor.selected.get())
        ttk.Label(self.window, text='Les chemins rapides utilisent 6 km/h et le ratio 1:3. Les rues définissent la topologie de la carte générale ; le décor se peint séparément.').pack(fill='x', padx=8, pady=8)
        self.roads = tk.Listbox(self.window, height=6)
        self.roads.pack(fill='x', padx=8)
        bar = ttk.Frame(self.window)
        bar.pack(fill='x')
        for label, command in (('Ajouter un chemin', lambda:self.road(True)),('Modifier le chemin', self.road)):
            ttk.Button(bar,text=label,command=command).pack(side='left')
        choice = ttk.Combobox(self.window,textvariable=self.zone,values=list(editor.maps),state='readonly')
        choice.pack(fill='x',padx=8,pady=8)
        choice.bind('<<ComboboxSelected>>',lambda e:self.refresh())
        self.list = tk.Listbox(self.window,height=8)
        self.list.pack(fill='both',expand=True,padx=8)
        bar = ttk.Frame(self.window)
        bar.pack(fill='x')
        for label, command in (('Ajouter une rue',lambda:self.street(True)),('Modifier la rue',self.street),('Supprimer la rue',self.delete),('↑',lambda:self.reorder(-1)),('↓',lambda:self.reorder(1)),('Place centrale',self.square),('Appliquer',self.apply)):
            ttk.Button(bar,text=label,command=command).pack(side='left')
        self.refresh()

    def refresh(self):
        self.roads.delete(0,'end')
        for route in self.routes:
            seconds = route['distance_km']/6*3600
            self.roads.insert('end',f"{route['name']} [{route['id']}] : {route['from']} → {route['to']} · {route['distance_km']:g} km · {seconds/60:g} min jeu / {seconds/3:g} s réelles")
        self.list.delete(0,'end')
        for street in self.streets.get(self.zone.get(),{}).get('streets',[]):
            self.list.insert('end',f"{street['name']} [{street['id']}] : {', '.join(street['buildings'])}")

    def road(self, new=False):
        selection = self.roads.curselection()
        if not new and not selection:
            return
        index = selection[0] if selection else None
        old = {} if new else self.routes[index]
        minutes = old.get('distance_km',.1)*10
        values = self.editor.form('Chemin rapide',{'route_id':old.get('id',''), 'name':old.get('name','Chemin'), 'from_zone':old.get('from','clearing'), 'to_zone':old.get('to','rosee'), 'distance_km':old.get('distance_km',.1), 'travel_minutes':minutes})
        if not values:
            return
        try:
            distance = float(values['distance_km'])
            if float(values['travel_minutes']) != minutes:
                distance = float(values['travel_minutes'])/10
            item = {**old, 'id':values['route_id'], 'name':values['name'], 'from':values['from_zone'], 'to':values['to_zone'], 'distance_km':distance}
            routes = deepcopy(self.routes)
            if new:
                routes.append(item)
            else:
                routes[index] = item
            candidate = deepcopy(self.editor.maps)
            candidate['clearing']['travel_routes'] = routes
            world_metadata(candidate,self.streets,routes)
            self.routes = routes
            self.refresh()
        except (ValueError, KeyError) as exc:
            self.messagebox.showerror('Trajet',str(exc),parent=self.window)

    def layout(self):
        return self.streets.setdefault(self.zone.get(),{'square':self.zone.get()+'_square','streets':[]})

    def street(self,new=False):
        selection = self.list.curselection()
        if not new and not selection:
            return
        layout = self.layout()
        index = selection[0] if selection else None
        old = {} if new else layout['streets'][index]
        values = self.editor.form('Rue et ordre des bâtiments',{'street_id':old.get('id',''), 'name':old.get('name','Rue'), 'buildings':','.join(old.get('buildings',[]))})
        if values:
            item = {'id':values['street_id'].strip(),'name':values['name'].strip(),'buildings':[v.strip() for v in values['buildings'].split(',') if v.strip()]}
            if new:
                layout['streets'].append(item)
            else:
                layout['streets'][index] = item
            self.refresh()

    def delete(self):
        selection = self.list.curselection()
        if selection:
            self.layout()['streets'].pop(selection[0])
            self.refresh()

    def reorder(self,delta):
        selected = self.list.curselection()
        if not selected:
            return
        items = self.layout()['streets']
        i,j = selected[0],selected[0]+delta
        if 0 <= j < len(items):
            items[i],items[j] = items[j],items[i]
            self.refresh()
            self.list.selection_set(j)

    def square(self):
        layout = self.layout()
        values = self.editor.form('Place centrale',{'square':layout['square']})
        if values:
            layout['square'] = values['square'].strip()

    def apply(self):
        from .map_assets import validate
        candidate = deepcopy(self.editor.maps)
        candidate['clearing']['travel_routes'] = deepcopy(self.routes)
        for key, layout in self.streets.items():
            if key in candidate:
                candidate[key]['village_streets'] = deepcopy(layout)
        try:
            world_metadata(candidate,self.streets,self.routes)
            candidate = validate(candidate)
            self.editor.remember()
            self.editor.maps = candidate
            self.editor.draw()
            self.editor.status.set('Trajets et rues appliqués. Enregistrez et redémarrez le serveur.')
            self.window.destroy()
        except ValueError as exc:
            self.messagebox.showerror('Plan',str(exc),parent=self.window)
