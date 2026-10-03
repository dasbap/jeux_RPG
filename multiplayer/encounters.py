RANKS = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1, "E": 0}
GOBLIN_CHAIN = (0.9, 0.3, 0.1, 0.03, 0.001)


def probabilities(rank, player_level, zone_level):
    if rank not in RANKS:
        raise ValueError("Rang inconnu")
    if rank == "E":
        return (0, 0, 0, 0, 0)
    factor = max(0.25, min(1.5, 2 ** (max(-10, min(10, (zone_level - player_level) / 5)))))
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
