"""Convert local images or the game's sprite catalogue to coloured 3D GLB models."""

import argparse
import json
import math
import struct
from collections import deque
from pathlib import Path


def image_pixels(path, size=64, background=None):
    from PIL import Image

    with Image.open(path) as source:
        image = source.convert("RGBA")
        image.thumbnail((size, size), Image.Resampling.NEAREST)
        rows = []
        for y in range(image.height):
            row = []
            for x in range(image.width):
                r, g, b, a = image.getpixel((x, y))
                row.append(None if a < 128 or (r, g, b) == background else (r, g, b))
            rows.append(row)
        return rows


def sprite_pixels(catalog, target, frame=0):
    sprite = catalog["assets"][catalog["bindings"][target]]
    palette = list(sprite["palette"])
    tint = catalog.get("colors", {}).get(target)
    if tint:
        palette[3] = tint
        palette[4] = "#" + "".join(
            f"{round(int(tint[i : i + 2], 16) * 0.7 + 255 * 0.3):02x}"
            for i in (1, 3, 5)
        )
    weapon = catalog["assets"].get(catalog.get("equipment", {}).get(target))
    layers = [(sprite, palette)] + ([(weapon, weapon["palette"])] if weapon else [])
    rows = [[None] * sprite["width"] for _ in range(sprite["height"])]
    for layer, colors in layers:
        for y, row in enumerate(layer["frames"][frame % len(layer["frames"])]):
            for x, digit in enumerate(row):
                if digit != "0":
                    color = colors[int(digit, 16)]
                    rows[y][x] = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
    return rows


def relief_mesh(rows, depth=0.35):
    """Round the silhouette into columns; emit only exposed, outward-facing faces."""
    if not math.isfinite(depth) or not 0.01 <= depth <= 2:
        raise ValueError("Profondeur requise : entre 0.01 et 2.")
    height, width = len(rows), len(rows[0]) if rows else 0
    if not width or max(width, height) > 256 or any(len(row) != width for row in rows):
        raise ValueError("Image rectangulaire de 1 à 256 pixels requise.")
    solid = {
        (x, y) for y, row in enumerate(rows) for x, color in enumerate(row) if color
    }
    if not solid:
        raise ValueError("L'image est entièrement transparente.")
    distances, queue = {}, deque()
    for x, y in sorted(solid):
        if any(
            (x + dx, y + dy) not in solid
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        ):
            distances[x, y] = 1
            queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            point = x + dx, y + dy
            if point in solid and point not in distances:
                distances[point] = distances[x, y] + 1
                queue.append(point)
    thickness = {
        p: depth / 2 * (0.35 + 0.65 * min(d / 3, 1)) for p, d in distances.items()
    }
    positions, normals, colors, indices = [], [], [], []

    def quad(points, normal, color):
        offset = len(positions) // 3
        linear = [
            v / 255 / 12.92 if v <= 10 else ((v / 255 + 0.055) / 1.055) ** 2.4
            for v in color
        ]
        for point in points:
            positions.extend(point)
            normals.extend(normal)
            colors.extend(linear)
        indices.extend(offset + i for i in (0, 1, 2, 0, 2, 3))

    scale = 1 / max(width, height)
    for x, y in sorted(solid):
        left, right = (x - width / 2) * scale, (x + 1 - width / 2) * scale
        bottom, top = (height - y - 1) * scale, (height - y) * scale
        half, color = thickness[x, y], rows[y][x]
        quad(
            [
                (left, bottom, half),
                (right, bottom, half),
                (right, top, half),
                (left, top, half),
            ],
            (0, 0, 1),
            color,
        )
        quad(
            [
                (right, bottom, -half),
                (left, bottom, -half),
                (left, top, -half),
                (right, top, -half),
            ],
            (0, 0, -1),
            color,
        )
        sides = [
            (
                (x - 1, y),
                (-1, 0, 0),
                lambda a, b, left=left, right=right, top=top, bottom=bottom: [
                    (left, bottom, a),
                    (left, bottom, b),
                    (left, top, b),
                    (left, top, a),
                ],
            ),
            (
                (x + 1, y),
                (1, 0, 0),
                lambda a, b, left=left, right=right, top=top, bottom=bottom: [
                    (right, bottom, b),
                    (right, bottom, a),
                    (right, top, a),
                    (right, top, b),
                ],
            ),
            (
                (x, y - 1),
                (0, 1, 0),
                lambda a, b, left=left, right=right, top=top, bottom=bottom: [
                    (left, top, b),
                    (right, top, b),
                    (right, top, a),
                    (left, top, a),
                ],
            ),
            (
                (x, y + 1),
                (0, -1, 0),
                lambda a, b, left=left, right=right, top=top, bottom=bottom: [
                    (left, bottom, a),
                    (right, bottom, a),
                    (right, bottom, b),
                    (left, bottom, b),
                ],
            ),
        ]
        for neighbor, normal, face in sides:
            other = thickness.get(neighbor, 0)
            if other >= half:
                continue
            ranges = [(-half, half)] if not other else [(-half, -other), (other, half)]
            for a, b in ranges:
                quad(face(a, b), normal, color)
    return positions, normals, colors, indices


def write_glb(path, mesh, name):
    positions, normals, colors, indices = mesh
    binary, views, accessors = bytearray(), [], []
    for values, fmt, kind in (
        (positions, "f", "VEC3"),
        (normals, "f", "VEC3"),
        (colors, "f", "VEC3"),
        (indices, "I", "SCALAR"),
    ):
        block = struct.pack(f"<{len(values)}{fmt}", *values)
        views.append(
            {
                "buffer": 0,
                "byteOffset": len(binary),
                "byteLength": len(block),
                "target": 34963 if fmt == "I" else 34962,
            }
        )
        binary.extend(block)
        accessor = {
            "bufferView": len(views) - 1,
            "componentType": 5125 if fmt == "I" else 5126,
            "count": len(values) if fmt == "I" else len(values) // 3,
            "type": kind,
        }
        if not accessors:
            accessor.update(
                min=[min(positions[i::3]) for i in range(3)],
                max=[max(positions[i::3]) for i in range(3)],
            )
        accessors.append(accessor)
    data = {
        "asset": {"version": "2.0", "generator": "jeuxRPG image_to_3d"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": 0, "NORMAL": 1, "COLOR_0": 2},
                        "indices": 3,
                        "material": 0,
                    }
                ]
            }
        ],
        "materials": [
            {"pbrMetallicRoughness": {"metallicFactor": 0, "roughnessFactor": 1}}
        ],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "accessors": accessors,
    }
    document = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    document += b" " * (-len(document) % 4)
    payload = (
        struct.pack("<I4s", len(document), b"JSON")
        + document
        + struct.pack("<I4s", len(binary), b"BIN\0")
        + binary
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, len(payload) + 12) + payload)
    return {
        "file": path.name,
        "vertices": len(positions) // 3,
        "triangles": len(indices) // 3,
    }


def convert(source, output, depth=0.35, size=64, all_frames=False, background=None):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    if source.suffix.lower() == ".json":
        data = json.loads(source.read_text(encoding="utf-8"))
        catalog = data.get("content", data).get("sprites", data)
        for target, identifier in catalog["bindings"].items():
            sprite = catalog["assets"][identifier]
            count = len(sprite["frames"]) if all_frames else 1
            for frame in range(count):
                name = target.replace(":", "_")
                if not name or any(
                    c
                    not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                    for c in name
                ):
                    name = "entity_" + target.encode("utf-8").hex()
                filename = f"{name}_{frame}.glb" if all_frames else f"{name}.glb"
                record = write_glb(
                    output / filename,
                    relief_mesh(sprite_pixels(catalog, target, frame), depth),
                    target,
                )
                records.append(
                    {
                        "entity": target,
                        "sprite": identifier,
                        "frame": frame,
                        "frame_ms": sprite["frame_ms"],
                        **record,
                    }
                )
    else:
        record = write_glb(
            output / (source.stem + ".glb"),
            relief_mesh(image_pixels(source, size, background), depth),
            source.stem,
        )
        records.append(record)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "source": source.name,
                "method": "rounded silhouette extrusion",
                "depth": depth,
                "models": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return records


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("Images 2D vers modèles 3D")
    root.geometry("680x340")
    all_frames = tk.BooleanVar(value=False)
    source, output, depth = (
        tk.StringVar(),
        tk.StringVar(value=str(Path("dist/models_3d").resolve())),
        tk.StringVar(value="0.35"),
    )
    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Image transparente ou catalogue de sprites JSON").grid(
        row=0, column=0, columnspan=2, sticky="w"
    )
    ttk.Entry(frame, textvariable=source, width=65).grid(row=1, column=0, pady=8)
    ttk.Button(
        frame,
        text="Choisir…",
        command=lambda: source.set(
            filedialog.askopenfilename(
                filetypes=[("Images et sprites", "*.png *.webp *.jpg *.jpeg *.json")]
            )
        ),
    ).grid(row=1, column=1)
    ttk.Label(frame, text="Dossier des modèles GLB").grid(row=2, column=0, sticky="w")
    ttk.Entry(frame, textvariable=output, width=65).grid(row=3, column=0, pady=8)
    ttk.Button(
        frame, text="Choisir…", command=lambda: output.set(filedialog.askdirectory())
    ).grid(row=3, column=1)
    ttk.Label(frame, text="Profondeur (0.01 à 2)").grid(row=4, column=0, sticky="w")
    ttk.Entry(frame, textvariable=depth, width=8).grid(row=4, column=1)

    ttk.Checkbutton(
        frame, text="Exporter toutes les poses des sprites", variable=all_frames
    ).grid(row=5, column=0, sticky="w", pady=8)
    ttk.Button(
        frame,
        text="Sprites du jeu",
        command=lambda: source.set(
            str(Path(__file__).resolve().parents[1] / "projects/authored/content.json")
        ),
    ).grid(row=5, column=1)

    def run():
        try:
            records = convert(
                source.get(),
                output.get(),
                float(depth.get()),
                all_frames=all_frames.get(),
            )
            messagebox.showinfo(
                "Conversion terminée",
                f"{len(records)} modèle(s) GLB créé(s) dans :\n{output.get()}",
            )
        except (OSError, ValueError, KeyError, ImportError) as error:
            messagebox.showerror("Conversion impossible", str(error))

    ttk.Button(frame, text="Créer les modèles 3D", command=run).grid(
        row=6, column=0, columnspan=2, pady=14
    )
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", help="PNG, WebP, JPEG ou catalogue JSON")
    parser.add_argument("--output", default="dist/models_3d")
    parser.add_argument("--depth", type=float, default=0.35)
    parser.add_argument(
        "--size", type=int, choices=range(1, 257), default=64, metavar="1..256"
    )
    parser.add_argument("--all-frames", action="store_true")
    parser.add_argument("--background", help="Couleur du fond à retirer, ex. #ffffff")
    args = parser.parse_args()
    if not args.source:
        gui()
        return
    try:
        background = None
        if args.background:
            color = args.background.removeprefix("#")
            if len(color) != 6:
                raise ValueError(
                    "Le fond doit être une couleur hexadécimale à 6 chiffres."
                )
            background = tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))
        records = convert(
            args.source, args.output, args.depth, args.size, args.all_frames, background
        )
    except (OSError, ValueError, KeyError, ImportError) as error:
        parser.exit(1, f"Conversion impossible : {error}\n")
    print(f"{len(records)} modèle(s) GLB créé(s) dans {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
