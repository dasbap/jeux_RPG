
from typing import Dict, Type, TypedDict, Union

from _class.res.advantage import Advantage
from _class.res.character.stats import basic_stat as stat_module
from _class.res.classType import ClassType
from _class.skills.skill import Skill


class BaseStats(TypedDict):
    hp: int
    force: int
    endurance: int
    intelligence: int
    sagesse: int
    energie: Dict[int, Dict[str, Union[Type[stat_module.Energie], int, float]]]

# Typage des améliorations par niveau
class EnergieUpgrade(TypedDict):
    type: Type[stat_module.Energie]
    value: int
    regen_rate: float

class StatUpgrade(TypedDict):
    HP: int
    Force: int
    Endurance: int
    Intelligence: int
    Sagesse: int
    Energie: Dict[Type[stat_module.Energie], int]
    new: Dict[str, Dict[Type[stat_module.Energie], int]]

UpgradeStats = Dict[int, StatUpgrade]


# Typage des compétences par niveau
SkillLevel = Dict[str, Skill]
ClassSkills = Dict[str, SkillLevel]

# Structure finale du Knight
class ClassTable(TypedDict):
    base_stats: BaseStats
    upgrade_stats: UpgradeStats
    advantage: Advantage
    class_type: ClassType
    class_skills_dict: ClassSkills