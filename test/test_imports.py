import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pkgutil
import importlib
import pytest

import jeuxRPG


def test_import_all_submodules():
    """Tentative d'importation de tous les sous-modules de `jeuxRPG`.

    Ce test échoue si un module lève une exception à l'import, ce qui aide
    à détecter les erreurs de syntaxe ou les effets de bord sur import.
    """
    package = jeuxRPG
    failures = []
    for finder, name, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
        try:
            importlib.import_module(name)
        except Exception as e:
            failures.append((name, e))

    if failures:
        msgs = [f"{n}: {type(e).__name__}: {e}" for n, e in failures]
        pytest.fail("Some modules failed to import:\n" + "\n".join(msgs))


def test_runtime_has_single_physical_source_tree():
    root = Path(__file__).parent.parent
    for name in ('_balance', '_class', '_core', '_function', 'game_engine', 'i18n', 'maps', 'multiplayer'):
        assert not (root / name).exists(), f'{name} doit exister uniquement sous jeuxRPG/'
    assert Path(jeuxRPG.__file__).resolve().parent == (root / 'jeuxRPG').resolve()
    assert list(jeuxRPG.__path__) == [str((root / 'jeuxRPG').resolve())]
