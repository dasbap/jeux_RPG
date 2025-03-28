from _class.character import Character
from _class.skill import Skill
from ..stats.basic_stat import Mana

class Archer(Character):
    def camouflage(caster : 'Archer',target : Character, mana_cost: int = 8):
        """Applique l'effet Camouflage au personnage."""
        if "Camouflage" in target.status:
            raise ValueError("Camouflage is already applied.")
        if mana_cost <= 0:
            raise ValueError("Mana cost must be greater than 0.")
        if caster.mana < mana_cost:
            raise ValueError(f"Not enough mana to apply Camouflage for {target.name}.")
        target.status["Camouflage"] = {
            "description": "Increases damage and debuffs inflicted by skills.",
            "duration": 2,
        }
        caster.mana -= mana_cost
        print(f"{target.name} has applied Camouflage.")

    class_skills_dict = {
        "level 1": {
            "Arrow Rain": Skill("Arrow Rain", "damage", 20, 12, "hp"),
        },
        "level 5": {
            "Piercing Shot": Skill("Piercing Shot", "damage", 30, 15, "hp"),
        },
        "level 10": {
            "Camouflage": Skill("Camouflage", "buff", 10, 8, "mana", camouflage),
        },
        "level 20": {
            "Explosive Arrow": Skill("Explosive Arrow", "damage", 50, 25),
        },
    }

    def __init__(self, user_id: str, name: str):
        super().__init__(user_id, name, hp=100, force=12, endurance=8, inteligence=4, energie=15, skills=self.class_skills_dict["level 1"])
        self.energie = self.energie.change_type(Mana)