from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeuxRPG.multiplayer.map_assets import validate
from jeuxRPG.multiplayer.map_preview import rotate_bridge, preview_html
from jeuxRPG.multiplayer.map_building import sync_overlap
from jeuxRPG.multiplayer.map_assembly import merge, align


def maps():
    return json.loads((Path(__file__).parent/'fixtures'/'fields.json').read_text())


def test_bridge_rotation_is_independent_and_cycles_without_changing_collision():
    data = maps()['clearing']
    original = deepcopy(data)
    point = data['bridges'][0]
    for angle in (90,180,270,0):
        data = rotate_bridge(data,point)
        assert data['bridge_rotations'][0]['rotation'] == angle
        assert data['cover'] == original['cover']
        assert data['blocked'] == original['blocked']
        assert data['bridges'] == original['bridges']
    assert 'bridge_rotations' not in original


@pytest.mark.parametrize('config', [lambda d:[{'position':[0,0],'rotation':90}], lambda d:[{'position':d['bridges'][0],'rotation':45}], lambda d:[{'position':d['bridges'][0],'rotation':True}], lambda d:[{'position':d['bridges'][0],'rotation':90}]*2])
def test_invalid_bridge_orientation_is_rejected(config):
    data = maps()
    data['clearing']['bridge_rotations'] = config(data['clearing'])
    with pytest.raises(ValueError):
        validate(data)


def test_bridge_orientation_survives_overlap_sync():
    data = maps()
    source = data['clearing']
    source['bridges'].append([26,10])
    source['bridge_rotations'] = [{'position':[26,10],'rotation':90}]
    sync_overlap(data,'clearing')
    assert {'position':[0,10],'rotation':90} in data['clearing_trail']['bridge_rotations']
    validate(data)


def test_bridge_orientation_survives_merge_offsets():
    data = maps()
    data['cave_2']['bridges'] = [[3,7]]
    data['cave_2']['bridge_rotations'] = [{'position':[3,7],'rotation':270}]
    data = align(data,'cave_2','cave_1','est',0)
    merged = merge(data,'cave_1','cave_2')
    assert {'position':[25,7],'rotation':270} in merged['cave_1']['bridge_rotations']


def test_preview_is_self_contained_and_escapes_map_text():
    data = maps()
    data['clearing']['name'] = '</script><script>alert(1)</script>'
    html = preview_html(data,'clearing')
    assert '</script><script>alert(1)' not in html
    assert 'renderStaticMap' in html
    assert 'patternTransform' in html
    assert 'river-bridge-' in html
    assert 'src="http' not in html
    assert 'snapshot' in html
