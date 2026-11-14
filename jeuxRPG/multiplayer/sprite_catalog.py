"""Project-owned pixel sprites: bounded, portable JSON, with no external assets."""

import re
from copy import deepcopy

DIGITS = "0123456789abcdef"
AMBIENT = {
    "resident": "Habitants",
    "guards": "Patrouilles de gardes",
    "monsters": "Groupes de monstres",
    "merchant": "Caravane",
    "raiders": "Assaillants",
}


def catalog(content):
    return content.get("sprites", {"assets": {}, "bindings": {}})


def validate(data):
    if (
        not isinstance(data, dict)
        or not {"assets", "bindings"} <= set(data)
        or set(data) - {"assets", "bindings", "equipment", "colors"}
    ):
        raise ValueError("Sprites : assets et bindings requis.")
    assets, bindings = data["assets"], data["bindings"]
    if (
        not isinstance(assets, dict)
        or len(assets) > 64
        or not isinstance(bindings, dict)
        or len(bindings) > 512
    ):
        raise ValueError("Sprites : catalogue trop grand ou invalide.")
    pixels = 0
    for identifier, sprite in assets.items():
        if not isinstance(identifier, str) or not re.fullmatch(
            r"[a-z][a-z0-9_-]{0,47}", identifier
        ):
            raise ValueError("Sprite : identifiant invalide.")
        if not isinstance(sprite, dict) or set(sprite) - {"layer"} != {
            "name",
            "width",
            "height",
            "palette",
            "frames",
            "frame_ms",
        }:
            raise ValueError(f"Sprite {identifier} : champs invalides.")
        if sprite.get("layer", "body") not in ("body", "weapon"):
            raise ValueError("Sprite : calque corps ou arme requis.")
        if (
            not isinstance(sprite["name"], str)
            or not 1 <= len(sprite["name"].strip()) <= 80
        ):
            raise ValueError(f"Sprite {identifier} : nom invalide.")
        if any(
            type(sprite[key]) is not int or not 1 <= sprite[key] <= 32
            for key in ("width", "height")
        ):
            raise ValueError("Sprite : dimensions maximales 32 × 32.")
        palette = sprite["palette"]
        if (
            not isinstance(palette, list)
            or not 2 <= len(palette) <= 16
            or palette[0] is not None
            or any(
                not isinstance(color, str)
                or not re.fullmatch(r"#[0-9a-fA-F]{6}", color)
                for color in palette[1:]
            )
        ):
            raise ValueError("Sprite : palette de 15 couleurs et transparence requise.")
        frames = sprite["frames"]
        if not isinstance(frames, list) or not 1 <= len(frames) <= 8:
            raise ValueError("Sprite : 1 à 8 images requises.")
        if type(sprite["frame_ms"]) is not int or not 80 <= sprite["frame_ms"] <= 2000:
            raise ValueError("Sprite : durée d'image de 80 à 2000 ms requise.")
        for frame in frames:
            if (
                not isinstance(frame, list)
                or len(frame) != sprite["height"]
                or any(
                    not isinstance(row, str)
                    or len(row) != sprite["width"]
                    or any(char not in DIGITS[: len(palette)] for char in row)
                    for row in frame
                )
            ):
                raise ValueError(f"Sprite {identifier} : pixels invalides.")
        pixels += sprite["width"] * sprite["height"] * len(frames)
    if pixels > 262144:
        raise ValueError("Sprites : budget total de 262 144 pixels dépassé.")
    for target, identifier in bindings.items():
        if (
            not isinstance(target, str)
            or not re.fullmatch(r"(?:class|mob|npc|ambient):[^\s]{1,128}", target)
            or not isinstance(identifier, str)
            or identifier not in assets
        ):
            raise ValueError("Sprite : association invalide ou sprite absent.")
        if assets[identifier].get("layer", "body") != "body":
            raise ValueError("L'entité doit utiliser un sprite de corps.")
    _validate_equipment(data, assets, bindings)
    return data


def _validate_equipment(data, assets, bindings):
    equipment = data.get("equipment", {})
    if not isinstance(equipment, dict) or len(equipment) > 512:
        raise ValueError("Sprites : associations d'armes invalides.")
    for target, identifier in equipment.items():
        if (
            target not in bindings
            or not isinstance(identifier, str)
            or identifier not in assets
        ):
            raise ValueError("Arme absente ou entité sans corps.")
        weapon, body = assets[identifier], assets[bindings[target]]
        if weapon.get("layer") != "weapon" or any(
            weapon[key] != body[key] for key in ("width", "height")
        ):
            raise ValueError(
                "L'arme doit être un calque de mêmes dimensions que le corps."
            )
    colors = data.get("colors", {})
    if not isinstance(colors, dict) or len(colors) > 512:
        raise ValueError("Sprites : teintes invalides.")
    for target, color in colors.items():
        if (
            target not in bindings
            or not isinstance(color, str)
            or not re.fullmatch(r"#[0-9a-fA-F]{6}", color)
            or len(assets[bindings[target]]["palette"]) < 5
        ):
            raise ValueError("Sprite : teinte ou palette de corps invalide.")
    return data


def targets(content, mobs, maps):
    result = {
        f"class:{item['id']}": f"Classe · {item['name']}"
        for item in content["templates"]["classes"]
    }
    result.update(
        {
            f"mob:{key}": f"Monstre · {value.get('name', key)}"
            for key, value in mobs.items()
        }
    )
    for definition in maps.values():
        for site in definition.get("sites", []):
            result[f"npc:{site['id']}"] = f"PNJ / lieu · {site['name']}"
    for npc in content.get("npcs", []):
        result.setdefault(f"npc:{npc['id']}", f"PNJ · {npc['name']}")
    result.update({f"ambient:{key}": label for key, label in AMBIENT.items()})
    return result


def validate_references(content, mobs, maps):
    data = validate(catalog(content))
    allowed = targets(content, mobs, maps)
    if (
        unknown := (data["bindings"].keys() | data.get("equipment", {}).keys())
        - allowed.keys()
    ):
        raise ValueError("Sprites : entité absente : " + ", ".join(sorted(unknown)))


def blank(name="Nouveau sprite", size=16):
    return {
        "name": name,
        "width": size,
        "height": size,
        "palette": [
            None,
            "#202738",
            "#e7b887",
            "#698cb7",
            "#e3e7ed",
            "#654832",
            "#73bf8a",
            "#bd6666",
        ],
        "frames": [["0" * size for _ in range(size)]],
        "frame_ms": 180,
    }


def original(name="Voyageur", accent="#698cb7", creature=False):
    """Small original geometric pixel designs, authored for this project."""
    result = blank(name)
    result["palette"][3] = accent
    rows = (
        [
            "0000000000000000",
            "0000001111000000",
            "0000014444100000",
            "0000144444410000",
            "0000141441410000",
            "0000012222100000",
            "0000001221000000",
            "0000113333110000",
            "0001234334321000",
            "0001233333321000",
            "0000113333110000",
            "0000015555100000",
            "0000013113100000",
            "0000013113100000",
            "0000151001510000",
            "0000111001110000",
        ]
        if not creature
        else [
            "0000000000000000",
            "0000100000010000",
            "0001610000161000",
            "0001661111661000",
            "0000166666610000",
            "0001616661610000",
            "0001667667661000",
            "0000162222610000",
            "0000016666100000",
            "0000116666110000",
            "0001666666661000",
            "0001616666161000",
            "0000101661010000",
            "0000016116100000",
            "0000161001610000",
            "0000111001110000",
        ]
    )
    result["frames"] = [rows]
    return result


class PixelDocument:
    """Editable frame buffer, independent of Tk; one undo entry per brush stroke."""

    def __init__(self, sprite):
        validate({"assets": {"work": sprite}, "bindings": {}})
        self.sprite = deepcopy(sprite)
        self.frame = 0
        self.history, self.future = [], []

    def checkpoint(self):
        self.history.append(deepcopy(self.sprite))
        self.history = self.history[-30:]
        self.future.clear()

    def undo(self, redo=False):
        source, destination = (
            (self.future, self.history) if redo else (self.history, self.future)
        )
        if source:
            destination.append(self.sprite)
            self.sprite = source.pop()
            self.frame = min(self.frame, len(self.sprite["frames"]) - 1)

    def paint(self, x, y, index, fill=False):
        width, height = self.sprite["width"], self.sprite["height"]
        if not (
            0 <= x < width
            and 0 <= y < height
            and 0 <= index < len(self.sprite["palette"])
        ):
            return
        rows = [list(row) for row in self.sprite["frames"][self.frame]]
        previous, color = rows[y][x], DIGITS[index]
        pending, visited = [(x, y)], set()
        while pending:
            px, py = pending.pop()
            if (px, py) in visited or not 0 <= px < width or not 0 <= py < height:
                continue
            visited.add((px, py))
            if fill and rows[py][px] != previous:
                continue
            rows[py][px] = color
            if fill:
                pending.extend(((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)))
        self.sprite["frames"][self.frame] = ["".join(row) for row in rows]

    def add_frame(self):
        if len(self.sprite["frames"]) >= 8:
            raise ValueError("Maximum : 8 images.")
        self.checkpoint()
        self.sprite["frames"].append(deepcopy(self.sprite["frames"][self.frame]))
        self.frame = len(self.sprite["frames"]) - 1

    def remove_frame(self):
        if len(self.sprite["frames"]) == 1:
            raise ValueError("Conservez au moins une image.")
        self.checkpoint()
        self.sprite["frames"].pop(self.frame)
        self.frame = min(self.frame, len(self.sprite["frames"]) - 1)
