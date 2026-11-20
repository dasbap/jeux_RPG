"""Install only the Android/Gradle archives locked in this repository."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / ".toolchains"


def install_archive(specification, destination, strip_prefix=False):
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile() as archive:
        request = urllib.request.Request(
            specification["url"], headers={"User-Agent": "JeuxRPG-build/1.0"}
        )
        digest = hashlib.new(specification["algorithm"])
        with urllib.request.urlopen(request, timeout=120) as response:
            while chunk := response.read(1024 * 1024):
                archive.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != specification["checksum"]:
            raise ValueError("Invalid archive checksum: " + specification["url"])
        archive.seek(0)
        with zipfile.ZipFile(archive) as bundle:
            prefixes = {name.split("/", 1)[0] for name in bundle.namelist()}
            if strip_prefix and len(prefixes) != 1:
                raise ValueError("Expected a single SDK archive root")
            for entry in bundle.infolist():
                name = entry.filename
                if strip_prefix:
                    name = name.partition("/")[2]
                if not name or entry.is_dir():
                    continue
                target = destination / name
                if not target.resolve().is_relative_to(destination.resolve()):
                    raise ValueError("Invalid archive path")
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(entry) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod((entry.external_attr >> 16) & 0o777 or 0o644)


def main():
    lock = json.loads(Path(__file__).with_name("tools.lock.json").read_text())
    install_archive(lock["gradle"], TOOLS)
    sdk = TOOLS / "android-sdk"
    for name, specification in lock["android"].items():
        install_archive(specification, sdk.joinpath(*name.split(";")), True)
    sdkmanager = sdk / "cmdline-tools/19.0/bin/sdkmanager"
    subprocess.run(
        [str(sdkmanager), f"--sdk_root={sdk}", "--licenses"],
        input="y\n" * 100,
        text=True,
        check=True,
    )


if __name__ == "__main__":
    main()
