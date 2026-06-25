from jeuxRPG._class.character import Character
from jeuxRPG._class.res.dictType import ClassSkills
from jeuxRPG._class.res.character.table_stat_subclass import dragon_whelp_table


class DragonWhelp(Character):
    """Classe représentant un Dragon Whelp (mob non jouable)."""
    
    is_playable: bool = False
    class_skills_dict: ClassSkills = dragon_whelp_table["class_skills_dict"]

    def __init__(self, user_id: str, name: str):
        super().__init__(
            user_id=user_id,
            name=name,
            class_table=dragon_whelp_table.copy(),
        )
