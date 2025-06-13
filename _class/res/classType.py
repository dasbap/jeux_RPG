from enum import Enum

class ClassType(Enum):
    DEFAULT = 0
    DAMAGE = 1
    DOT = 2
    HEAL = 3
    BUFF = 4
    SHIELD = 5
    INVOCATION = 6
    SUMMONER = 7

class DamageType(Enum):
    PHYSICAL = 0
    MAGIC = 1
    SACRED = 2

class SkillType(Enum):
    DAMAGE = 0
    HEAL = 1
    BUFF = 2
    DEBUFF = 3
    RESURRECT = 4
    INVOCATION = 5
    CUSTOM = 6

class ReductionType(Enum):
    MULTIPLY = 0
    ADD = 1
    SUBSTRACT = 2