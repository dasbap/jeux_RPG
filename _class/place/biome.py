"""
Biome system for the world map.

Defines different terrain types that can exist on the world map.
"""

from enum import Enum, auto
from typing import Dict, Any

from jeuxRPG.i18n import t


class Biome(Enum):
    """Types of terrain/biome on the world map."""
    PLAIN = "plain"
    FOREST = "forest"
    MOUNTAIN = "mountain"
    VOLCANO = "volcano"
    DESERT = "desert"
    SWAMP = "swamp"
    OCEAN = "ocean"
    SNOW = "snow"
    
    def get_symbol(self) -> str:
        """Get ASCII symbol for map display."""
        symbols = {
            Biome.PLAIN: ".",
            Biome.FOREST: "♣",
            Biome.MOUNTAIN: "▲",
            Biome.VOLCANO: "V",
            Biome.DESERT: "≈",
            Biome.SWAMP: "~",
            Biome.OCEAN: "░",
            Biome.SNOW: "*",
        }
        return symbols.get(self, "?")
    
    def get_emoji(self) -> str:
        """Get emoji for Discord display."""
        emojis = {
            Biome.PLAIN: "🌾",
            Biome.FOREST: "🌲",
            Biome.MOUNTAIN: "⛰️",
            Biome.VOLCANO: "🌋",
            Biome.DESERT: "🏜️",
            Biome.SWAMP: "🌿",
            Biome.OCEAN: "🌊",
            Biome.SNOW: "❄️",
        }
        return emojis.get(self, "❓")
    
    def get_name(self, lang: str = "en") -> str:
        """Get translated biome name."""
        key = f"biome.{self.value}"
        translated = t(key, lang)
        # If no translation, return capitalized value
        return translated if translated != key else self.value.capitalize()
    
    def is_passable(self) -> bool:
        """Check if this biome can be walked through."""
        return self != Biome.OCEAN
    
    def get_movement_cost(self) -> float:
        """Get movement cost multiplier for this biome."""
        costs = {
            Biome.PLAIN: 1.0,
            Biome.FOREST: 1.5,
            Biome.MOUNTAIN: 2.5,
            Biome.VOLCANO: 3.0,
            Biome.DESERT: 2.0,
            Biome.SWAMP: 2.0,
            Biome.OCEAN: float('inf'),
            Biome.SNOW: 1.8,
        }
        return costs.get(self, 1.0)


# Default biome distribution weights for procedural generation
BIOME_WEIGHTS: Dict[Biome, float] = {
    Biome.PLAIN: 0.35,
    Biome.FOREST: 0.25,
    Biome.MOUNTAIN: 0.15,
    Biome.DESERT: 0.10,
    Biome.SWAMP: 0.08,
    Biome.SNOW: 0.05,
    Biome.VOLCANO: 0.02,
}
