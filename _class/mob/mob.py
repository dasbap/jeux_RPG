from ..character import Character
from ..skill import Skill
from ..stats.basic_stat import Mana

class Mob(Character):
    class_skills_dict = {
        "level 1": {
            "Attack": Skill("Attack", "damage", 5, 2, "hp"),
        },
        "level 5": {
            "Garde": Skill("Pack de sang", "buff", 20, 1, "hp"),
        },
        "level 10": {
            Skill("bite", "damage",40,10, "hp")
    }}
    
    def __init__(self, user_id: str, name: str, xp_drop: int = 0):
        super().__init__(user_id, name, hp=250, force=17, endurance=12, inteligence=2, energie=14, skills=self.class_skills_dict["level 1"])
        self.energie = self.energie.change_type(Mana)
        if xp_drop > 0:
            self.gain_exp(xp_drop)
    
    def exp_for_level_up(self):
        return self.level * 10

