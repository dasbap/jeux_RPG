from _class.character import Character
from _class.skill import Skill
from ..stats.basic_stat import Foie
from typing import Dict
from _class.skill import Skill, SkillType, SkillEffect
from ..stats.basic_stat import Foie, Mana

class Priest(Character):
    """Classe représentant un Prêtre, spécialisé dans les soins et soutien."""
    
    class_skills_dict: Dict[str, Dict[str, Skill]] = {
        "level 1": {
            "Heal": Skill(
                name="Heal",
                skill_type=SkillType.HEAL,
                effects={"heal": SkillEffect(value=30)},
                energie_cost=10,
                energie_target = Foie,
                description="Soigne un allié"
            ),
        },
        "level 5": {
            "Blessing": Skill(
                name="Blessing",
                skill_type=SkillType.BUFF,
                effects={
                    "defense": SkillEffect(value=10, duration=3, stat_target="defense"),
                    "resistance": SkillEffect(value=10, duration=3, stat_target="resistance")
                },
                energie_cost=5,
                energie_target = Foie,
                cooldown=2,
                description="Augmente la défense et résistance magique"
            ),
        },
        "level 10": {
            "Divine Shield": Skill(
                name="Divine Shield",
                skill_type=SkillType.BUFF,
                effects={"shield": SkillEffect(value=15, duration=2, stat_target="shield")},
                energie_cost=8,
                energie_target = Foie,
                cooldown=3,
                description="Protège un allié avec un bouclier divin"
            ),
        },
        "level 20": {
            "Resurrection": Skill(
                name="Resurrection",
                skill_type=SkillType.RESURRECT,
                effects={"resurrect": SkillEffect(value=1)},
                energie_cost=50,
                energie_target = Foie,
                cooldown=10,
                description="Ressuscite un allié mort"
            ),
        },
    }

    def __init__(self, user_id: str, name: str):
        super().__init__(
            user_id=user_id,
            name=name,
            hp=100,
            force=3,
            endurance=4,
            intelligence=15,
            energie=30,
            skills=self.class_skills_dict["level 1"].copy()
        )
        self.change_energie(Mana,Foie)
        self.healing_power = 1.2 