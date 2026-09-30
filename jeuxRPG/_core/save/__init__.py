"""
Save system module - Structured persistence for game entities.

Structure:
    saves/
    ├── players/       # Player characters (Discord users)
    ├── npcs/          # Non-player characters (merchants, quest givers, etc.)
    ├── mobs/          # Spawned creatures/monsters
    ├── world/         # World data (towns, regions, buildings)
    └── sessions/      # Active game sessions/battles
"""

from .save_manager import SaveManager, SaveCategory
from .entity_save import EntitySaveData, PlayerSaveData, NpcSaveData, MobSaveData

__all__ = [
    "SaveManager",
    "SaveCategory",
    "EntitySaveData",
    "PlayerSaveData",
    "NpcSaveData",
    "MobSaveData",
]
