class Mage(Character):
    """Classe représentant un Mage, spécialisé dans les sorts offensifs et de contrôle."""
    
    class_skills_dict: Dict[str, Dict[str, Skill]] = {
        "level 1": {
            "Fire Ball": Skill(
                name="Fire Ball",
                skill_type=SkillType.INVOCATION,
                effects={"invocation": SkillEffect(value=10)},
                energie_cost=3,
                description="Boule de feu élémentaire"
            ),
        },
        "level 5": {
            "Thunder": Skill(
                name="Thunder",
                skill_type=SkillType.DAMAGE,
                effects={"damage": SkillEffect(value=15)},
                energie_cost=5,
                cooldown=1,
                description="Décharge électrique frappant l'ennemi"
            ),
        },
        "level 20": {
            "Arcane Blast": Skill(
                name="Arcane Blast",
                skill_type=SkillType.DAMAGE,
                effects={"damage": SkillEffect(value=40)},
                energie_cost=30,
                cooldown=5,
                description="Explosion arcanique puissante"
            ),
        },
    }

    def __init__(self, user_id: str, name: str):
        super().__init__(
            user_id=user_id,
            name=name,
            hp=80,
            force=5,
            endurance=3,
            intelligence=19,
            energie=35,
            skills=self.class_skills_dict["level 1"].copy()
        )
        self.class_type = ClassType.DAMAGE

