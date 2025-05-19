from _class.character import Character
from _class.skill import Skill, SkillEffect, SkillType


class Mob(Character):
    class_skills_dict = {
    "level 1": {
        "Attack": Skill(
            name="Attack",
            skill_type=SkillType.DAMAGE,
            effects={"damage": SkillEffect(value=5)},
            energie_cost=2
        )
    },
    "level 5": {
        "Pack de sang": Skill(
            name="Pack de sang",
            skill_type=SkillType.BUFF,
            effects={"hp": SkillEffect(value=20, duration=1)},
            energie_cost=5
        )
    },
    "level 10": {
        "Bite": Skill(
            name="Bite",
            skill_type=SkillType.DAMAGE,
            effects={"damage": SkillEffect(value=40)},
            energie_cost=10
        )
    }
}

    
    def __init__(self, user_id: str, name: str, xp_drop: int = 0):
        super().__init__(user_id, name, hp=250, force=17, endurance=12, intelligence=2, energie=14, skills=self.class_skills_dict["level 1"])
        if xp_drop > 0:
            self.gain_exp(xp_drop)
    
    def exp_for_level_up(self):
        return self.level * 10

class Boss:
    def __init__(self):
        pass

class Minion:
    def __init__(self):
        pass