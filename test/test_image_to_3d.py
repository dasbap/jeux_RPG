import json
import math
import struct
from pathlib import Path

import pytest

from scripts.image_to_3d import convert, relief_mesh, sprite_pixels, write_glb


def read_glb(path):
    raw = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", raw)
    assert (magic, version, length) == (b"glTF", 2, len(raw))
    size, kind = struct.unpack_from("<I4s", raw, 12)
    assert kind == b"JSON" and size % 4 == 0
    data = json.loads(raw[20 : 20 + size])
    count, kind = struct.unpack_from("<I4s", raw, 20 + size)
    assert kind == b"BIN\0"
    binary = raw[28 + size :]
    assert count == len(binary) == data["buffers"][0]["byteLength"]
    for view in data["bufferViews"]:
        assert view["byteOffset"] % 4 == 0
        assert view["byteOffset"] + view["byteLength"] <= len(binary)
    return data


def test_single_pixel_is_a_closed_box_with_outward_normals(tmp_path):
    mesh = relief_mesh([[(255, 100, 0)]])
    positions, normals, colors, indices = mesh
    assert len(indices) == 36 and len(positions) == 72
    assert len(colors) == len(positions) == len(normals)
    edges = {}
    points = [tuple(positions[i : i + 3]) for i in range(0, len(positions), 3)]
    for offset in range(0, len(indices), 3):
        a, b, c = [points[i] for i in indices[offset : offset + 3]]
        ab, ac = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        normal = normals[indices[offset] * 3 : indices[offset] * 3 + 3]
        assert sum(x * y for x, y in zip(cross, normal, strict=True)) > 0
        for start, end in ((a, b), (b, c), (c, a)):
            edge = tuple(sorted((start, end)))
            edges[edge] = edges.get(edge, 0) + 1
    assert set(edges.values()) == {2}
    path = tmp_path / "model.glb"
    write_glb(path, mesh, "Test")
    data = read_glb(path)
    assert data["accessors"][0]["count"] == 24
    assert data["accessors"][0]["max"][2] > data["accessors"][0]["min"][2]


def test_transparency_removes_geometry_and_neighbor_faces_are_omitted():
    single = relief_mesh([[(255, 0, 0), None]])
    pair = relief_mesh([[(255, 0, 0), (0, 255, 0)]])
    assert len(single[3]) == 36
    assert len(pair[3]) == 60
    for invalid in (0, float("nan"), float("inf"), -1, 3):
        with pytest.raises(ValueError):
            relief_mesh([[(255, 0, 0)]], invalid)
    with pytest.raises(ValueError):
        relief_mesh([[None]])


def test_png_and_jpeg_conversion_with_background_and_resizing(tmp_path):
    image = pytest.importorskip("PIL.Image")
    source = tmp_path / "image.png"
    picture = image.new("RGBA", (5, 5), (255, 255, 255, 255))
    picture.putpixel((2, 2), (0, 255, 0, 255))
    picture.save(source)
    records = convert(source, tmp_path / "out", background=(255, 255, 255))
    assert records[0]["vertices"] == 24
    read_glb(tmp_path / "out/image.glb")
    picture.convert("RGB").save(tmp_path / "image.jpg")
    assert convert(tmp_path / "image.jpg", tmp_path / "jpg", size=2)


def test_all_catalogue_entities_export_with_weapons_tints_and_frames(tmp_path):
    catalog = json.loads(
        Path("projects/authored/content.json").read_text(encoding="utf-8")
    )["content"]["sprites"]
    before = json.dumps(catalog, sort_keys=True)
    assert sprite_pixels(catalog, "mob:gobelin_archer") != sprite_pixels(
        catalog, "mob:goblin"
    )
    assert sprite_pixels(catalog, "mob:slime_bleu") != sprite_pixels(
        catalog, "mob:slime_vert"
    )
    records = convert("projects/authored/content.json", tmp_path, all_frames=True)
    assert len(records) == len(catalog["bindings"]) * 4
    assert {record["entity"] for record in records} == set(catalog["bindings"])
    for record in records:
        data = read_glb(tmp_path / record["file"])
        assert all(math.isfinite(n) for n in data["accessors"][0]["min"])
        assert data["nodes"][0]["name"] == record["entity"]
    assert json.dumps(catalog, sort_keys=True) == before
    assert len(
        json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["models"]
    ) == len(records)
