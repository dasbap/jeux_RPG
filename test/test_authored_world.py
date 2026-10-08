from pathlib import Path


def test_published_world_supports_five_classes_and_forty_players():
    import os
    import subprocess
    import sys
    root = Path(__file__).resolve().parent.parent
    environment = {**os.environ, 'RPG_MAPS_FILE': str(root / 'maps')}
    result = subprocess.run([sys.executable, '-m', 'scripts.verify_authored_runtime'], cwd=root, env=environment, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
