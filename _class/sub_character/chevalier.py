from _class.character import Character
from _class.skill import Skill
from ..stats.basic_stat import Aura

class Chevalier(Character):
    class_skills_dict = {
        "level 1": {
            "Sword Slash": Skill("Sword Slash", "damage", 25, 8, "hp"),
        },
        "level 5": {
            "Shield Bash": Skill("Shield Bash", "damage", 20, 6, "hp"),
        },
        "level 10": {
            "Charge": Skill("Charge", "buff", 10, 5, "hp"),
        },
        "level 20": {
            "Holy Strike": Skill("Holy Strike", "damage", 40, 12),
        },
    }

    def __init__(self, user_id: str, name: str):
        super().__init__(user_id, name, hp=250, force=17, endurance=12, inteligence=2, energie=14, skills=self.class_skills_dict["level 1"])
        self.energie = self.energie.change_type(Aura)