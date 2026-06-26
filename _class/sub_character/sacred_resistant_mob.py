from jeuxRPG._class.character import Character
from jeuxRPG._class.res.dictType import ClassSkills
from jeuxRPG._class.res.character.table_stat_subclass import sacred_resistant_mob_table


class SacredResistantMob(Character):
    """Non-playable mob resilient to sacred damage."""

    is_playable: bool = False
    class_skills_dict: ClassSkills = sacred_resistant_mob_table["class_skills_dict"]

    def __init__(self, user_id: str, name: str):
        super().__init__(
            user_id=user_id,
            name=name,
            class_table=sacred_resistant_mob_table.copy(),
        )
