from jeuxRPG._class.place.town import Town


def make_basic_town() -> Town:
    """Create and return a basic Town instance with four districts.

    This factory avoids creating objects at import time.
    """
    basic_town = Town("default", 0, 0, 0)
    for direction in ["north", "south", "east", "west"]:
        basic_town.create_new_district("district " + direction)
    return basic_town
