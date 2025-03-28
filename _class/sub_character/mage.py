from _class.character import Character
from _class.skill import Skill
from ..stats.basic_stat import Mana
class Mage(Character):
    class_skills_dict = {
        "level 1": {
            "Fire Ball": Skill("Fire Ball", "damage", 10, 3, "hp"),
        },
        "level 5": {
            "Thunder": Skill("Thunder", "damage", 15, 5, "hp"),
        },
        "level 10": {
            "Ice Trap": Skill("Ice Trap", "debuff", 4, 10, "mana"),
        },
        "level 20": {
            "Arcane Blast": Skill("Arcane Blast", "damage", 40, 30),
        },
    }

    def __init__(self, user_id: str, name: str):
        super().__init__(user_id, name, hp=80, force=5, endurance=3, inteligence=19, energie=35, skills=self.class_skills_dict["level 1"])
        self.energie = self.energie.change_type(Mana)