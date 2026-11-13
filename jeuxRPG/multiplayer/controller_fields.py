RANKS = ("SSS", "SS", "S", "AA", "A", "B", "C", "D", "E")
QUEST_TYPE_LABELS = {
    "main": "Principale",
    "side": "Secondaire",
    "tutorial": "Découverte",
}


DECIMAL_FIELDS = {
    "chance",
    "threshold",
    "xp_multiplier",
    "damage_growth",
    "power",
    "growth",
    "cooldown",
    "cast",
    "range",
    "duration",
    "repop_seconds",
    "xp_base",
    "xp_exponent",
    "merchant_stay_hours",
    "hp_multiplier",
    "damage_multiplier",
}


def form_choices(values, choices):
    result = dict(choices or {})
    for key, value in values.items():
        if type(value) is bool:
            result[key] = ["Oui", "Non"]
        elif key == "quest_type":
            result[key] = list(QUEST_TYPE_LABELS.values())
    return result


def display_field(key, value):
    if type(value) is bool:
        return "Oui" if value else "Non"
    return QUEST_TYPE_LABELS.get(value, value) if key == "quest_type" else value


def parse_field(key, value, initial):
    if key == "quest_type":
        return {
            label: identifier for identifier, label in QUEST_TYPE_LABELS.items()
        }.get(value, value)
    if isinstance(initial, (dict, list)):
        import json

        parsed = json.loads(value)
        if type(parsed) is not type(initial):
            raise ValueError("Structure JSON incompatible.")
        return parsed
    if type(initial) is bool:
        return value == "Oui"
    if (
        key in DECIMAL_FIELDS
        or key.endswith(("_base", "_growth"))
        or type(initial) is float
    ):
        return float(value.strip().replace(",", "."))
    if type(initial) is int:
        return int(value)
    return value
