from copy import deepcopy

from .map_assets import validate
from . import tactics


def objects_at(data, point):
    result = []
    for field in ('sites', 'exits', 'spawners', 'decorations'):
        for index, item in enumerate(data.get(field, [])):
            if item['position'] == point:
                result.append((f"{field} · {item.get('name', item.get('kind', item.get('mob_id', index)))}", field, index, None))
            if field == 'spawners':
                for step, waypoint in enumerate(item.get('patrol', [])):
                    if waypoint == point:
                        result.append((f"Patrouille {index+1} · point {step+1}", field, index, step))
    for index, position in enumerate(data.get('spawns', [])):
        if position == point and not any(item['position'] == point for item in data.get('spawners', [])):
            result.append((f'Spawn {index+1}', 'spawns', index, None))
    return result


def move_object(maps, map_id, field, index, waypoint, point):
    result = deepcopy(maps)
    data = result[map_id]
    if not tactics.walkable(data, point):
        raise ValueError('Destination impraticable.')
    item = data[field][index]
    if field == 'spawns':
        data[field][index] = point[:]
    elif waypoint is not None:
        item['patrol'][waypoint] = point[:]
    else:
        old = item['position'][:]
        item['position'] = point[:]
        if field == 'spawners':
            data['spawns'][data['spawns'].index(old)] = point[:]
            dx, dy = point[0]-old[0], point[1]-old[1]
            item['patrol'] = [[x+dx, y+dy] for x, y in item.get('patrol', [])]
        elif field == 'decorations' and old in data.get('cover', []):
            data['cover'].remove(old)
            data['cover'].append(point[:])
    return validate(result)


def place_portal(maps, source, point, destination, entry, name, reverse=None, returning=None, fast_destination=None):
    result = deepcopy(maps)
    if not name.strip() or not tactics.walkable(result[source], point):
        raise ValueError('Nom et case de départ praticable requis.')
    if destination:
        if destination not in result or not tactics.walkable(result[destination], entry):
            raise ValueError('Arrivée impraticable.')
        if entry in [g['position'] for g in result[destination]['exits']] or destination == source and entry == point:
            raise ValueError('L’arrivée ne doit pas être sur un TP : risque de boucle.')
    gate = {'position': point[:], 'name': name.strip(), 'destination': destination or None, 'entry': entry[:] if destination else None}
    if fast_destination and not destination:
        gate['fast_destination'] = fast_destination
    result[source]['exits'] = [g for g in result[source]['exits'] if g['position'] != point] + [gate]
    if reverse is not None:
        if not destination or destination == source or reverse == entry or returning == point:
            raise ValueError('Le retour et les arrivées doivent être sur des cases distinctes.')
        if not tactics.walkable(result[destination], reverse) or not tactics.walkable(result[source], returning):
            raise ValueError('Retour impraticable.')
        if returning in [g['position'] for g in result[source]['exits']]:
            raise ValueError('L’arrivée du retour ne doit pas être sur un TP.')
        result[destination]['exits'] = [g for g in result[destination]['exits'] if g['position'] != reverse] + [{'position': reverse[:], 'name': 'Retour · '+name.strip(), 'destination': source, 'entry': returning[:]}]
    return validate(result)


def pick_cell(editor, title, fixed_map=None):
    import tkinter as tk
    from tkinter import ttk
    from .editor_ui import EditorPanel
    panel = EditorPanel(editor.root, title)
    window = panel.content
    selected = tk.StringVar(value=fixed_map or editor.selected.get())
    bar = ttk.Frame(window)
    bar.pack(fill='x')
    choice = ttk.Combobox(bar, textvariable=selected, values=list(editor.maps), state='disabled' if fixed_map else 'readonly', width=40)
    choice.pack(side='left')
    ttk.Label(bar, text='Cliquez une case praticable. Les coordonnées sont locales.').pack(side='left', padx=8)
    frame = ttk.Frame(window)
    frame.pack(fill='both', expand=True)
    canvas = tk.Canvas(frame, background='#15201b')
    canvas.grid(row=0, column=0, sticky='nsew')
    xs = ttk.Scrollbar(frame, orient='horizontal', command=canvas.xview)
    ys = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
    xs.grid(row=1, column=0, sticky='ew')
    ys.grid(row=0, column=1, sticky='ns')
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    canvas.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
    size = [24]
    answer = []
    def draw(event=None):
        canvas.delete('all')
        data = editor.maps[selected.get()]
        s = size[0]
        canvas.configure(scrollregion=(0,0,data['width']*s,data['height']*s))
        water, bridges, paths = ({tuple(p) for p in data.get(field, [])} for field in ('water', 'bridges', 'paths'))
        for y in range(data['height']):
            for x in range(data['width']):
                color = '#353b43' if not tactics.walkable(data, [x,y]) else '#b19768' if (x,y) in paths else '#537347'
                if (x,y) in water:
                    color = '#357c94'
                if (x,y) in bridges:
                    color = '#ba9960'
                canvas.create_rectangle(x*s,y*s,(x+1)*s,(y+1)*s,fill=color,outline='#71806b')
        for field, mark, color in (('exits','↗','#80e9ff'),('sites','N','#ffe080'),('spawners','G','#ff7777')):
            for item in data.get(field, []):
                x,y = item['position']
                canvas.create_text((x+.5)*s,(y+.5)*s,text=mark,fill=color)
    def click(event):
        point = [int(canvas.canvasx(event.x)//size[0]), int(canvas.canvasy(event.y)//size[0])]
        if tactics.walkable(editor.maps[selected.get()], point):
            answer.append((selected.get(), point))
            panel.destroy()
    def zoom(delta):
        size[0] = max(12,min(48,size[0]+delta))
        draw()
    ttk.Button(bar, text='−', command=lambda:zoom(-4)).pack(side='left')
    ttk.Button(bar, text='+', command=lambda:zoom(4)).pack(side='left')
    ttk.Button(bar, text='Annuler', command=panel.destroy).pack(side='left')
    choice.bind('<<ComboboxSelected>>', draw)
    canvas.bind('<Button-1>', click)
    draw()
    editor.root.wait_window(panel)
    return answer[0] if answer else None
