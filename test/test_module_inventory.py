import importlib
from pathlib import Path

import pytest
import jeuxRPG

root = Path(jeuxRPG.__file__).parent
modules = sorted("jeuxRPG." + ".".join(path.relative_to(root).with_suffix("").parts) for path in root.rglob("*.py") if path.name not in {"__init__.py", "__main__.py"})


@pytest.mark.parametrize("module", modules)
def test_each_module_imports(module):
    importlib.import_module(module)
