"""Download verified, workspace-local Linux build tools for WSL builds."""

import hashlib
import json
import subprocess
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".toolchains"
DOWNLOADS = TOOLS / "downloads"


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"JeuxRPG-build/1.0"}), timeout=90)


def download(name, url, checksum, algorithm="sha256"):
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    target = DOWNLOADS / name
    if not target.exists():
        print("Downloading " + name, flush=True)
        temporary = target.with_suffix(target.suffix + ".part")
        with request(url) as response, temporary.open("wb") as output:
            while chunk := response.read(1024*1024):
                output.write(chunk)
        temporary.replace(target)
    digest = hashlib.new(algorithm)
    with target.open("rb") as source:
        while chunk := source.read(1024*1024):
            digest.update(chunk)
    if digest.hexdigest().lower() != checksum.lower():
        raise ValueError("Invalid checksum: " + name)
    return target


def wsl_path(path):
    path = Path(path).resolve()
    return "/mnt/" + path.drive[0].lower() + path.as_posix()[2:]


def extract_tar(archive, destination, expected):
    if expected.exists():
        return
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(["wsl.exe","-d","Ubuntu","--","tar","-xf",wsl_path(archive),"-C",wsl_path(destination),"--strip-components=1"], check=True)


def extract_zip(archive, destination, expected):
    if not expected.exists():
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as source:
            source.extractall(destination)


def main():
    TOOLS.mkdir(parents=True, exist_ok=True)
    manifest_path = TOOLS / "platform-tools.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    else:
        assets = json.load(request("https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=linux"))
        jdk = assets[0]["binary"]["package"]
        version = "24.11.1"
        checksums = request(f"https://nodejs.org/dist/v{version}/SHASUMS256.txt").read().decode()
        node_name = f"node-v{version}-linux-x64.tar.xz"
        node_checksum = next(line.split()[0] for line in checksums.splitlines() if line.endswith("  "+node_name))
        manifest = {
            "jdk":{"name":jdk["name"],"url":jdk["link"],"checksum":jdk["checksum"]},
            "node":{"name":node_name,"url":f"https://nodejs.org/dist/v{version}/{node_name}","checksum":node_checksum},
            "gradle":{"name":"gradle-8.11.1-bin.zip","url":"https://services.gradle.org/distributions/gradle-8.11.1-bin.zip","checksum":request("https://services.gradle.org/distributions/gradle-8.11.1-bin.zip.sha256").read().decode().strip()},
        }
        manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf8")
    manifest = {key:value for key,value in manifest.items() if key in ("jdk", "node", "gradle")}
    manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf8")
    for key, value in manifest.items():
        archive = download(value["name"],value["url"],value["checksum"],value.get("algorithm","sha256"))
        if key in ("jdk","node"):
            extract_tar(archive,TOOLS/key,TOOLS/key/"bin"/("java" if key=="jdk" else "node"))
        elif key=="gradle":
            extract_zip(archive,TOOLS,TOOLS/"gradle-8.11.1/bin/gradle")
    print("Local toolchains ready in .toolchains",flush=True)


if __name__ == "__main__":
    main()
