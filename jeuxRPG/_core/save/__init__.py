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

from .entity_save import EntitySaveData, MobSaveData, NpcSaveData, PlayerSaveData
from .save_manager import SaveCategory, SaveManager

__all__ = [
    "SaveManager",
    "SaveCategory",
    "EntitySaveData",
    "PlayerSaveData",
    "NpcSaveData",
    "MobSaveData",
]
