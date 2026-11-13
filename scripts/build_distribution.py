"""Build the three local distributions from one Builder content export."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*arguments):
    subprocess.run(arguments, cwd=ROOT, check=True)


def wsl(script):
    location = ROOT.as_posix()
    linux_root = "/mnt/" + location[0].lower() + location[2:]
    run("wsl", "-d", "Ubuntu", "--", "bash", linux_root + "/scripts/" + script)


def finalize():
    windows = ROOT / "dist/windows"
    windows.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "dist/client/Jeux-RPG.exe", windows / "Jeux-RPG.exe")
    paths = [windows / "Jeux-RPG.exe", ROOT / "dist/mobile/Jeux-RPG-Android.apk",
             ROOT / "dist/linux/Jeux-RPG-Linux-x86_64.AppImage", ROOT / "dist/linux/Jeux-RPG-Linux-x64.tar.gz"]
    manifest = {}
    for path in paths:
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        manifest[path.relative_to(ROOT / "dist").as_posix()] = {"bytes": path.stat().st_size, "sha256": digest}
    (ROOT / "dist/SHA256SUMS.txt").write_text("".join(value["sha256"] + "  " + name + "\n" for name, value in manifest.items()), encoding="utf-8")
    (ROOT / "dist/artifacts.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.copy2(ROOT / "docs/DISTRIBUTION_LIREMOI.md", ROOT / "dist/LIREMOI.md")
    print("Distributions disponibles dans dist : " + ", ".join(manifest))


def main():
    if "--finalize-only" not in sys.argv:
        if os.name != "nt":
            raise SystemExit("Cette commande orchestre Windows et WSL depuis Windows.")
        os.environ["PYTHON"] = sys.executable
        run(sys.executable, "scripts/prepare_platform_toolchains.py")
        run("node", "desktop/build.cjs")
        wsl("build-linux.sh")
        run(sys.executable, "scripts/install_android_sdk.py")
        run(sys.executable, "scripts/prepare_android_client.py")
        wsl("build-android.sh")
    finalize()


if __name__ == "__main__":
    main()
