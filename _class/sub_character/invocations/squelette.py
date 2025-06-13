from _class.character import Character

from _class.res.dictType import ClassSkills
from _class.sub_character.invocations.invocation import Invocation

from _class.res.character.table_stat_subclass import squelette_table

class Squelette(Invocation):
    class_skills_dict : ClassSkills = squelette_table["class_skills_dict"]
    def __init__(self, master : Character, name=None, level : str = "BL"):
        self.level = level
        super().__init__(master,squelette_table,name,
                        skills = Squelette.class_skills_dict[level].copy())
    
    def can_level_up(self):
        return False
    def _required_exp_for_next_level(self):
        return 0
    def level_up(self):
        return f"{self.name} can't level up"