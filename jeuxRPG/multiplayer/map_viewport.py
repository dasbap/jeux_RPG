def zoom_canvas(canvas, old_scale, new_scale, draw, x=None, y=None):
    x = canvas.winfo_width()/2 if x is None else x
    y = canvas.winfo_height()/2 if y is None else y
    world_x, world_y = canvas.canvasx(x)/old_scale, canvas.canvasy(y)/old_scale
    draw()
    left, top, right, bottom = map(float, canvas.cget('scrollregion').split())
    canvas.xview_moveto((world_x*new_scale-x-left)/max(1, right-left))
    canvas.yview_moveto((world_y*new_scale-y-top)/max(1, bottom-top))


def assembly_bounds(maps, layout, previous=None):
    left = min(0, *(position[0]-100 for position in layout.values()))
    top = min(0, *(position[1]-100 for position in layout.values()))
    right = max(200, *(layout[key][0]+data['width']+100 for key, data in maps.items()))
    bottom = max(150, *(layout[key][1]+data['height']+100 for key, data in maps.items()))
    if previous:
        left, top, right, bottom = min(left, previous[0]), min(top, previous[1]), max(right, previous[2]), max(bottom, previous[3])
    return left, top, right, bottom
