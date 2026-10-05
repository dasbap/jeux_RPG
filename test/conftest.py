"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

import os

os.environ.setdefault("RPG_MAPS_FILE", str(Path(__file__).parent / "fixtures" / "reference_world"))
