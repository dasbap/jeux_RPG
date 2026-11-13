"""A Windows-only build updates the executable players launch from dist/windows."""

import hashlib
import json

from scripts import build_distribution


def test_windows_finalize_needs_no_android_or_linux_build(tmp_path, monkeypatch):
    monkeypatch.setattr(build_distribution, "ROOT", tmp_path)
    client = tmp_path / "dist/client/Jeux-RPG.exe"
    client.parent.mkdir(parents=True)
    client.write_bytes(b"new client with Builder maps")
    windows = tmp_path / "dist/windows/Jeux-RPG.exe"
    windows.parent.mkdir()
    windows.write_bytes(b"previous client")
    guide = tmp_path / "docs/DISTRIBUTION_LIREMOI.md"
    guide.parent.mkdir()
    guide.write_text("Windows", encoding="utf8")
    build_distribution.finalize()
    assert windows.read_bytes() == client.read_bytes()
    manifest = json.loads((tmp_path / "dist/artifacts.json").read_text(encoding="utf8"))
    assert list(manifest) == ["windows/Jeux-RPG.exe"]
    assert (
        manifest["windows/Jeux-RPG.exe"]["sha256"]
        == hashlib.sha256(client.read_bytes()).hexdigest()
    )
