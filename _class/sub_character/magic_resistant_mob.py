from jeuxRPG._class.character import Character
from jeuxRPG._class.res.dictType import ClassSkills
from jeuxRPG._class.res.character.table_stat_subclass import magic_resistant_mob_table


class MagicResistantMob(Character):
    """Non-playable mob resilient to magic damage."""

    is_playable: bool = False
    class_skills_dict: ClassSkills = magic_resistant_mob_table["class_skills_dict"]

    def __init__(self, user_id: str, name: str):
        super().__init__(
            user_id=user_id,
            name=name,
            class_table=magic_resistant_mob_table.copy(),
        )
