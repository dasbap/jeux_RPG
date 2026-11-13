"""Package the prepared desktop engine and web client for the Android host."""
import hashlib
import json
import re
import secrets
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "desktop/assets"
    destination = ROOT / "android/app/src/main/assets/web"
    shutil.copytree(source, destination, dirs_exist_ok=True)
    shutil.copy2(ROOT / "android/mobile_bridge.js", destination / "mobile_bridge.js")
    html = (destination / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'<meta name="rpg-realtime-url"[^>]*>\s*', "", html)
    html = html.replace('<script src="/map_artwork.js"', '<script src="/mobile_bridge.js" defer></script>\n  <script src="/map_artwork.js"', 1)
    (destination / "index.html").write_text(html, encoding="utf-8")
    worker_path = destination / "solo_worker.js"
    worker = worker_path.read_text(encoding="utf-8")
    marker = 'if (payload.path.startsWith("/api/account/")) await save();'
    if worker.count(marker) != 1:
        raise RuntimeError("Le point de sauvegarde du moteur solo a changé.")
    worker = worker.replace(marker, 'if (payload.path.startsWith("/api/account/") || (payload.path === "/api/commands" && result.status === 200)) await save();')
    worker_path.write_text(worker, encoding="utf-8")
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in (*manifest["web_assets"], "mobile_bridge.js"):
        manifest["web_assets"][name] = hashlib.sha256((destination / name).read_bytes()).hexdigest()
    manifest["platform"] = "android"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    signing = ROOT / ".signing/android/signing.properties"
    signing.parent.mkdir(parents=True, exist_ok=True)
    if not signing.exists():
        password = secrets.token_urlsafe(32)
        signing.write_text("storeFile=../.signing/android/jeux-rpg.jks\nstorePassword=" + password + "\nkeyAlias=jeux-rpg\nkeyPassword=" + password + "\n", encoding="utf-8", newline="\n")
    print("Android : ressources locales et sauvegarde préparées.")


if __name__ == "__main__":
    main()
