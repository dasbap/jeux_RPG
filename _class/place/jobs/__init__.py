"""
Module jobs - Métiers et PNJ.

Classes:
- Job: Représente un métier (pour joueurs et PNJ)
- NPC: Personnage non-joueur

Enums:
- JobType: Types de métiers (BLACKSMITH, MERCHANT, etc.)
- ServiceType: Types de services (BUY, SELL, CRAFT, etc.)

Factory:
- create_blacksmith, create_innkeeper, create_merchant, etc.
"""

from jeuxRPG._class.place.jobs.job_types import JobType, ServiceType
from jeuxRPG._class.place.jobs.job import Job
from jeuxRPG._class.place.jobs.npc import (
    NPC,
    create_blacksmith,
    create_innkeeper,
    create_merchant,
    create_priest,
    create_mayor,
    create_guard
)

__all__ = [
    "JobType",
    "ServiceType",
    "Job",
    "NPC",
    "create_blacksmith",
    "create_innkeeper",
    "create_merchant",
    "create_priest",
    "create_mayor",
    "create_guard",
]
