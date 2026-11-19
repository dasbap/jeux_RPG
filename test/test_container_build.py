"""Delivery exports use only the selected container artifacts and retain hashes."""

import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pytest

from scripts import build_container


def test_export_preserves_other_platforms_and_updates_windows(tmp_path, monkeypatch):
    root = tmp_path / "container"
    output = tmp_path / "output"
    client = root / "dist/client/Jeux-RPG.exe"
    client.parent.mkdir(parents=True)
    client.write_bytes(b"fresh container client")
    guide = root / "docs/DISTRIBUTION_LIREMOI.md"
    guide.parent.mkdir()
    guide.write_text("Guide", encoding="utf-8")
    previous = output / "mobile/Jeux-RPG-Android.apk"
    previous.parent.mkdir(parents=True)
    previous.write_bytes(b"existing Android")
    monkeypatch.setattr(build_container, "ROOT", root)
    build_container.export_artifacts(["windows"], output)
    assert (output / "windows/Jeux-RPG.exe").read_bytes() == client.read_bytes()
    assert (output / "client/Jeux-RPG.exe").read_bytes() == client.read_bytes()
    assert previous.read_bytes() == b"existing Android"
    manifest = json.loads((output / "artifacts.json").read_text())
    assert len(manifest) == 2
    for name, entry in manifest.items():
        content = (output / name).read_bytes()
        assert entry == {
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        assert f"{entry['sha256']}  {name}\n" in (output / "SHA256SUMS.txt").read_text()


def test_android_refuses_ephemeral_signing_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(build_container, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="persistent signing"):
        build_container.build_android()


@pytest.fixture
def installer():
    filename = Path(__file__).resolve().parents[1] / "deploy/build/install_tools.py"
    specification = importlib.util.spec_from_file_location("install_tools", filename)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def archive_bytes(name="sdk/bin/sdkmanager"):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        entry = zipfile.ZipInfo(name)
        entry.external_attr = 0o100755 << 16
        archive.writestr(entry, b"sdk tool")
    return output.getvalue()


def test_locked_archive_rejects_corruption_before_extracting(
    installer, tmp_path, monkeypatch
):
    content = archive_bytes()
    monkeypatch.setattr(
        installer.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(content)
    )
    specification = {
        "url": "https://example.test/sdk.zip",
        "algorithm": "sha256",
        "checksum": "0" * 64,
    }
    with pytest.raises(ValueError, match="checksum"):
        installer.install_archive(specification, tmp_path, True)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "name,valid", [("sdk/bin/sdkmanager", True), ("sdk/../../escaped", False)]
)
def test_locked_archive_checks_paths_and_strips_root(
    installer, tmp_path, monkeypatch, name, valid
):
    content = archive_bytes(name)
    monkeypatch.setattr(
        installer.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(content)
    )
    specification = {
        "url": "https://example.test/sdk.zip",
        "algorithm": "sha256",
        "checksum": hashlib.sha256(content).hexdigest(),
    }
    if valid:
        installer.install_archive(specification, tmp_path, True)
        assert (tmp_path / "bin/sdkmanager").read_bytes() == b"sdk tool"
    else:
        with pytest.raises(ValueError, match="archive path"):
            installer.install_archive(specification, tmp_path, True)
