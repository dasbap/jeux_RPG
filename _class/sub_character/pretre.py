from _class.character import Character
from _class.skill import Skill
from ..stats.basic_stat import Foie
class Prêtre(Character):
    class_skills_dict = {
        "level 1": {
            "Heal": Skill("Heal", "heal", 30, 10, "mana"),
        },
        "level 5": {
            "Blessing": Skill("Blessing", "buff", 10, 5, "mana"),
        },
        "level 10": {
            "Divine Shield": Skill("Divine Shield", "buff", 15, 8, "hp"),
        },
        "level 20": {
            "Resurrection": Skill("Resurrection", "resurrect", 1, 50, "mana"),
        },
    }

    def __init__(self, user_id: str, name: str):
        super().__init__(user_id, name, hp=100, force=3, endurance=4, inteligence=15, energie=30, skills=self.class_skills_dict["level 1"])
        self.energie = self.energie.change_type(Foie)