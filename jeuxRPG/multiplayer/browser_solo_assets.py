import io
import zipfile
from functools import lru_cache
from pathlib import Path

PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/"


@lru_cache(maxsize=1)
def engine_archive():
    root = Path(__file__).resolve().parents[1]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if (
                path.is_file()
                and not path.is_symlink()
                and path.suffix in (".py", ".json", ".sql")
            ):
                archive.write(path, path.relative_to(root.parent).as_posix())
    return output.getvalue()


def client_csp(path):
    if path.split("?", 1)[0] == "/solo_worker.js":
        return f"default-src 'none'; script-src 'self' 'wasm-unsafe-eval' {PYODIDE_URL}; connect-src 'self' {PYODIDE_URL}; worker-src 'self'; base-uri 'none'"
    return "default-src 'none'; script-src 'self'; worker-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
