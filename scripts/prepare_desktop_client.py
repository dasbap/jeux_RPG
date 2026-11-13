"""Build the desktop assets from the web client; no installed Python package needed."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for variable in ("RPG_MAPS_FILE", "RPG_CONTENT_FILE", "RPG_CLASSES_FILE"):
    os.environ.pop(variable, None)

from scripts.export_builder_project import export_builder_project  # noqa: E402

export_builder_project(ROOT)

from jeuxRPG.multiplayer.browser_solo_assets import (  # noqa: E402
    PYODIDE_URL,
    client_csp,
    engine_archive,
)
from jeuxRPG.multiplayer.catalogue import catalogue  # noqa: E402

SERVER = "https://jeux-rpg.vercel.app"


def prepare():
    output = ROOT / "desktop" / "assets"
    output.mkdir(parents=True, exist_ok=True)
    web = ROOT / "jeuxRPG" / "multiplayer" / "web"
    classes = catalogue()
    options = "".join(
        f'<option value="{escape(item["id"], quote=True)}">{escape(item["name"])}</option>'
        for item in classes
    )
    # Only assets referenced by the public client, never admin pages or local files.
    index = (web / "index.html").read_text(encoding="utf-8")
    names = set(re.findall(r'(?:src|href)="/([a-z_]+\.(?:js|css))"', index))
    names.update(("solo_worker.js", "index.html"))
    hashes = {}
    for name in sorted(names):
        content = (web / name).read_text(encoding="utf-8")
        hashes[name] = hashlib.sha256(content.encode()).hexdigest()
        if name == "index.html":
            content = content.replace("{{CLASS_OPTIONS}}", options).replace(
                "</head>",
                f'<meta name="rpg-realtime-url" content="{SERVER}/api/ws">\n</head>',
            )
        elif name == "solo_worker.js":
            if PYODIDE_URL not in content:
                raise ValueError(
                    "La version Pyodide du Worker a changé : adapter le build."
                )
            content = content.replace(PYODIDE_URL, "/vendor/pyodide/")
        elif name == "app_modes.js":
            content = content.replace(
                "La première ouverture nécessite Internet.",
                "Le moteur est installé sur cet appareil.",
            )
        (output / name).write_text(content, encoding="utf-8")
    (output / "solo-engine.zip").write_bytes(engine_archive())
    (output / "classes.json").write_text(json.dumps(classes), encoding="utf-8")
    pyodide = ROOT / "desktop" / "node_modules" / "pyodide"
    version = json.loads((pyodide / "package.json").read_text(encoding="utf-8"))[
        "version"
    ]
    if f"v{version}/full/" not in PYODIDE_URL:
        raise ValueError("Les versions Pyodide du site et de l'application diffèrent.")
    vendor = output / "vendor" / "pyodide"
    vendor.mkdir(parents=True, exist_ok=True)
    for name in (
        "pyodide.mjs",
        "pyodide.mjs.map",
        "pyodide.asm.mjs",
        "pyodide.asm.wasm",
        "pyodide-lock.json",
        "python_stdlib.zip",
    ):
        shutil.copyfile(pyodide / name, vendor / name)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    manifest = {
        "server": SERVER,
        "commit": commit,
        "web_assets": hashes,
        "pyodide": version,
        "csp": client_csp("/").replace(
            PYODIDE_URL, f"{SERVER} {SERVER.replace('https:', 'wss:')}"
        ),
        "worker_csp": client_csp("/solo_worker.js").replace(PYODIDE_URL, ""),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(
        f"Client web embarqué : {len(names)} fichiers, moteur Python et Pyodide {version}."
    )


if __name__ == "__main__":
    prepare()
