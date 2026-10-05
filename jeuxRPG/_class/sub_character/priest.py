
from jeuxRPG._class.character import Character
from jeuxRPG._class.res.character.table_stat_subclass import priest_table


class Priest(Character):
    """Classe représentant un Prêtre, spécialisé dans les soins et soutien."""
    
    is_playable: bool = True
    class_skills_dict = priest_table["class_skills_dict"]
    
    def __init__(self, user_id: str, name: str):
        super().__init__(
            user_id=user_id,
            name=name,
            class_table=priest_table.copy(),
        )