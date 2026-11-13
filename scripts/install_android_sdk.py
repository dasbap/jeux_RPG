"""Install verified SDK archives natively, avoiding slow WSL/NTFS file moves."""
import hashlib
import json
import shutil
import sys
import xml.dom.minidom as DOM
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from prepare_platform_toolchains import download, request

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / ".toolchains/android-sdk"


def install(specification):
    key, package, base = specification
    archive = next(item for item in package.iter("archive") if item.findtext("host-os") in (None, "linux"))
    complete = archive.find("complete")
    url = base + complete.findtext("url")
    checksum = complete.find("checksum")
    source = download(url.rsplit("/", 1)[-1], url, checksum.text, checksum.get("type", "sha1"))
    destination = SDK.joinpath(*key.split(";"))
    print("Installing " + key, flush=True)
    with zipfile.ZipFile(source) as bundle:
        prefixes = {name.split("/", 1)[0] for name in bundle.namelist() if name and not name.startswith("__MACOSX/")}
        strip = len(prefixes) == 1
        for entry in bundle.infolist():
            name = entry.filename.split("/", 1)[1] if strip and "/" in entry.filename else entry.filename
            if not name or entry.is_dir():
                continue
            target = destination / name
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Invalid SDK archive path")
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(entry) as source_file, target.open("wb") as output:
                shutil.copyfileobj(source_file, output)
    return key, {"url": url, "checksum": checksum.text}


def write_sdk_metadata(repositories, selected):
    # Legacy SDK readers require package.xml for emulator/system-image discovery.
    for _, location in repositories:
        filename = "sys-img2-1.xml" if "sys-img/" in location else "repository2-1.xml"
        remote = DOM.parseString(request(location + filename).read())
        for item in remote.documentElement.childNodes:
            if item.nodeType != item.ELEMENT_NODE or item.localName != "remotePackage":
                continue
            key = item.getAttribute("path")
            if key not in selected:
                continue
            # Match the exact stable revision selected above.
            revision = item.getElementsByTagName("revision")[0]
            version = tuple(int(revision.getElementsByTagName(part)[0].firstChild.nodeValue) if revision.getElementsByTagName(part) else 0 for part in ("major", "minor", "micro"))
            if version != selected[key][0] or revision.getElementsByTagName("preview"):
                continue
            document = DOM.Document()
            root = document.createElementNS("http://schemas.android.com/repository/android/common/02", "local:repository")
            root.setAttribute("xmlns:local", "http://schemas.android.com/repository/android/common/02")
            for name, value in remote.documentElement.attributes.items():
                if name.startswith("xmlns:"):
                    value = {
                        "http://schemas.android.com/repository/android/generic/01": "http://schemas.android.com/repository/android/generic/02",
                        "http://schemas.android.com/sdk/android/repo/repository2/01": "http://schemas.android.com/sdk/android/repo/repository2/03",
                        "http://schemas.android.com/sdk/android/repo/sys-img2/01": "http://schemas.android.com/sdk/android/repo/sys-img2/04",
                    }.get(value, value)
                    root.setAttribute(name, value)
            document.appendChild(root)
            for license_node in remote.documentElement.childNodes:
                if license_node.nodeType == license_node.ELEMENT_NODE and license_node.localName == "license":
                    root.appendChild(document.importNode(license_node, True))
            local = document.importNode(item, True)
            document.renameNode(local, None, "localPackage")
            local.setAttribute("obsolete", "false")
            for child in list(local.childNodes):
                if child.nodeType == child.ELEMENT_NODE and child.localName in ("archives", "channelRef"):
                    local.removeChild(child)
            root.appendChild(local)
            SDK.joinpath(*key.split(";"), "package.xml").write_text(document.toxml(), encoding="utf-8")


def main():
    base = "https://dl.google.com/android/repository/"
    repositories = [(ET.fromstring(request(base + "repository2-1.xml").read()), base)]
    keys = {"platform-tools", "platforms;android-35", "build-tools;35.0.0", "cmdline-tools;19.0"}
    if "--with-emulator" in sys.argv:
        keys.update({"emulator", "system-images;android-35;google_apis;x86_64"})
        image_base = "https://dl.google.com/android/repository/sys-img/google_apis/"
        repositories.append((ET.fromstring(request(image_base + "sys-img2-1.xml").read()), image_base))
    selected = {}
    for repository, location in repositories:
        for item in repository:
            if item.tag.endswith("license"):
                directory = SDK / "licenses"
                directory.mkdir(parents=True, exist_ok=True)
                license_hash = hashlib.sha1((item.text or "").strip().encode()).hexdigest()
                (directory / item.get("id")).write_text(license_hash + "\n", encoding="utf-8", newline="\n")
            if item.tag.endswith("remotePackage") and item.get("path") in keys:
                channel = item.find("channelRef")
                if channel is not None and channel.get("ref") != "channel-0":
                    continue
                revision = item.find("revision")
                if revision.find("preview") is not None:
                    continue
                version = tuple(int(revision.findtext(part, "0")) for part in ("major", "minor", "micro"))
                key = item.get("path")
                if key not in selected or version > selected[key][0]:
                    selected[key] = (version, item, location)
    tasks = [(key, item, location) for key, (_, item, location) in selected.items()]
    if {key for key, _, _ in tasks} != keys:
        raise ValueError("Required SDK package not found")
    if "--metadata-only" not in sys.argv:
        with ThreadPoolExecutor(max_workers=3) as pool:
            manifest = dict(pool.map(install, tasks))
        (ROOT / ".toolchains/android-packages.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_sdk_metadata(repositories, selected)
    print("Android SDK ready.", flush=True)


if __name__ == "__main__":
    main()
