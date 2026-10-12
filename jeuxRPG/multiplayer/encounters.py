from .content import DATA


RANKS = {"SSS": 8, "SS": 7, "S": 6, "AA": 5, "A": 4, "B": 3, "C": 2, "D": 1, "E": 0}
GOBLIN_CHAIN = tuple(DATA['gameplay']['encounter_chain'])
RULES = DATA['gameplay']['rules']['encounters']


def probabilities(rank, player_level, zone_level):
    if rank not in RANKS:
        raise ValueError("Rang inconnu")
    if rank == "E":
        return (0,) * len(GOBLIN_CHAIN)
    factor = max(RULES['factor_min'], min(RULES['factor_max'], RULES['difficulty_base'] ** (max(-RULES['delta_limit'], min(RULES['delta_limit'], (zone_level - player_level) / RULES['level_divisor'])))))
    weight = RANKS[rank]
    first = GOBLIN_CHAIN[0] if rank == "D" else 1.0
    return tuple(min(1.0, value * factor / (weight ** index)) for index, value in enumerate((first, *GOBLIN_CHAIN[1:])))


def group_size(rank, player_level, zone_level, random):
    count = 0
    for chance in probabilities(rank, player_level, zone_level):
        if chance <= 0 or random() >= chance:
            break
        count += 1
    return count
