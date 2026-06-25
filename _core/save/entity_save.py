"""
Entity save data structures - Type-safe save/load for game entities.

Provides dataclasses for structured serialization of different entity types,
ensuring consistent save formats and easier evolution.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar
from enum import Enum

T = TypeVar("T", bound="EntitySaveData")


class EntityType(Enum):
    """Type of game entity for polymorphic loading."""
    PLAYER = "player"
    NPC = "npc"
    MOB = "mob"
    BOSS = "boss"
    INVOCATION = "invocation"


@dataclass
class EntitySaveData:
    """
    Base save data structure for all character-like entities.
    
    Subclasses add specific fields for players, NPCs, mobs, etc.
    """
    # Identity
    entity_id: str
    entity_type: str  # EntityType value
    name: str
    char_class: str
    
    # Core stats
    level: int = 1
    exp: int = 0
    hp_current: int = 0
    hp_max: int = 0
    
    # Stats snapshot
    stats: Dict[str, int] = field(default_factory=dict)
    
    # Energies: list of {type, current, max, regen_rate}
    energies: List[Dict[str, Any]] = field(default_factory=list)
    
    # Skills: list of skill names or full skill data
    skills: List[str] = field(default_factory=list)
    
    # Active alterations
    alterations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    created_at: str = ""
    updated_at: str = ""
    version: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["updated_at"] = datetime.now().isoformat()
        if not data["created_at"]:
            data["created_at"] = data["updated_at"]
        return data
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Create instance from dictionary."""
        # Filter to only known fields
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
    
    @classmethod
    def from_character(cls: Type[T], character: Any, entity_type: EntityType = EntityType.PLAYER) -> T:
        """
        Create save data from a Character instance.
        
        Args:
            character: A Character (or subclass) instance
            entity_type: The type of entity being saved
        """
        # Extract stats
        stats = {}
        for stat_name in ["force", "endurance", "intelligence", "sagesse"]:
            stat = getattr(character, stat_name, None)
            if stat is not None:
                stats[stat_name] = getattr(stat, "current_value", int(stat))
        
        # Extract energies
        energies = []
        for energie in getattr(character, "energie", []):
            energies.append({
                "type": type(energie).__name__,
                "current": getattr(energie, "current_value", 0),
                "max": getattr(energie, "value", 0),
                "regen_rate": getattr(energie, "regen_rate", 0.0),
            })
        
        # Extract skill names
        skills = list(getattr(character, "skills", {}).keys())
        
        # Extract HP
        hp = getattr(character, "hp", None)
        hp_current = getattr(hp, "current_value", 0) if hp else 0
        hp_max = getattr(hp, "value", 0) if hp else 0
        
        return cls(
            entity_id=str(getattr(character, "user_id", "")),
            entity_type=entity_type.value,
            name=getattr(character, "name", ""),
            char_class=getattr(character, "char_class", type(character).__name__),
            level=getattr(character, "level", 1),
            exp=getattr(character, "exp", 0),
            hp_current=hp_current,
            hp_max=hp_max,
            stats=stats,
            energies=energies,
            skills=skills,
        )


@dataclass
class PlayerSaveData(EntitySaveData):
    """
    Save data specific to player characters.
    
    Extends base with Discord-specific and player progression fields.
    """
    # Discord integration
    discord_user_id: str = ""
    discord_username: str = ""
    
    # Team/alliance
    team_id: Optional[str] = None
    alliance_id: Optional[str] = None
    
    # Progression
    total_battles: int = 0
    wins: int = 0
    losses: int = 0
    
    # Inventory (future)
    inventory: List[Dict[str, Any]] = field(default_factory=list)
    gold: int = 0
    
    # Quest progress (future)
    active_quests: List[str] = field(default_factory=list)
    completed_quests: List[str] = field(default_factory=list)
    
    @classmethod
    def from_character(cls, character: Any, discord_user_id: str = "", discord_username: str = "") -> "PlayerSaveData":
        """Create player save from character with Discord info."""
        base = EntitySaveData.from_character(character, EntityType.PLAYER)
        return cls(
            **asdict(base),
            discord_user_id=discord_user_id or base.entity_id,
            discord_username=discord_username,
        )


@dataclass
class NpcSaveData(EntitySaveData):
    """
    Save data for NPCs (merchants, quest givers, etc.).
    """
    # NPC behavior
    npc_role: str = ""  # "merchant", "quest_giver", "trainer", etc.
    dialogue_state: str = "default"
    
    # Location
    location_town: str = ""
    location_district: str = ""
    location_building: str = ""
    
    # Merchant data (if applicable)
    shop_inventory: List[Dict[str, Any]] = field(default_factory=list)
    
    # Quest data (if applicable)
    offered_quests: List[str] = field(default_factory=list)
    
    # AI behavior
    is_hostile: bool = False
    respawn_enabled: bool = True
    respawn_time_seconds: int = 300
    
    @classmethod
    def from_character(cls, character: Any, npc_role: str = "") -> "NpcSaveData":
        """Create NPC save from character."""
        base = EntitySaveData.from_character(character, EntityType.NPC)
        return cls(
            **asdict(base),
            npc_role=npc_role,
        )


@dataclass
class MobSaveData(EntitySaveData):
    """
    Save data for mobs/monsters.
    """
    # Mob identity
    mob_type: str = ""  # "goblin", "orc", "dragon_whelp", etc.
    is_boss: bool = False
    
    # Spawn info
    spawn_location: str = ""
    spawn_group_id: Optional[str] = None
    
    # Combat behavior
    aggro_range: float = 10.0
    patrol_path: List[str] = field(default_factory=list)
    
    # Loot (future)
    loot_table_id: str = ""
    guaranteed_drops: List[str] = field(default_factory=list)
    
    # State
    is_spawned: bool = True
    last_killed_at: Optional[str] = None
    kill_count: int = 0  # Times this mob was killed (for respawning mobs)
    
    @classmethod
    def from_character(cls, character: Any, mob_type: str = "", is_boss: bool = False) -> "MobSaveData":
        """Create mob save from character."""
        entity_type = EntityType.BOSS if is_boss else EntityType.MOB
        base = EntitySaveData.from_character(character, entity_type)
        return cls(
            **asdict(base),
            mob_type=mob_type or base.char_class.lower(),
            is_boss=is_boss,
        )
