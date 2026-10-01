"""
Character mixins module.

This module provides mixins that implement specific responsibilities
for the Character class, following the Single Responsibility Principle.
"""

from .health_mixin import HealthMixin
from .energy_mixin import EnergyMixin
from .alteration_mixin import AlterationMixin
from .skill_mixin import SkillMixin
from .progression_mixin import ProgressionMixin
from .combat_mixin import CombatMixin
from .navigation_mixin import NavigationMixin

__all__ = [
    "HealthMixin",
    "EnergyMixin", 
    "AlterationMixin",
    "SkillMixin",
    "ProgressionMixin",
    "CombatMixin",
    "NavigationMixin",
]
