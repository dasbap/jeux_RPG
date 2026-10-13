from typing import TypedDict

from jeuxRPG._class.res.advantage import Advantage
from jeuxRPG._class.res.character.stats import basic_stat as stat_module
from jeuxRPG._class.res.classType import ClassType
from jeuxRPG._class.skills.skill import Skill


class BaseStats(TypedDict):
    hp: int
    force: int
    endurance: int
    intelligence: int
    sagesse: int
    energie: dict[int, dict[str, type[stat_module.Energie] | int | float]]


# Typage des améliorations par niveau
class EnergieUpgrade(TypedDict):
    type: type[stat_module.Energie]
    value: int
    regen_rate: float


class StatUpgrade(TypedDict):
    HP: int
    Force: int
    Endurance: int
    Intelligence: int
    Sagesse: int
    Energie: dict[type[stat_module.Energie], int]
    new: dict[str, dict[type[stat_module.Energie], int]]


UpgradeStats = dict[int, StatUpgrade]


# Typage des compétences par niveau
SkillLevel = dict[str, Skill]
ClassSkills = dict[str, SkillLevel]


# Structure finale du Knight
class ClassTable(TypedDict):
    base_stats: BaseStats
    upgrade_stats: UpgradeStats
    advantage: Advantage
    class_type: ClassType
    class_skills_dict: ClassSkills
