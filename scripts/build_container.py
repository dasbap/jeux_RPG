"""Build delivery files inside Docker; /out is the only artifact destination."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = {
    "windows": (
        ("dist/client/Jeux-RPG.exe", "windows/Jeux-RPG.exe"),
        ("dist/client/Jeux-RPG.exe", "client/Jeux-RPG.exe"),
    ),
    "linux": (
        (
            "dist/linux/Jeux-RPG-Linux-x86_64.AppImage",
            "linux/Jeux-RPG-Linux-x86_64.AppImage",
        ),
        ("dist/linux/Jeux-RPG-Linux-x64.tar.gz", "linux/Jeux-RPG-Linux-x64.tar.gz"),
    ),
    "android": (
        (
            "android/app/build/outputs/apk/release/app-release.apk",
            "mobile/Jeux-RPG-Android.apk",
        ),
    ),
}


def run(*arguments):
    subprocess.run(arguments, cwd=ROOT, check=True)


def build_desktop(target):
    arguments = [
        "node",
        "desktop/node_modules/electron-builder/cli.js",
        "--projectDir",
        "desktop",
        "--" + ("win" if target == "windows" else "linux"),
        "--x64",
        "--publish",
        "never",
    ]
    if target == "linux":
        arguments.append("--config.directories.output=../dist/linux")
    run("xvfb-run", "-a", *arguments)


def build_android():
    signing = ROOT / ".signing/android"
    if not (ROOT / ".signing").is_mount():
        raise RuntimeError("Mount a persistent signing directory at /project/.signing")
    run("python3", "scripts/prepare_android_client.py")
    properties = dict(
        line.split("=", 1)
        for line in (signing / "signing.properties").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    keystore = ROOT / "android" / properties["storeFile"]
    if not keystore.is_file():
        environment = dict(os.environ, RPG_SIGNING_PASSWORD=properties["storePassword"])
        subprocess.run(
            [
                "keytool",
                "-genkeypair",
                "-keystore",
                str(keystore),
                "-alias",
                properties["keyAlias"],
                "-keyalg",
                "RSA",
                "-keysize",
                "3072",
                "-validity",
                "10000",
                "-storepass:env",
                "RPG_SIGNING_PASSWORD",
                "-keypass:env",
                "RPG_SIGNING_PASSWORD",
                "-dname",
                "CN=Jeux RPG, O=Jeux RPG, C=FR",
            ],
            env=environment,
            check=True,
        )
    run(
        ".toolchains/gradle-8.11.1/bin/gradle",
        "-p",
        "android",
        "assembleRelease",
        "--no-daemon",
    )
    run(
        ".toolchains/android-sdk/build-tools/35.0.0/apksigner",
        "verify",
        "--verbose",
        "android/app/build/outputs/apk/release/app-release.apk",
    )


def export_artifacts(targets, output):
    output.mkdir(parents=True, exist_ok=True)
    for target in targets:
        for source, destination in ARTIFACTS[target]:
            path = output / destination
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, path)
    manifest = {}
    for target in ARTIFACTS:
        for _, name in ARTIFACTS[target]:
            if name.startswith("client/"):
                continue
            path = output / name
            if path.is_file():
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                manifest[name] = {"bytes": path.stat().st_size, "sha256": digest}
    (output / "artifacts.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (output / "SHA256SUMS.txt").write_text(
        "".join(f"{value['sha256']}  {name}\n" for name, value in manifest.items()),
        encoding="utf-8",
    )
    shutil.copy2(ROOT / "docs/DISTRIBUTION_LIREMOI.md", output / "LIREMOI.md")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target", choices=[*ARTIFACTS, "all"], default="windows", nargs="?"
    )
    args = parser.parse_args()
    targets = list(ARTIFACTS) if args.target == "all" else [args.target]
    for target in targets:
        build_android() if target == "android" else build_desktop(target)
    export_artifacts(targets, Path("/out"))
    print("Livrables exportés dans /out : " + ", ".join(targets), flush=True)


if __name__ == "__main__":
    main()
