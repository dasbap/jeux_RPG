"""Validated Builder-owned presentation settings, compatible with older projects."""

import re
from copy import deepcopy

DEFAULTS = {
    "menus": {"width_percent": 75, "height_percent": 75, "position": "center"},
    "quests": {
        "card_min_width_px": 300,
        "padding_px": 10,
        "gap_px": 10,
        "compact": True,
    },
    "minimap": {"width_px": 224, "height_px": 126},
    "theme": {
        "accent_color": "#b7a0ff",
        "panel_color": "#13202f",
        "text_color": "#eceef3",
        "font_size_px": 16,
    },
    "hud": {"zone_banner_seconds": 3},
}
GROUPS = {
    "menus": "Menus",
    "quests": "Quêtes",
    "minimap": "Mini-carte",
    "theme": "Couleurs et texte",
    "hud": "Informations",
}
LABELS = {
    "width_percent": "Largeur des menus (%)",
    "height_percent": "Hauteur des menus (%)",
    "position": "Position des menus",
    "card_min_width_px": "Largeur minimale d’une fiche (px)",
    "padding_px": "Marge intérieure des fiches (px)",
    "gap_px": "Espacement entre les fiches (px)",
    "compact": "Fiches compactes",
    "width_px": "Largeur sur grand écran (px)",
    "height_px": "Hauteur sur grand écran (px)",
    "accent_color": "Couleur des boutons",
    "panel_color": "Fond des menus",
    "text_color": "Couleur du texte",
    "font_size_px": "Taille de base du texte (px)",
    "zone_banner_seconds": "Nom de zone : durée (secondes)",
}
RANGES = {
    "width_percent": (40, 95),
    "height_percent": (35, 95),
    "card_min_width_px": (200, 600),
    "padding_px": (4, 24),
    "gap_px": (4, 24),
    "width_px": (120, 360),
    "height_px": (60, 240),
    "font_size_px": (12, 22),
    "zone_banner_seconds": (1, 15),
}
POSITIONS = {"center": "Centré", "left": "À gauche", "right": "À droite"}


def validate_interface(value):
    if not isinstance(value, dict) or set(value) - DEFAULTS.keys():
        raise ValueError("Interface : groupes de réglages invalides.")
    result = deepcopy(DEFAULTS)
    for group, fields in value.items():
        if not isinstance(fields, dict) or set(fields) - DEFAULTS[group].keys():
            raise ValueError(f"Interface : champs invalides dans {GROUPS[group]}.")
        for key, item in fields.items():
            if key in RANGES:
                low, high = RANGES[key]
                valid = type(item) is int and low <= item <= high
            elif key == "position":
                valid = isinstance(item, str) and item in POSITIONS
            elif key == "compact":
                valid = type(item) is bool
            else:
                valid = isinstance(item, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", item)
            if not valid:
                raise ValueError(f"Interface : valeur invalide pour {LABELS[key]}.")
            result[group][key] = item
    return result


def settings(content):
    return validate_interface(content.get("interface", {}))
