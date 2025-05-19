from _class.character import Character
from _class.skill import Skill
from ..stats.basic_stat import Aura
from typing import Dict
from _class.skill import Skill, SkillType, SkillEffect
from ..stats.basic_stat import Aura, Mana

class Knight(Character):
    """Classe représentant un Knight, tank résistant avec des capacités défensives."""
    
    class_skills_dict: Dict[str, Dict[str, Skill]] = {
        "level 1": {
            "Sword Slash": Skill(
                name="Sword Slash",
                skill_type=SkillType.DAMAGE,
                effects={"damage": SkillEffect(value=25)},
                energie_cost=8,
                energie_target= Aura,
                description="Coup d'épée de base"
            ),
        },
        "level 5": {
            "Shield Bash": Skill(
                name="Shield Bash",
                skill_type=SkillType.DAMAGE,
                effects={
                    "damage": SkillEffect(value=20),
                    "stun": SkillEffect(value=1, duration=1, stat_target="stun")
                },
                energie_cost=6,
                energie_target= Aura,
                cooldown=2,
                description="Coup de bouclier pouvant étourdir"
            ),
        },
        "level 10": {
            "Charge": Skill(
                name="Charge",
                skill_type=SkillType.BUFF,
                effects={
                    "attack": SkillEffect(value=10, duration=2, stat_target="attack"),
                    "defense": SkillEffect(value=-5, duration=2, stat_target="defense")
                },
                energie_cost=5,
                energie_target= Aura,
                cooldown=3,
                description="Augmente l'attaque mais réduit la défense temporairement"
            ),
        },
        "level 20": {
            "Holy Strike": Skill(
                name="Holy Strike",
                skill_type=SkillType.DAMAGE,
                effects={"damage": SkillEffect(value=40)},
                energie_cost=12,
                energie_target= Aura,
                cooldown=4,
                description="Coup sacré infligeant des dégâts importants"
            ),
        },
    }

    def __init__(self, user_id: str, name: str):
        super().__init__(
            user_id=user_id,
            name=name,
            hp=250,
            force=17,
            endurance=12,
            intelligence=2,
            energie=14,
            skills=self.class_skills_dict["level 1"].copy()
        )
        
        self.change_energie(Mana, Aura)
        self.base_defense = 15
