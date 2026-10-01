from copy import deepcopy

from jeuxRPG._class.res.advantage import Advantage

from jeuxRPG._class.res.character.alteration.alteration import AlterationType
from jeuxRPG._class.res.character.stats.basic_stat import HP, Aura, Endurance, Foie, Force, Intelligence, Mana, Sagesse

from jeuxRPG._class.res.classType import ClassType, DamageType, SkillType
from jeuxRPG._class.res.dictType import ClassTable

from jeuxRPG._class.skills.skill import Skill
from jeuxRPG._class.skills.skillEffect import SkillEffect

from jeuxRPG._function.skill.custom import multy_action_skill


knight_advantage = Advantage()
knight_advantage.add_resilience(DamageType.PHYSICAL)
knight_advantage.add_weakness(DamageType.MAGIC)


knight_table : ClassTable = {
    "base_stats":{
        "hp":25,
        "force":5,
        "endurance": 9,
        "intelligence":2,
        "sagesse": 6,
        "energie": {
            1:{
                "type" : Aura,
                "value" : 14,
                "regen_rate" : 0.3
            }
        }
    },
    "upgrade_stats":{
        1:{
            HP:15,
            Force:3,
            Endurance: 5,
            Intelligence:1,
            Sagesse: 2,
            "Energie": {
                Aura : 3
            },
        },
        15:{
            HP:3,
            Force:1,
            Endurance: 1,
            Sagesse: 6,
            "Energie": {
                Aura : 1
            },
        },
        20:{
            Endurance: 2,
            Sagesse: 4,
            "Energie": {
                Aura : 25
            },
            "new":{
                "Energie":{
                    Foie : 90
                },
            }
        },
        21:{
            HP: 2,
            Endurance: 1,
            Sagesse: 1,
            "Energie": {
                Aura : 1,
                Foie : 10
            },
        }
    },
    "advantage": deepcopy(knight_advantage),
    "class_type": ClassType.SHIELD,
    "class_skills_dict" : {
        "level 1": {
            "Sword Slash": Skill(
                name="Sword Slash",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=11)},
                energie_cost=8,
                energie_target= Aura,
                cooldown=0,
                description="Coup d'épée de base"
            ),
        },
        "level 5": {
            "Shield Bash": Skill(
                name="Shield Bash",
                skill_type=SkillType.DAMAGE,
                custom_action= multy_action_skill,
                damage_type=DamageType.PHYSICAL,
                effects={
                    "damage": SkillEffect(value=4, name="Shield Bash"),
                    "Stun": SkillEffect(duration=1,name="Shield Bash",alterationtype=AlterationType.STUN)
                },
                energie_cost=6,
                energie_target= Aura,
                cooldown=2,
                description="Coup de bouclier"
            ),
        },
        "level 10": {
            "Charge": Skill(
                name="Charge",
                skill_type=SkillType.BUFF,
                effects={
                    "Buff": SkillEffect(value=10,name="Charge", duration=3, stat_target=Force, alterationtype=AlterationType.BUFFSTAT),
                    "Debuff": SkillEffect(value=5,name="Charge Side effect", duration=3, stat_target=Endurance, alterationtype=AlterationType.DEBUFFSTAT)
                },
                require_target=False,
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
                damage_type=DamageType.SACRED,
                effects={"damage": SkillEffect(value=40)},
                energie_cost=12,
                energie_target= Foie,
                cooldown=4,
                description="Coup sacré infligeant des dégâts importants"
            ),
        },
    }
}

necromancien_table : ClassTable = {
    "base_stats":{
        "hp":15,
        "force":3,
        "endurance": 2,
        "intelligence":16,
        "sagesse": 4,
        "energie": {
            1:{
                "type" : Mana,
                "value" : 21,
                "regen_rate" : 0.4
            }
        }
    },
    "upgrade_stats":{
        1:{
            HP:2,
            Force:2,
            Endurance: 1,
            Intelligence:3,
            Sagesse: 1,
            "Energie": {
                Mana : 4
            },
        },
        15:{
            HP:2,
            Sagesse: 6,
            Intelligence:2,
            "Energie": {
                Mana : 1
            },
        },
        20:{
            Endurance: 2,
            Sagesse: 4,
            "Energie": {
                Mana : 9
            },
        },
        21:{
            HP: 4,
            Endurance: 1,
            Intelligence: 2,
            "Energie": {
                Mana : 1,
            },
        }
    },
    "advantage": {
        "resilient": [DamageType.MAGIC],
        "weak": [DamageType.PHYSICAL,DamageType.SACRED]
        },
    "class_type": ClassType.SUMMONER,
    "class_skills_dict" : {
        "level 1": {
            "Low Skull": Skill(
                name="Low Skull",
                skill_type=SkillType.INVOCATION,
                effects={"invocation": SkillEffect(invocation = {"class" : "Squelette",
                                                                "level": "BL",
                                                                "id":"-1"})},
                energie_cost=15,
                description="invoque un faible squelette"
            ),
        },
    }
}

squelette_table : ClassTable = {
    "base_stats":{
        "hp":15,
        "force":10,
        "endurance": 3,
        "intelligence":1,
        "sagesse": 1,
        "energie": {
            1:{
                "type" : Mana,
                "value" : 24,
                "regen_rate" : 0.4
            }
        }
    },
    "advantage": {
        "resilient": [DamageType.MAGIC],
        "weak": [DamageType.SACRED]
        },
    "class_type": ClassType.INVOCATION,
    "class_skills_dict" : {
        "BL": {
            "Sword Slash": Skill(
                name="Sword Slash",
                skill_type=SkillType.DAMAGE,
                damage_type= DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=12)},
                energie_cost=8,
                energie_target= Mana,
                description="Coup d'épée de base"
            ),
        },
        "NL": {
            "headbutt": Skill(
                name="headbutt",
                skill_type=SkillType.DAMAGE,
                damage_type= DamageType.PHYSICAL,
                effects={
                    "damage": SkillEffect(value=20),
                },
                energie_cost=6,
                energie_target= Mana,
                cooldown=2,
                description="Coup de tête"
            ),
        },
        "HL": {
            "Charge": Skill(
                name="Charge",
                skill_type=SkillType.BUFF,
                effects={
                    "attack": SkillEffect(value=15, duration=2, stat_target=Force),
                },
                energie_cost=5,
                energie_target= Mana,
                cooldown=3,
                description="Augmente l'attaque temporairement"
            ),
            "Sword Slash": Skill(
                name="Sword Slash",
                skill_type=SkillType.DAMAGE,
                damage_type= DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=12)},
                energie_cost=8,
                energie_target= Mana,
                description="Coup d'épée de base"
            ),
        },
        "THL": {
            "Strike": Skill(
                name="Strike",
                skill_type=SkillType.DAMAGE,
                damage_type= DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=40)},
                energie_cost=12,
                energie_target= Mana,
                cooldown=4,
                description="Coup infligeant des dégâts importants"
            ),
        }
    }
}

# --- Heroic-Fantasy Creatures ----------------------------------------------

goblin_table: ClassTable = {
    "base_stats": {
        "hp": 14,
        "force": 6,
        "endurance": 2,
        "intelligence": 2,
        "sagesse": 1,
        "energie": {
            1: {"type": Mana, "value": 10, "regen_rate": 0.2}
        },
    },
    "upgrade_stats": {
        1: {HP: 2, Force: 1, "Energie": {Mana: 1}},
        5: {HP: 1, Force: 1},
    },
    "advantage": {"weakness": [], "resilience": []},
    "class_type": ClassType.DAMAGE,
    "class_skills_dict": {
        "level 1": {
            "Stab": Skill(
                name="Stab",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=6)},
                energie_cost=2,
                energie_target=Mana,
                description="Coupe rapide de gobelin",
            ),
            "Dirty Tricks": Skill(
                name="Dirty Tricks",
                skill_type=SkillType.DEBUFF,
                effects={
                    "Debuff": SkillEffect(value=2, name="Dirty Tricks", duration=2, stat_target=Endurance, alterationtype=AlterationType.DEBUFFSTAT)
                },
                energie_cost=3,
                energie_target=Mana,
                cooldown=1,
                description="Fourberie: affaiblit l'endurance",
            ),
        }
    },
}

orc_table: ClassTable = {
    "base_stats": {
        "hp": 28,
        "force": 10,
        "endurance": 6,
        "intelligence": 1,
        "sagesse": 2,
        "energie": {
            1: {"type": Aura, "value": 12, "regen_rate": 0.3}
        },
    },
    "upgrade_stats": {
        1: {HP: 6, Force: 3, Endurance: 2, "Energie": {Aura: 2}},
        10: {HP: 3, Force: 2},
    },
    "advantage": {"weakness": [], "resilience": []},
    "class_type": ClassType.SHIELD,
    "class_skills_dict": {
        "level 1": {
            "Cleave": Skill(
                name="Cleave",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=12)},
                energie_cost=5,
                energie_target=Aura,
                cooldown=1,
                description="Frappe lourde orque",
            ),
            "Rally": Skill(
                name="Rally",
                skill_type=SkillType.BUFF,
                effects={
                    "Buff": SkillEffect(value=3, name="Rally", duration=2, stat_target=Force, alterationtype=AlterationType.BUFFSTAT)
                },
                require_target=False,
                energie_cost=4,
                energie_target=Aura,
                cooldown=2,
                description="Cri de guerre: renforce la force",
            ),
        }
    },
}

dragon_whelp_table: ClassTable = {
    "base_stats": {
        "hp": 22,
        "force": 4,
        "endurance": 4,
        "intelligence": 9,
        "sagesse": 6,
        "energie": {
            1: {"type": Mana, "value": 24, "regen_rate": 0.4}
        },
    },
    "upgrade_stats": {
        1: {HP: 3, Intelligence: 2, Sagesse: 1, "Energie": {Mana: 3}},
        10: {HP: 2, Intelligence: 2},
    },
    "advantage": {"weakness": [], "resilience": []},
    "class_type": ClassType.DAMAGE,
    "class_skills_dict": {
        "level 1": {
            "Small Breath": Skill(
                name="Small Breath",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.MAGIC,
                effects={"damage": SkillEffect(value=11)},
                energie_cost=6,
                energie_target=Mana,
                cooldown=1,
                description="Petit souffle draconique",
            ),
            "Wing Buffet": Skill(
                name="Wing Buffet",
                skill_type=SkillType.DAMAGE,
                custom_action= multy_action_skill,
                effects={
                    "damage": SkillEffect(value=3, name="Wing Buffet"),
                    "Stun": SkillEffect(duration=1, name="Wing Buffet", alterationtype=AlterationType.STUN)
                },
                energie_cost=5,
                energie_target=Mana,
                cooldown=2,
                description="Coup d'aile étourdissant",
            ),
        }
    },
}

physical_resistant_mob_table: ClassTable = {
    "base_stats": {
        "hp": 24,
        "force": 8,
        "endurance": 8,
        "intelligence": 2,
        "sagesse": 3,
        "energie": {
            1: {"type": Aura, "value": 14, "regen_rate": 0.25}
        },
    },
    "upgrade_stats": {
        1: {HP: 5, Force: 2, Endurance: 3, "Energie": {Aura: 2}},
        10: {HP: 3, Endurance: 2},
    },
    "advantage": {"weakness": [DamageType.MAGIC], "resilience": [DamageType.PHYSICAL]},
    "class_type": ClassType.SHIELD,
    "class_skills_dict": {
        "level 1": {
            "Crushing Blow": Skill(
                name="Crushing Blow",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=9)},
                energie_cost=4,
                energie_target=Aura,
                cooldown=1,
                description="Frappe lourde d'un gardien cuirasse",
            ),
        }
    },
}

magic_resistant_mob_table: ClassTable = {
    "base_stats": {
        "hp": 18,
        "force": 3,
        "endurance": 4,
        "intelligence": 10,
        "sagesse": 5,
        "energie": {
            1: {"type": Mana, "value": 22, "regen_rate": 0.35}
        },
    },
    "upgrade_stats": {
        1: {HP: 3, Intelligence: 3, Sagesse: 1, "Energie": {Mana: 3}},
        10: {HP: 2, Intelligence: 2},
    },
    "advantage": {"weakness": [DamageType.SACRED], "resilience": [DamageType.MAGIC]},
    "class_type": ClassType.DAMAGE,
    "class_skills_dict": {
        "level 1": {
            "Arcane Spark": Skill(
                name="Arcane Spark",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.MAGIC,
                effects={"damage": SkillEffect(value=10)},
                energie_cost=5,
                energie_target=Mana,
                cooldown=1,
                description="Eclat magique concentre",
            ),
        }
    },
}

sacred_resistant_mob_table: ClassTable = {
    "base_stats": {
        "hp": 20,
        "force": 4,
        "endurance": 5,
        "intelligence": 4,
        "sagesse": 10,
        "energie": {
            1: {"type": Foie, "value": 20, "regen_rate": 0.3}
        },
    },
    "upgrade_stats": {
        1: {HP: 3, Endurance: 1, Sagesse: 3, "Energie": {Foie: 3}},
        10: {HP: 2, Sagesse: 2},
    },
    "advantage": {"weakness": [DamageType.PHYSICAL], "resilience": [DamageType.SACRED]},
    "class_type": ClassType.DAMAGE,
    "class_skills_dict": {
        "level 1": {
            "Radiant Smite": Skill(
                name="Radiant Smite",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.SACRED,
                effects={"damage": SkillEffect(value=10)},
                energie_cost=5,
                energie_target=Foie,
                cooldown=1,
                description="Impact sacre focalise",
            ),
        }
    },
}

priest_table: ClassTable = {
    "base_stats": {
        "hp": 20,
        "force": 3,
        "endurance": 4,
        "intelligence": 10,
        "sagesse": 14,
        "energie": {
            1: {
                "type": Foie,
                "value": 30,
                "regen_rate": 0.3
            }
        }
    },
    "upgrade_stats": {
        1: {
            HP: 5,
            Force: 1,
            Endurance: 2,
            Intelligence: 3,
            Sagesse: 5,
            "Energie": {Foie: 5}
        },
        15: {
            HP: 2,
            Sagesse: 3,
            Intelligence: 2,
            "Energie": {Foie: 2}
        },
        20: {
            Endurance: 3,
            Sagesse: 4,
            "Energie": {Foie: 3}
        }
    },
    "class_type": ClassType.HEAL,
    "class_skills_dict": {
        "level 1": {
            "Heal": Skill(
                name="Heal",
                skill_type=SkillType.HEAL,
                effects={"heal": SkillEffect(value=30, stat_target=HP)},
                energie_cost=10,
                energie_target=Foie,
                description="Soigne un allié"
            ),
        },
        "level 5": {
            "Blessing": Skill(
                name="Blessing",
                skill_type=SkillType.BUFF,
                effects={
                    "defense": SkillEffect(name="Blessing Defense", value=10, duration=3, stat_target=Endurance, alterationtype=AlterationType.BUFFSTAT),
                },
                energie_cost=5,
                energie_target=Foie,
                cooldown=2,
                description="Augmente la défense et résistance magique"
            ),
        },
        "level 10": {
            "Divine Shield": Skill(
                name="Divine Shield",
                skill_type=SkillType.BUFF,
                effects={"shield": SkillEffect(value=15, duration=2, stat_target=HP)},
                energie_cost=8,
                energie_target=Foie,
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
                energie_target=Foie,
                cooldown=10,
                description="Ressuscite un allié mort"
            ),
        },
    }
}

archer_table: ClassTable = {
    "base_stats": {
        "hp": 22,
        "force": 10,
        "endurance": 6,
        "intelligence": 4,
        "sagesse": 7,
        "energie": {
            1: {
                "type": Mana,
                "value": 15,
                "regen_rate": 0.25
            }
        }
    },
    "upgrade_stats": {
        1: {
            HP: 4,
            Force: 3,
            Endurance: 2,
            Intelligence: 1,
            Sagesse: 2,
            "Energie": {Mana: 3}
        },
        15: {
            HP: 2,
            Force: 2,
            Intelligence: 1,
            "Energie": {Mana: 2}
        },
        20: {
            Endurance: 2,
            Force: 2,
            "Energie": {Mana: 2}
        }
    },
    "class_type": ClassType.DAMAGE,
    "class_skills_dict": {
        "level 1": {
            "Arrow Rain": Skill(
                name="Arrow Rain",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=20)},
                energie_cost=12,
                energie_target=Mana,
                description="Pluie de flèches infligeant des dégâts à zone"
            ),
        },
        "level 5": {
            "Piercing Shot": Skill(
                name="Piercing Shot",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=30)},
                energie_cost=15,
                energie_target=Mana,
                description="Tir perforant traversant les défenses"
            ),
        },
        "level 10": {
            "Camouflage": Skill(
                name="Camouflage",
                skill_type=SkillType.BUFF,
                effects={
                    "evasion": SkillEffect(value=15, duration=3, stat_target=Force),
                },
                energie_cost=8,
                energie_target=Mana,
                description="Augmente l'évasion et le taux critique pendant 3 tours"
            ),
        },
        "level 20": {
            "Explosive Arrow": Skill(
                name="Explosive Arrow",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=50)},
                energie_cost=25,
                energie_target=Mana,
                cooldown=3,
                description="Flèche explosive causant des dégâts massifs"
            ),
        },
    }
}

mage_table: ClassTable = {
    "base_stats": {
        "hp": 18,
        "force": 3,
        "endurance": 2,
        "intelligence": 16,
        "sagesse": 8,
        "energie": {
            1: {
                "type": Mana,
                "value": 35,
                "regen_rate": 0.4
            }
        }
    },
    "upgrade_stats": {
        1: {
            HP: 3,
            Force: 1,
            Endurance: 1,
            Intelligence: 5,
            Sagesse: 2,
            "Energie": {Mana: 6}
        },
        15: {
            HP: 1,
            Intelligence: 3,
            Sagesse: 2,
            "Energie": {Mana: 3}
        },
        20: {
            Intelligence: 2,
            "Energie": {Mana: 4}
        }
    },
    "class_type": ClassType.DAMAGE,
    "class_skills_dict": {
        "level 1": {
            "Fire Ball": Skill(
                name="Fire Ball",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.MAGIC,
                effects={"damage": SkillEffect(value=15)},
                energie_cost=10,
                energie_target=Mana,
                description="Boule de feu élémentaire"
            ),
        },
        "level 5": {
            "Thunder": Skill(
                name="Thunder",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.MAGIC,
                effects={"damage": SkillEffect(value=20)},
                energie_cost=12,
                energie_target=Mana,
                cooldown=1,
                description="Décharge électrique frappant l'ennemi"
            ),
        },
        "level 20": {
            "Arcane Blast": Skill(
                name="Arcane Blast",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.MAGIC,
                effects={"damage": SkillEffect(value=40)},
                energie_cost=30,
                energie_target=Mana,
                cooldown=5,
                description="Explosion arcanique puissante"
            ),
        },
    }
}

mob_table: ClassTable = {
    "base_stats": {
        "hp": 15,
        "force": 5,
        "endurance": 3,
        "intelligence": 3,
        "sagesse": 2,
        "energie": {
            1: {
                "type": Mana,
                "value": 10,
                "regen_rate": 0.2
            }
        }
    },
    "upgrade_stats": {
        1: {
            HP: 2,
            Force: 1,
            Endurance: 1,
            "Energie": {Mana: 1}
        },
        5: {
            HP: 1,
            Force: 1,
            "Energie": {Mana: 1}
        },
        10: {
            Force: 1,
            Endurance: 1,
            "Energie": {Mana: 1}
        }
    },
    "class_type": ClassType.DAMAGE,
    "class_skills_dict": {
        "level 1": {
            "Attack": Skill(
                name="Attack",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=5)},
                energie_cost=2,
                energie_target=Mana,
                description="Attaque basique"
            ),
        },
        "level 5": {
            "Pack de sang": Skill(
                name="Pack de sang",
                skill_type=SkillType.HEAL,
                effects={"heal": SkillEffect(value=20, stat_target=HP)},
                energie_cost=5,
                energie_target=Mana,
                cooldown=2,
                description="Régénère de la santé"
            ),
        },
        "level 10": {
            "Bite": Skill(
                name="Bite",
                skill_type=SkillType.DAMAGE,
                damage_type=DamageType.PHYSICAL,
                effects={"damage": SkillEffect(value=40)},
                energie_cost=10,
                energie_target=Mana,
                cooldown=3,
                description="Morsure féroce"
            ),
        }
    }
}

