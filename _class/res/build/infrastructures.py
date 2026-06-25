from typing import Dict


def get_base_buildings() -> Dict[str, "Building"]:
    """Return a fresh dict of base Building instances.

    Instances are created on demand to avoid side-effects at import time.
    """
    from jeuxRPG._class.place.building import Building
    from jeuxRPG._class.res.classType import Build_state, Build_type

    return {
        "Forge": Building("Forge", Build_type.FORGE, 1, Build_state.OPERATIONAL),
        "Magic_tower": Building("Magic_tower", Build_type.MAGIC_TOWER, 1, Build_state.OPERATIONAL),
        "Milice": Building("Milice", Build_type.MILICE, 1, Build_state.OPERATIONAL),
        "House": Building("House", Build_type.HOUSE, 1, Build_state.OPERATIONAL),
        "Dojo": Building("Dojo", Build_type.TRAINING, 1, Build_state.OPERATIONAL),
    }