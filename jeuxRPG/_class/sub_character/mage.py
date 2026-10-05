from jeuxRPG._class.character import Character
from jeuxRPG._class.res.character.table_stat_subclass import mage_table


class Mage(Character):
    """Classe représentant un Mage, spécialisé dans les sorts offensifs et de contrôle."""
    
    is_playable: bool = True
    class_skills_dict = mage_table["class_skills_dict"]
    
    def __init__(self, user_id: str, name: str):
        super().__init__(
            user_id=user_id,
            name=name,
            class_table=mage_table.copy(),
        )

