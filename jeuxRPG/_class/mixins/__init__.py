"""
Character mixins module.

This module provides mixins that implement specific responsibilities
for the Character class, following the Single Responsibility Principle.
"""

from .alteration_mixin import AlterationMixin
from .combat_mixin import CombatMixin
from .energy_mixin import EnergyMixin
from .health_mixin import HealthMixin
from .navigation_mixin import NavigationMixin
from .progression_mixin import ProgressionMixin
from .skill_mixin import SkillMixin

__all__ = [
    "HealthMixin",
    "EnergyMixin",
    "AlterationMixin",
    "SkillMixin",
    "ProgressionMixin",
    "CombatMixin",
    "NavigationMixin",
]
