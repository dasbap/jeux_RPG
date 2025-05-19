"""
Système de statistiques et attributs.
"""

from .stat import DefaultStat
from .basic_stat import (
    HP, Energie, Endurance, Force,
    Sagesse, Intelligence, Mana, Aura, Foie
)

__all__ = [
    'DefaultStat',
    'HP',
    'Energie',
    'Endurance',
    'Force',
    'Sagesse',
    'Intelligence',
    'Mana',
    'Aura',
    'Foie'
]