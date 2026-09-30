"""
SaveManager - Central save system with categorized storage.

Handles persistence for different entity types in separate directories,
enabling future expansion (NPCs, mobs, world data, etc.).
"""

from __future__ import annotations
import json
import os
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from dataclasses import asdict

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SaveCategory(Enum):
    """Categories for different save types - each gets its own subdirectory."""
    PLAYERS = "players"       # Player characters (Discord users)
    NPCS = "npcs"             # Non-player characters
    MOBS = "mobs"             # Spawned monsters/creatures
    WORLD = "world"           # World/map data (towns, regions)
    SESSIONS = "sessions"     # Active game sessions/battles
    TEAMS = "teams"           # Team/alliance data
    QUESTS = "quests"         # Quest progress (future)
    INVENTORY = "inventory"   # Inventories (future)


class SaveManager:
    """
    Centralized save manager with category-based storage.
    
    Usage:
        manager = SaveManager(".data/saves")
        
        # Save a player
        manager.save(SaveCategory.PLAYERS, user_id, player_data)
        
        # Load a player
        data = manager.load(SaveCategory.PLAYERS, user_id)
        
        # List all NPCs
        npc_ids = manager.list_ids(SaveCategory.NPCS)
    """
    
    _instance: Optional["SaveManager"] = None
    
    def __init__(self, base_path: Union[str, Path] = ".data/saves"):
        self._base_path = Path(base_path)
        self._ensure_directories()
    
    @classmethod
    def get_instance(cls, base_path: Union[str, Path] = ".data/saves") -> "SaveManager":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls(base_path)
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (useful for tests)."""
        cls._instance = None
    
    @property
    def base_path(self) -> Path:
        return self._base_path
    
    def set_base_path(self, path: Union[str, Path]) -> None:
        """Change base path and recreate directories."""
        self._base_path = Path(path)
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Create all category subdirectories."""
        self._base_path.mkdir(parents=True, exist_ok=True)
        for category in SaveCategory:
            (self._base_path / category.value).mkdir(exist_ok=True)

        # Migrate legacy flat player files into per-player folders if needed
        try:
            self._migrate_players_to_folders()
        except Exception:
            logger.exception("Failed during players migration")
    
    def _get_filepath(self, category: SaveCategory, entity_id: str) -> Path:
        """Get the file path for a specific entity."""
        safe_id = self._sanitize_id(entity_id)
        # For players, prefer a per-player folder with character.json
        if category == SaveCategory.PLAYERS:
            player_dir = self._base_path / category.value / safe_id
            char_file = player_dir / "character.json"
            if char_file.exists():
                return char_file
            # Fallback to legacy single-file layout
            return self._base_path / category.value / f"{safe_id}.json"

        return self._base_path / category.value / f"{safe_id}.json"

    def _get_save_filepath(self, category: SaveCategory, entity_id: str) -> Path:
        """Get the filepath to use when saving data.

        For players, ensure per-player folder and return character.json path.
        """
        safe_id = self._sanitize_id(entity_id)
        if category == SaveCategory.PLAYERS:
            player_dir = self._base_path / category.value / safe_id
            player_dir.mkdir(parents=True, exist_ok=True)
            return player_dir / "character.json"
        return self._base_path / category.value / f"{safe_id}.json"
    
    @staticmethod
    def _sanitize_id(entity_id: str) -> str:
        """Sanitize ID for use as filename (remove problematic chars)."""
        # Replace problematic filesystem characters
        return str(entity_id).replace("/", "_").replace("\\", "_").replace(":", "_")
    
    def save(
        self,
        category: SaveCategory,
        entity_id: str,
        data: Dict[str, Any],
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Save entity data to the appropriate category directory.
        
        Args:
            category: The save category (PLAYERS, NPCS, etc.)
            entity_id: Unique identifier for the entity
            data: The entity data to persist
            metadata: Optional metadata (timestamps, version, etc.)
        
        Returns:
            True if save succeeded, False otherwise
        """
        # Use the save-specific filepath which ensures directories are created
        filepath = self._get_save_filepath(category, entity_id)
        
        payload = {
            "id": entity_id,
            "category": category.value,
            "data": data,
        }
        if metadata:
            payload["metadata"] = metadata
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
            logger.debug(f"Saved {category.value}/{entity_id}")
            return True
        except Exception as e:
            logger.exception(f"Failed to save {category.value}/{entity_id}: {e}")
            return False
    
    def load(
        self,
        category: SaveCategory,
        entity_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Load entity data from the appropriate category directory.
        
        Args:
            category: The save category
            entity_id: Unique identifier for the entity
        
        Returns:
            The saved data dict, or None if not found/error
        """
        filepath = self._get_filepath(category, entity_id)
        
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload.get("data")
        except Exception as e:
            logger.exception(f"Failed to load {category.value}/{entity_id}: {e}")
            return None
    
    def load_full(
        self,
        category: SaveCategory,
        entity_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Load full payload including metadata."""
        filepath = self._get_filepath(category, entity_id)
        
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.exception(f"Failed to load {category.value}/{entity_id}: {e}")
            return None
    
    def delete(self, category: SaveCategory, entity_id: str) -> bool:
        """Delete a saved entity."""
        filepath = self._get_filepath(category, entity_id)
        
        if not filepath.exists():
            return False
        
        try:
            filepath.unlink()
            logger.debug(f"Deleted {category.value}/{entity_id}")
            return True
        except Exception as e:
            logger.exception(f"Failed to delete {category.value}/{entity_id}: {e}")
            return False
    
    def exists(self, category: SaveCategory, entity_id: str) -> bool:
        """Check if a save file exists."""
        return self._get_filepath(category, entity_id).exists()
    
    def list_ids(self, category: SaveCategory) -> List[str]:
        """List all entity IDs in a category."""
        category_path = self._base_path / category.value
        if not category_path.exists():
            return []

        ids = set()
        # Include directories (for players) and legacy json files
        for entry in category_path.iterdir():
            if entry.is_dir():
                ids.add(entry.name)
            elif entry.is_file() and entry.suffix == ".json":
                ids.add(entry.stem)
        return sorted(list(ids))
    
    def load_all(self, category: SaveCategory) -> Dict[str, Dict[str, Any]]:
        """Load all entities in a category."""
        result = {}
        for entity_id in self.list_ids(category):
            data = self.load(category, entity_id)
            if data is not None:
                result[entity_id] = data
        return result

    def _migrate_players_to_folders(self) -> int:
        """Migrate legacy player JSON files in players/ to per-player folders.

        Legacy files are expected as players/{id}.json. This will move them to
        players/{id}/character.json keeping the same data payload.
        Returns number of migrated files.
        """
        migrated = 0
        players_path = self._base_path / SaveCategory.PLAYERS.value
        if not players_path.exists():
            return 0

        for file in list(players_path.glob("*.json")):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                # Determine entity id
                entity_id = payload.get("id") or file.stem
                data = payload.get("data", payload)

                # Write into folder structure
                player_dir = players_path / file.stem
                player_dir.mkdir(parents=True, exist_ok=True)
                char_file = player_dir / "character.json"
                with open(char_file, "w", encoding="utf-8") as cf:
                    json.dump({"id": entity_id, "category": SaveCategory.PLAYERS.value, "data": data}, cf, ensure_ascii=False, indent=2)

                # Remove legacy file
                try:
                    file.unlink()
                except Exception:
                    logger.warning(f"Could not remove legacy file {file}")

                migrated += 1
            except Exception as e:
                logger.warning(f"Failed migrating {file}: {e}")
        if migrated:
            logger.info(f"Migrated {migrated} player save files to per-player folders")
        return migrated
    
    def clear_category(self, category: SaveCategory) -> int:
        """Delete all saves in a category. Returns count of deleted files."""
        count = 0
        for entity_id in self.list_ids(category):
            if self.delete(category, entity_id):
                count += 1
        return count
    
    def migrate_legacy_save(
        self,
        legacy_path: Union[str, Path],
        category: SaveCategory,
        id_extractor: callable = None,
    ) -> int:
        """
        Migrate legacy save files to the new structure.
        
        Args:
            legacy_path: Path to legacy saves directory
            category: Target category for migrated saves
            id_extractor: Optional function to extract ID from legacy data
        
        Returns:
            Count of successfully migrated files
        """
        legacy_path = Path(legacy_path)
        if not legacy_path.exists():
            return 0
        
        count = 0
        for file in legacy_path.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    legacy_data = json.load(f)
                
                # Extract ID from legacy format or filename
                if id_extractor:
                    entity_id = id_extractor(legacy_data, file.stem)
                elif "id" in legacy_data:
                    entity_id = str(legacy_data["id"])
                else:
                    entity_id = file.stem
                
                # Extract data portion
                data = legacy_data.get("data", legacy_data)
                
                if self.save(category, entity_id, data, metadata={"migrated_from": str(file)}):
                    count += 1
                    
            except Exception as e:
                logger.warning(f"Failed to migrate {file}: {e}")
        
        return count
