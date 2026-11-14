"""Original CC0 pixel designs, generated as editable frames for the local Builder.

Bodies share a 24 px canvas. The right-hand equipment area is kept separate;
weapons use transparent canvases of the same size and follow the same four poses.
"""

from copy import deepcopy

from .sprite_catalog import AMBIENT, validate

PALETTE = [
    None,
    "#202435",
    "#414958",
    "#638d62",
    "#a2c791",
    "#e2b58c",
    "#755039",
    "#f0d269",
    "#e4dcc0",
    "#b7ced9",
    "#93694b",
    "#d69e45",
    "#bf6064",
    "#9476bb",
    "#304e43",
    "#f4f4e9",
]
POSES = [(0, 0), (0, 1), (0, 0), (0, 1)]


class Pixels:
    def __init__(self):
        self.rows = [list("0" * 24) for _ in range(24)]

    def dot(self, x, y, color):
        if 0 <= x < 24 and 0 <= y < 24:
            self.rows[y][x] = color

    def rect(self, x, y, width, height, color):
        for py in range(y, y + height):
            for px in range(x, x + width):
                self.dot(px, py, color)

    def line(self, x, y, tx, ty, color):
        steps = max(abs(tx - x), abs(ty - y), 1)
        for step in range(steps + 1):
            self.dot(
                round(x + (tx - x) * step / steps),
                round(y + (ty - y) * step / steps),
                color,
            )

    def oval(self, x, y, rx, ry, color):
        for py in range(y - ry, y + ry + 1):
            for px in range(x - rx, x + rx + 1):
                if (px - x) ** 2 * ry**2 + (py - y) ** 2 * rx**2 <= rx**2 * ry**2:
                    self.dot(px, py, color)

    def outlined(self, x, y, rx, ry, color):
        self.oval(x, y, rx, ry, "1")
        self.oval(x, y, max(1, rx - 1), max(1, ry - 1), color)

    def frame(self):
        return ["".join(row) for row in self.rows]


def humanoid(p, frame, kind):
    bob = frame % 2
    if kind == "golem":
        p.rect(8, 10 + bob, 10, 10, "1")
        p.rect(9, 11 + bob, 8, 8, "3")
        p.rect(4, 10 + bob, 5, 6, "2")
        p.rect(18, 10 + bob, 5, 6, "2")
        p.rect(5, 15 + bob, 3, 4, "3")
        p.rect(19, 15 + bob, 3, 4, "3")
        p.outlined(13, 5 + bob, 5, 4, "3")
        p.dot(11, 5 + bob, "d")
        p.dot(15, 5 + bob, "d")
        p.line(12, 11 + bob, 14, 14 + bob, "2")
        p.line(14, 14 + bob, 11, 17 + bob, "2")
        p.rect(8, 20, 4, 3, "2")
        p.rect(15, 20, 4, 3, "2")
        p.dot(13, 12 + bob, "b" if frame % 2 else "d")
        return
    heavy = kind in ("orc", "ogre", "troll", "golem")
    robe = kind in ("mage", "priest", "necromancer", "ghost", "liche")
    skin = (
        "3"
        if kind in ("goblin", "orc", "troll", "kobold")
        else "8"
        if kind in ("skeleton", "liche")
        else "5"
    )
    width = 7 if heavy else 5
    p.rect(10, 18, 3, 4, "1")
    p.rect(14, 18, 3, 4, "1")
    p.rect(10, 19, 2, 2, "2")
    p.rect(14, 19, 2, 2, "2")
    stride = 1 if frame in (1, 2) else 0
    p.rect(9 + stride, 21, 4, 2, "1")
    p.rect(14 - stride, 21, 4, 2, "1")
    p.outlined(13, 14 + bob, width, 5, "3")
    p.rect(9 if not heavy else 7, 17 + bob, 9 if not heavy else 13, 2, "a")
    p.dot(13, 17 + bob, "b")
    p.line(8 if not heavy else 6, 12 + bob, 7, 16 + bob, "1")
    p.line(17, 12 + bob, 18, 14 + bob, "1")
    p.rect(6, 15 + bob, 2, 2, skin)
    p.rect(17, 13 + bob, 2, 2, skin)
    p.outlined(12, 6 + bob, 5 if heavy else 4, 5, skin)
    if kind in ("goblin", "orc", "kobold"):
        p.line(8, 4 + bob, 4, 3 + bob, "1")
        p.line(4, 3 + bob, 7, 7 + bob, "1")
        p.rect(6, 4 + bob, 2, 2, skin)
        p.line(16, 4 + bob, 20, 3 + bob, "1")
        p.line(20, 3 + bob, 17, 7 + bob, "1")
        p.rect(17, 4 + bob, 2, 2, skin)
    p.rect(9, 5 + bob, 2, 2, "1")
    p.rect(14, 5 + bob, 2, 2, "1")
    p.dot(10, 5 + bob, "7")
    p.dot(14, 5 + bob, "7")
    p.line(11, 9 + bob, 14, 9 + bob, "1")
    if kind in ("knight", "guard", "golem"):
        p.rect(8, 2 + bob, 9, 2, "1")
        p.rect(9, 2 + bob, 7, 1, "9")
        p.line(8, 4 + bob, 16, 4 + bob, "9")
        p.line(12, 3 + bob, 12, 8 + bob, "9")
        p.rect(10, 12 + bob, 5, 3, "9")
        p.dot(12, 13 + bob, "f")
    elif robe:
        for y in range(2, 10):
            p.dot(7, y + bob, "d" if kind == "necromancer" else "3")
            p.dot(17, y + bob, "d" if kind == "necromancer" else "3")
        p.line(8, 1 + bob, 16, 1 + bob, "1")
        p.line(9, 2 + bob, 15, 2 + bob, "4")
        for y in range(15, 22):
            p.rect(8 - (y - 15) // 3, y, 10 + 2 * ((y - 15) // 3), 1, "3")
        p.line(12, 11 + bob, 12, 20, "b")
        if kind == "priest":
            p.rect(11, 12 + bob, 3, 1, "8")
            p.rect(12, 11 + bob, 1, 4, "8")
    elif kind == "skeleton":
        for y in (12, 14, 16):
            p.rect(10, y + bob, 6, 1, "8")
        p.rect(12, 11 + bob, 1, 7, "8")
        p.rect(10, 7 + bob, 6, 2, "8")
    elif kind in ("archer", "merchant"):
        p.rect(8, 1 + bob, 9, 2, "3")
        p.rect(6, 3 + bob, 13, 1, "1")
        p.line(10, 11 + bob, 15, 17 + bob, "a")
        if kind == "merchant":
            p.outlined(7, 16 + bob, 3, 3, "b")
    elif kind in ("ogre", "troll"):
        p.rect(8, 7 + bob, 2, 3, "8")
        p.rect(15, 7 + bob, 2, 3, "8")
        p.rect(9, 13 + bob, 7, 4, skin)


def quadruped(p, frame, kind):
    bob = frame % 2
    skin = "3"
    p.outlined(11, 14 + bob, 7, 4, skin)
    p.outlined(17, 10 + bob, 4, 4, skin)
    p.rect(18, 10 + bob, 5, 3, "4")
    p.dot(22, 11 + bob, "1")
    p.dot(17, 8 + bob, "1")
    for index, x in enumerate((6, 9, 14, 17)):
        stride = 1 if (frame + index) % 4 < 2 else -1
        p.line(x, 16 + bob, x + stride, 20, "1")
        p.rect(x + stride - 1, 20, 3, 1, "2")
    p.line(5, 13 + bob, 1, 10 + (frame % 3), "1")
    if kind == "rat":
        p.outlined(15, 7 + bob, 2, 2, "c")
        p.line(2, 11, 0, 15 + bob, "c")
        p.line(21, 11 + bob, 23, 9 + bob, "8")
    elif kind == "boar":
        p.rect(17, 5 + bob, 3, 2, "1")
        p.line(20, 13 + bob, 22, 11 + bob, "8")
        p.line(7, 9 + bob, 13, 10 + bob, "2")
    else:
        p.line(14, 7 + bob, 14, 3 + bob, "1")
        p.line(14, 3 + bob, 18, 7 + bob, "4")
        p.line(19, 7 + bob, 20, 4 + bob, "1")


def winged(p, frame, kind):
    bob = frame % 2
    lift = (0, 2, 4, 2)[frame]
    for direction in (-1, 1):
        for step in range(8):
            x = 12 + direction * (step + 2)
            p.line(12, 12 + bob, x, 10 - lift + step // 3, "1")
            p.line(12, 11 + bob, x, 9 - lift + step // 3, "3")
    p.outlined(12, 13 + bob, 4, 6, "3")
    p.outlined(13, 6 + bob, 3, 3, "4")
    p.dot(14, 5 + bob, "1")
    if kind in ("dragon", "griffon"):
        p.line(10, 16 + bob, 4, 21 - bob, "3")
        p.rect(9, 19, 2, 3, "1")
        p.rect(14, 19, 2, 3, "1")
        p.dot(12, 2 + bob, "8")
        p.dot(15, 3 + bob, "8")
    if kind in ("crow", "griffon", "harpy"):
        p.line(16, 6 + bob, 19, 7 + bob, "b")
    if kind == "bat":
        p.line(10, 5 + bob, 10, 1 + bob, "1")
        p.line(14, 5 + bob, 15, 1 + bob, "1")
        p.dot(11, 6 + bob, "c")
        p.dot(14, 6 + bob, "c")


def insect(p, frame, kind):
    count = 4 if kind in ("spider", "scorpion") else 3
    for side in (-1, 1):
        for index in range(count):
            y = 8 + index * 3
            bend = 2 if (index + frame) % 2 else -1
            p.line(12 + side * 3, y, 12 + side * 7, y - 2 + bend, "1")
            p.line(12 + side * 7, y - 2 + bend, 12 + side * 10, y + 2 + bend, "a")
    p.outlined(12, 13, 5, 6, "3")
    p.outlined(12, 6, 3, 3, "2")
    p.dot(11, 5, "7")
    p.dot(13, 5, "7")
    if kind == "scorpion":
        p.line(12, 17, 16, 21, "3")
        p.line(16, 21, 20, 18 - frame % 2, "3")
        p.dot(20, 17 - frame % 2, "b")
    elif kind == "beetle":
        p.line(12, 9, 12, 18, "b")
        p.dot(10, 11 + frame % 2, "f")


def magical(p, frame, kind):
    bob = frame % 2
    if kind == "slime":
        ry = (5, 6, 7, 6)[frame]
        p.outlined(12, 20 - ry, 8 - bob, ry, "3")
        p.rect(8, 12 - bob, 3, 2, "4")
        p.dot(10, 16 - bob, "1")
        p.dot(15, 16 - bob, "1")
        p.line(11, 19 - bob, 14, 19 - bob, "4")
    elif kind in ("ghost", "spirit", "flame"):
        p.outlined(12, 10 + bob, 6, 8, "3")
        for index in range(4):
            p.line(
                7 + index * 3,
                15,
                6 + index * 3 + frame % 2,
                20 - (index + frame) % 3,
                "4",
            )
        p.dot(10, 8 + bob, "f")
        p.dot(14, 8 + bob, "f")
        if kind == "flame":
            p.line(11, 6, 9 + frame, 1, "b")
            p.outlined(12, 13, 3, 4, "7")
    elif kind in ("mushroom", "plant"):
        p.line(12, 20, 12 + bob, 8, "1")
        p.line(13, 20, 13 + bob, 8, "3")
        if kind == "mushroom":
            p.outlined(12 + bob, 7, 8, 5, "c")
            p.rect(5 + bob, 8, 15, 2, "8")
            p.rect(8 + bob, 5, 2, 2, "8")
            p.rect(14 + bob, 4, 2, 2, "8")
        else:
            p.outlined(7 + bob, 11, 5, 2, "3")
            p.outlined(17 + bob, 9, 4, 2, "4")
            p.line(13, 15, 5, 5 + bob, "3")
            p.line(13, 15, 20, 4 - bob, "3")
        p.dot(11, 13, "1")
        p.dot(14, 13, "1")


def object_art(p, frame, kind):
    if kind == "book":
        p.rect(4, 7, 16, 13, "1")
        p.rect(5, 8, 6, 10, "8")
        p.rect(13, 8, 6, 10, "8")
        for y in (10, 13, 16):
            p.line(6, y, 9, y, "a")
            p.line(14, y, 17, y, "a")
    elif kind == "cargo":
        p.rect(4, 9, 16, 12, "1")
        p.rect(5, 10, 14, 10, "a")
        p.line(5, 10, 18, 19, "b")
        p.line(18, 10, 5, 19, "b")
    else:
        p.outlined(12, 10, 6, 7, "2")
        p.rect(6, 10, 13, 11, "2")
        p.rect(5, 20, 15, 2, "1")
        p.line(9, 8, 15, 8, "9")
        p.line(9, 11, 14, 11, "9")
    p.dot(8 + frame * 2, 7 + (frame % 2), "f")


def weapon_art(p, frame, kind):
    bob = frame % 2
    if kind == "bow":
        for x, y, tx, ty in (
            (19, 4, 22, 8),
            (22, 8, 23, 13),
            (23, 13, 22, 18),
            (22, 18, 19, 21),
        ):
            p.line(x, y + bob, tx, ty + bob, "a")
        p.line(19, 4 + bob, 19, 21 + bob, "8")
        p.line(16, 13 + bob, 23, 13 + bob, "a")
        p.dot(23, 12 + bob, "9")
        p.dot(23, 14 + bob, "9")
    elif kind in ("staff", "skull_staff", "wand"):
        p.line(18, 20 + bob, 20, 7 + bob, "a")
        if kind == "skull_staff":
            p.outlined(20, 5 + bob, 3, 3, "8")
            p.dot(19, 5 + bob, "1")
            p.dot(21, 5 + bob, "1")
        else:
            p.outlined(20, 5 + bob, 2, 3, "d" if kind == "wand" else "7")
            p.dot(20, 4 + bob, "f")
    elif kind in ("axe", "hammer", "pick"):
        p.line(18, 21 + bob, 19, 9 + bob, "a")
        if kind == "axe":
            p.outlined(21, 8 + bob, 2, 4, "9")
            p.line(19, 5 + bob, 19, 11 + bob, "b")
        elif kind == "hammer":
            p.rect(16, 6 + bob, 7, 5, "1")
            p.rect(17, 7 + bob, 5, 3, "9")
        else:
            p.line(14, 9 + bob, 20, 5 + bob, "9")
            p.line(20, 5 + bob, 23, 8 + bob, "9")
    elif kind == "spear":
        p.line(18, 22, 19, 8 + bob, "a")
        for row in range(5):
            p.line(19 - row // 2, 4 + row + bob, 19 + row // 2, 4 + row + bob, "9")
    else:
        short = kind == "dagger"
        p.rect(18, 8 + bob if short else 3 + bob, 2, 6 if short else 11, "1")
        p.line(19, 9 + bob if short else 4 + bob, 19, 13 + bob, "9")
        p.line(16, 14 + bob, 22, 14 + bob, "b")
        p.line(19, 15 + bob, 19, 19 + bob, "a")
        p.dot(19, 10 + frame, "f")
        if kind == "sword_shield":
            p.outlined(4, 14 + bob, 3, 5, "3")
            p.line(4, 11 + bob, 4, 17 + bob, "b")
            p.line(2, 14 + bob, 6, 14 + bob, "b")


def make_sprite(name, family, color="#638d62", weapon=False):
    palette = deepcopy(PALETTE)
    palette[3] = color
    palette[4] = "#" + "".join(
        f"{round(int(color[index : index + 2], 16) * 0.7 + 255 * 0.3):02x}"
        for index in (1, 3, 5)
    )
    frames = []
    for frame in range(4):
        pixels = Pixels()
        if weapon:
            weapon_art(pixels, frame, family)
        elif family in ("rat", "wolf", "boar", "lizard"):
            quadruped(pixels, frame, family)
        elif family in ("dragon", "crow", "bat", "griffon", "harpy"):
            winged(pixels, frame, family)
        elif family in ("spider", "scorpion", "beetle"):
            insect(pixels, frame, family)
        elif family in ("slime", "ghost", "spirit", "flame", "mushroom", "plant"):
            magical(pixels, frame, family)
        elif family in ("stone", "cargo", "book"):
            object_art(pixels, frame, family)
        else:
            humanoid(pixels, frame, family)
        frames.append(pixels.frame())
    return {
        "name": name,
        "width": 24,
        "height": 24,
        "palette": palette,
        "frames": frames,
        "frame_ms": 180,
        "layer": "weapon" if weapon else "body",
    }


RACES = {
    "Gobelin": ("goblin", "#739747"),
    "Orc": ("orc", "#5c7952"),
    "Dragon": ("dragon", "#a56549"),
    "Rat": ("rat", "#8d8176"),
    "Slime": ("slime", "#69a85b"),
    "Scarabée": ("beetle", "#849545"),
    "Corbeau": ("crow", "#53536b"),
    "Araignée": ("spider", "#776b8a"),
    "Chauve-souris": ("bat", "#776482"),
    "Loup": ("wolf", "#8b969d"),
    "Sanglier": ("boar", "#88694f"),
    "Squelette": ("skeleton", "#86837a"),
    "Végétal": ("plant", "#73994d"),
    "Kobold": ("kobold", "#ad7956"),
    "Scorpion": ("scorpion", "#bc9956"),
    "Golem": ("golem", "#9b8e77"),
    "Spectre": ("ghost", "#9aaac6"),
    "Feu follet": ("flame", "#7fb2be"),
    "Harpie": ("harpy", "#ab8b7e"),
    "Salamandre": ("lizard", "#bb6d49"),
    "Troll": ("troll", "#718a62"),
    "Humain": ("necromancer", "#655077"),
    "Basilic": ("lizard", "#939b54"),
    "Ogre": ("ogre", "#b5997b"),
    "Élémentaire": ("flame", "#dd874a"),
    "Griffon": ("griffon", "#b99a5f"),
    "Liche": ("liche", "#7a6b96"),
    "Esprit": ("spirit", "#72ad9a"),
}


def preferred_weapon(identifier, race):
    if "archer" in identifier:
        return "bow"
    if any(
        word in identifier for word in ("chamane", "apprenti", "liche", "necromancien")
    ):
        return (
            "skull_staff"
            if "liche" in identifier or "necromancien" in identifier
            else "staff"
        )
    if "mineur" in identifier or "kobold" in identifier:
        return "pick"
    if (
        "berserker" in identifier
        or "boss" in identifier
        or "chef" in identifier
        and race in ("Gobelin", "Orc")
    ):
        return "axe"
    if "garde" in identifier or "chevalier" in identifier:
        return "sword_shield"
    if "seigneur" in identifier:
        return "sword_shield"
    if race in ("Gobelin", "Kobold"):
        return "dagger" if "eclaireur" in identifier else "spear"
    if race in ("Orc", "Ogre", "Troll"):
        return "axe"
    if race == "Squelette":
        return "sword"
    return None


def mob_appearance(identifier, definition, families):
    race = definition.get("race", "Gobelin")
    body = families.get(race, families["Gobelin"])
    color = RACES.get(race, (None, None))[1]
    variants = {
        "slime_bleu": "#638fc4",
        "dragonnet_rouge": "#c56557",
        "runique": "#8b78aa",
        "schiste": "#718a94",
        "roncier": "#728052",
        "boss": "#8b7247",
        "seigneur": "#8b7247",
    }
    color = next((tint for word, tint in variants.items() if word in identifier), color)
    if "champignon" in identifier:
        body = "corps_mushroom"
    return body, preferred_weapon(identifier, race), color


def populate(project):
    """Assign all current entities, preserving additional user assets and bindings."""
    from .mob_rules import resolve

    data = deepcopy(project.content.get("sprites", {"assets": {}, "bindings": {}}))
    assets, bindings = data["assets"], data["bindings"]
    equipment = data.setdefault("equipment", {})
    colors = data.setdefault("colors", {})
    families = {}
    for race, (family, color) in RACES.items():
        identifier = "gobelin_original" if race == "Gobelin" else f"corps_{family}"
        # Same geometry may serve multiple species with a palette override.
        if identifier not in families.values():
            assets[identifier] = make_sprite(f"Corps · {race}", family, color)
        families[race] = identifier
    for identifier, family, color, name in (
        ("chevalier_original", "knight", "#667f9c", "Chevalier"),
        ("garde_original", "guard", "#608677", "Garde"),
        ("marchand_original", "merchant", "#ac8253", "Marchand"),
        ("corps_mage", "mage", "#6589ad", "Mage"),
        ("corps_archer", "archer", "#7e9256", "Archer"),
        ("corps_pretre", "priest", "#d0c8aa", "Prêtre"),
    ):
        assets[identifier] = make_sprite(name, family, color)
    for kind in (
        "sword",
        "sword_shield",
        "dagger",
        "spear",
        "axe",
        "bow",
        "staff",
        "skull_staff",
        "wand",
        "hammer",
        "pick",
    ):
        assets[f"arme_{kind}"] = make_sprite(f"Arme · {kind}", kind, weapon=True)
    for kind in ("stone", "book", "cargo"):
        assets[f"objet_{kind}"] = make_sprite(f"Indice · {kind}", kind, "#859193")
    assets["corps_mushroom"] = make_sprite("Champignon animé", "mushroom", "#8a9d63")

    def assign(target, body, weapon=None, color=None):
        bindings[target] = body
        equipment.pop(target, None)
        colors.pop(target, None)
        if weapon:
            equipment[target] = f"arme_{weapon}"
        if color:
            colors[target] = color

    classes = {
        "Knight": ("chevalier_original", "sword_shield"),
        "Mage": ("corps_mage", "wand"),
        "Archer": ("corps_archer", "bow"),
        "Priest": ("corps_pretre", "staff"),
        "Necromancien": (families["Humain"], "skull_staff"),
        "Goblin": (families["Gobelin"], "spear"),
        "Orc": (families["Orc"], "axe"),
        "DragonWhelp": (families["Dragon"], None),
        "Squelette": (families["Squelette"], "sword"),
        "PhysicalResistantMob": (families["Golem"], None),
        "MagicResistantMob": (families["Spectre"], None),
        "SacredResistantMob": (families["Squelette"], None),
    }
    for item in project.content["templates"]["classes"]:
        body, weapon = classes.get(item["id"], ("chevalier_original", None))
        assign(f"class:{item['id']}", body, weapon)
    for identifier in project.mobs:
        definition = resolve(project.mobs, identifier)
        assign(f"mob:{identifier}", *mob_appearance(identifier, definition, families))
    npcs = {
        "mira": ("garde_original", "spear"),
        "forge": ("marchand_original", "hammer"),
        "rusk": (families["Gobelin"], "dagger"),
        "seve": ("corps_pretre", "staff"),
        "oriel": ("corps_mage", "staff"),
        "neran": ("marchand_original", "pick"),
        "elyne": ("garde_original", "sword_shield"),
    }
    for definition in project.maps.values():
        for site in definition.get("sites", []):
            if site.get("interaction") == "inspect":
                body = (
                    "objet_cargo"
                    if "chargement" in site["id"]
                    else "objet_book"
                    if "inscription" in site["id"]
                    else "objet_stone"
                )
                assign(f"npc:{site['id']}", body)
            else:
                body, weapon = npcs.get(site["id"], ("marchand_original", None))
                assign(f"npc:{site['id']}", body, weapon)
    ambient = {
        "resident": ("marchand_original", None),
        "guards": ("garde_original", "spear"),
        "merchant": ("marchand_original", None),
        "monsters": (families["Loup"], None),
        "raiders": (families["Gobelin"], "axe"),
    }
    for kind in AMBIENT:
        body, weapon = ambient[kind]
        assign(f"ambient:{kind}", body, weapon)
    validate(data)
    project.content["sprites"] = data
    project.validate()
    return data
