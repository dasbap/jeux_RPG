from copy import deepcopy

from _class.res.advantage import Advantage

from _class.res.character.alteration.alteration import AlterationType
from _class.res.character.stats.basic_stat import HP, Aura, Endurance, Foie, Force, Intelligence, Mana, Sagesse

from _class.res.classType import ClassType, DamageType, SkillType
from _class.res.dictType import ClassTable

from _class.skills.skill import Skill
from _class.skills.skillEffect import SkillEffect

from _function.skill.custom import multy_action_skill


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
                Foie : 1
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
                effects={"damage": SkillEffect(value=9)},
                energie_cost=8,
                energie_target= Aura,
                cooldown=2,
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
        "hp":10,
        "force":2,
        "endurance": 1,
        "intelligence":16,
        "sagesse": 3,
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
            Intelligence:4,
            Sagesse: 1,
            "Energie": {
                Mana : 4
            },
        },
        15:{
            HP:1,
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
