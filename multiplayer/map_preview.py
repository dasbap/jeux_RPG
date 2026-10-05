import json
from pathlib import Path
import tempfile
import webbrowser



def rotate_bridge(data, point, rotation=None):
    from copy import deepcopy
    if point not in data.get('bridges', []):
        raise ValueError('Sélectionnez une case de pont.')
    previous = next((item['rotation'] for item in data.get('bridge_rotations', []) if item['position'] == point), 0)
    angle = (previous + 90) % 360 if rotation is None else rotation
    if type(angle) is not int or angle not in (0,90,180,270):
        raise ValueError('Rotation : 0, 90, 180 ou 270 degrés.')
    result = deepcopy(data)
    result['bridge_rotations'] = [item for item in result.get('bridge_rotations', []) if item['position'] != point] + [{'position':point[:], 'rotation':angle}]
    return result


def preview_html(maps, selected):
    web = Path(__file__).parent/'web'
    encoded = json.dumps({'maps':maps,'selected':selected},ensure_ascii=False).replace('<','\\u003c')
    style = (web/'style.css').read_text(encoding='utf-8')
    artwork = (web/'map_artwork.js').read_text(encoding='utf-8')
    return '''<!doctype html><html lang="fr"><meta charset="utf-8"><title>Aperçu du builder</title><style>'''+style+'''
body{padding:12px}header{flex-wrap:wrap}#scene{height:calc(100vh - 110px)}#scene svg{height:100%;max-height:none;border-radius:0;touch-action:none}select{width:auto;max-width:45vw}label{display:flex;align-items:center;gap:8px}input{width:auto}button{padding:7px 12px}p{margin:6px 0;font-size:.85rem}
</style><header><select id="map" aria-label="Carte"></select><button id="less">−</button><button id="more">+</button><button id="reset">Vue entière</button><label><input type="checkbox" id="markers" checked>Repères PNJ / spawns / TP</label></header><p>Rendu du terrain en jeu · aperçu figé des modifications courantes · molette pour zoomer, glisser pour déplacer la vue.</p><div id="scene"></div><script type="application/json" id="snapshot">'''+encoded+'''</script><script>'''+artwork+'''
const snapshot = JSON.parse(document.getElementById("snapshot").textContent);
const choice = document.getElementById("map"), scene = document.getElementById("scene");
for (const [id,map] of Object.entries(snapshot.maps)) { const option = document.createElement("option"); option.value=id; option.textContent=map.name+" ["+id+"]"; choice.append(option); }
choice.value=snapshot.selected;
let camera, dragging;
function view() { scene.querySelector("svg").setAttribute("viewBox", `${camera.x-camera.width/2} ${camera.y-camera.height/2} ${camera.width} ${camera.height}`); }
function draw() { const map=snapshot.maps[choice.value]; scene.replaceChildren(renderStaticMap(map,document.getElementById("markers").checked)); camera={x:map.width*20,y:map.height*20,width:map.width*40,height:map.height*40}; view(); }
function zoom(factor) { const map=snapshot.maps[choice.value]; camera.width=Math.max(80,Math.min(map.width*40,camera.width*factor)); camera.height=camera.width*map.height/map.width; view(); }
choice.onchange=draw; document.getElementById("markers").onchange=draw;
document.getElementById("more").onclick=()=>zoom(.8); document.getElementById("less").onclick=()=>zoom(1.25); document.getElementById("reset").onclick=draw;
scene.onwheel=event=>{event.preventDefault();zoom(event.deltaY>0?1.25:.8);};
scene.onpointerdown=event=>{ dragging=[event.clientX,event.clientY,camera.x,camera.y];scene.setPointerCapture(event.pointerId);};
scene.onpointermove=event=>{if(!dragging)return;const svg=scene.querySelector("svg"), point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;const current=point.matrixTransform(svg.getScreenCTM().inverse());point.x=dragging[0];point.y=dragging[1];const start=point.matrixTransform(svg.getScreenCTM().inverse());camera.x=dragging[2]-(current.x-start.x);camera.y=dragging[3]-(current.y-start.y);view();};
scene.onpointerup=()=>{dragging=null;};scene.onpointercancel=()=>{dragging=null;};draw();
</script></html>'''


def open_preview(maps, selected):
    path = Path(tempfile.mkdtemp(prefix='rpg-map-preview-'))/'preview.html'
    path.write_text(preview_html(maps,selected),encoding='utf-8')
    webbrowser.open(path.as_uri())
    return path
