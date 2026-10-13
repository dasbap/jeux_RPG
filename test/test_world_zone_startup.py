import os
from pathlib import Path
import subprocess
import sys


def test_packaged_world_starts_and_can_spawn_combat_in_logical_zone():
    root = Path(__file__).resolve().parent.parent
    environment = {**os.environ, "RPG_MAPS_FILE": str(root / "jeuxRPG" / "maps")}
    source = '''
from jeuxRPG.multiplayer import tutorial, world
party = tutorial.new_party([{'id': 'p', 'name': 'Test', 'class_name': 'Knight'}])
view = tutorial.view(party, 'p', 0)
assert view['world']['current'] == 'foret_eveilles'
assert all(key in world.PLACES or key in world.ROAD_POINTS or any(p['id'] == key for place in world.PLACES.values() for p in place['points']) for key in view['world']['graph'])
tutorial.spawn(party, 0, lambda: .2, [], origin='explore')
assert party['battle']['preset'] == 'field_clearing'
'''
    result = subprocess.run([sys.executable, '-c', source], cwd=root, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
