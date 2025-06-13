from typing import Dict
from _class.character import Character
from _class.res.classType import ClassType, SkillType
from _class.skills.skill import Skill
from _class.skills.skillEffect import SkillEffect


class Archer(Character):
    """Classe représentant un Archer, spécialisé dans les attaques à distance."""
    
    class_skills_dict: Dict[str, Dict[str, Skill]] = {
        "level 1": {
            "Arrow Rain": Skill(
                name="Arrow Rain",
                skill_type=SkillType.DAMAGE,
                effects={"damage": SkillEffect(value=20)},
                energie_cost=12,
                description="Pluie de flèches infligeant des dégâts à zone"
            ),
        },
        "level 5": {
            "Piercing Shot": Skill(
                name="Piercing Shot",
                skill_type=SkillType.DAMAGE,
                effects={"damage": SkillEffect(value=30)},
                energie_cost=15,
                description="Tir perforant traversant les défenses"
            ),
        },
        "level 10": {
            "Camouflage": Skill(
                name="Camouflage",
                skill_type=SkillType.BUFF,
                effects={
                    "evasion": SkillEffect(value=15, duration=3, stat_target="evasion"),
                    "critical": SkillEffect(value=10, duration=3, stat_target="critical")
                },
                energie_cost=8,
                description="Augmente l'évasion et le taux critique pendant 3 tours"
            ),
        },
        "level 20": {
            "Explosive Arrow": Skill(
                name="Explosive Arrow",
                skill_type=SkillType.DAMAGE,
                effects={"damage": SkillEffect(value=50)},
                energie_cost=25,
                cooldown=3,
                description="Flèche explosive causant des dégâts massifs"
            ),
        },
    }

    def __init__(self, user_id: str, name: str):
        """Initialise un Archer avec ses statistiques de base.
        
        Args:
            user_id: Identifiant unique du joueur
            name: Nom du personnage
        """
        super().__init__(
            user_id=user_id,
            name=name,
            hp=100,
            force=12,
            endurance=8,
            intelligence=4,
            energie=15,
            skills=self.class_skills_dict["level 1"].copy()
        )
        self.class_type = ClassType.DAMAGE