RANKS = ("SSS", "SS", "S", "AA", "A", "B", "C", "D", "E")


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


def parse_field(key, value, initial):
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
