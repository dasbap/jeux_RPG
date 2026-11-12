import os
from pathlib import Path
import subprocess
import sys


def test_delivered_optional_content_and_rosee_forge():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/verify_optional_content.py")],
        cwd=root, env={**os.environ, "PYTHONIOENCODING":"utf-8"},
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
