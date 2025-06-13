from _class.character import Character
from _class.res.dictType import ClassSkills

from _class.res.character.table_stat_subclass import knight_table

class Knight(Character):
    """Classe représentant un Knight, tank résistant avec des capacités défensives."""
    class_skills_dict : ClassSkills = knight_table["class_skills_dict"]
    
    def __init__(self, user_id: str, name: str):
        super().__init__(
            user_id=user_id,
            name=name,
            class_table=knight_table.copy(),
        )
