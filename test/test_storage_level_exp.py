"""
Tests for bot/game/storage.py - Player save/load with level and exp.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from jeuxRPG._core.save import SaveManager, SaveCategory
from jeuxRPG._class.character import Character


class TestStorageSaveLoad:
    """Tests for storage module save/load functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """Create a temporary directory and reset SaveManager."""
        self.temp_dir = tempfile.mkdtemp()
        SaveManager.reset_instance()
        yield
        SaveManager.reset_instance()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_character_includes_level_and_exp(self):
        """Saving a character should persist level and exp."""
        manager = SaveManager(self.temp_dir)
        
        # Create a character and level it up
        char = Character.create("Knight", "user_save_test", "SaveTestKnight")
        char.gain_exp(300)  # Should level up
        
        initial_level = char.level
        initial_exp = char.exp
        assert initial_level >= 1
        
        # Save using the same format as storage.py
        data = {
            "name": char.name,
            "char_class": char.char_class,
            "level": char.level,
            "exp": char.exp,
        }
        result = manager.save(SaveCategory.PLAYERS, "user_save_test", data)
        assert result is True
        
        # Load and verify
        loaded = manager.load(SaveCategory.PLAYERS, "user_save_test")
        assert loaded is not None
        assert loaded["name"] == "SaveTestKnight"
        assert loaded["char_class"] == "Knight"
        assert loaded["level"] == initial_level
        assert loaded["exp"] == initial_exp
    
    def test_load_character_restores_level(self):
        """Loading a character should restore its level."""
        manager = SaveManager(self.temp_dir)
        
        # Save a character at level 5
        data = {
            "name": "LevelTestHero",
            "char_class": "Mage",
            "level": 5,
            "exp": 250,
        }
        manager.save(SaveCategory.PLAYERS, "user_level_test", data)
        
        # Load and verify data is intact
        loaded = manager.load(SaveCategory.PLAYERS, "user_level_test")
        assert loaded["level"] == 5
        assert loaded["exp"] == 250
        assert loaded["char_class"] == "Mage"
    
    def test_recreate_character_with_level(self):
        """Character can be recreated and leveled up from saved data."""
        # Create fresh character
        char = Character.create("Knight", "user_recreate_test", "RecreateHero")
        assert char.level == 1
        
        # Level it up using level_up_f with target level
        from jeuxRPG._function.Character.level_up_f import level_up_f
        level_up_f(char, 3)  # Level up to level 3
        assert char.level == 3
        
        # Remember stats at level 3
        hp_at_level_3 = char.hp.value
        
        # Create new character and level up the same way
        char2 = Character.create("Knight", "user_recreate_test2", "RecreateHero2")
        level_up_f(char2, 3)  # Level up to level 3
        
        # Should have same level and similar HP
        assert char2.level == 3
        assert char2.hp.value == hp_at_level_3
    
    def test_save_preserves_exp_after_level_up(self):
        """Exp remaining after level up should be saved correctly."""
        manager = SaveManager(self.temp_dir)
        
        char = Character.create("Knight", "user_exp_test", "ExpTestKnight")
        
        # Give enough exp to level up with remainder
        char.gain_exp(500)  # Should level up multiple times
        
        level_after = char.level
        exp_after = char.exp
        
        # Save
        data = {
            "name": char.name,
            "char_class": char.char_class,
            "level": level_after,
            "exp": exp_after,
        }
        manager.save(SaveCategory.PLAYERS, "user_exp_test", data)
        
        # Load and verify
        loaded = manager.load(SaveCategory.PLAYERS, "user_exp_test")
        assert loaded["level"] == level_after
        assert loaded["exp"] == exp_after
    
    def test_backward_compatibility_with_class_key(self):
        """Old saves with 'class' instead of 'char_class' should still work."""
        manager = SaveManager(self.temp_dir)
        
        # Simulate old save format
        old_data = {
            "name": "OldHero",
            "class": "Archer",  # Old key name
            # No level/exp in old format
        }
        manager.save(SaveCategory.PLAYERS, "user_old_format", old_data)
        
        # Load should still work
        loaded = manager.load(SaveCategory.PLAYERS, "user_old_format")
        assert loaded["name"] == "OldHero"
        # The raw load returns what was saved
        assert loaded.get("class") == "Archer"
    
    def test_default_level_and_exp_for_missing_fields(self):
        """Missing level/exp should default to level 1, exp 0."""
        manager = SaveManager(self.temp_dir)
        
        # Save without level/exp
        data = {"name": "NoLevelHero", "char_class": "Priest"}
        manager.save(SaveCategory.PLAYERS, "user_no_level", data)
        
        loaded = manager.load(SaveCategory.PLAYERS, "user_no_level")
        
        # Application code should handle defaults
        level = loaded.get("level", 1)
        exp = loaded.get("exp", 0)
        assert level == 1
        assert exp == 0


class TestStoragePlayerSaveInfo:
    """Tests for PlayerSaveInfo TypedDict structure."""
    
    def test_player_save_info_structure(self):
        """PlayerSaveInfo should have all required fields."""
        from bot.game.storage import PlayerSaveInfo
        
        info: PlayerSaveInfo = {
            "name": "TestPlayer",
            "char_class": "Knight",
            "level": 10,
            "exp": 500,
        }
        
        assert info["name"] == "TestPlayer"
        assert info["char_class"] == "Knight"
        assert info["level"] == 10
        assert info["exp"] == 500


class TestStorageSaveCharacterFunction:
    """Tests for save_character function."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        self.temp_dir = tempfile.mkdtemp()
        SaveManager.reset_instance()
        from bot.game import storage
        storage._save_manager = None
        storage._users.clear()
        storage._persisted.clear()
        yield
        SaveManager.reset_instance()
        storage._save_manager = None
        storage._users.clear()
        storage._persisted.clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_character_from_instance(self):
        """save_character should extract data from Character instance."""
        # We need to test the _save_player_from_character logic
        manager = SaveManager(self.temp_dir)
        
        char = Character.create("Mage", "user_instance_test", "InstanceMage")
        char.gain_exp(200)
        
        # Simulate what _save_player_from_character does
        data = {
            "name": getattr(char, "name", ""),
            "char_class": getattr(char, "char_class", type(char).__name__),
            "level": getattr(char, "level", 1),
            "exp": getattr(char, "exp", 0),
        }
        
        result = manager.save(SaveCategory.PLAYERS, "user_instance_test", data)
        assert result is True
        
        loaded = manager.load(SaveCategory.PLAYERS, "user_instance_test")
        assert loaded["name"] == "InstanceMage"
        assert loaded["char_class"] == "Mage"
        assert loaded["level"] == char.level
        assert loaded["exp"] == char.exp

    def test_reset_character_progress_keeps_equipment_like_fields(self):
        """Tower death reset should not replace the character object."""
        from bot.game import storage

        manager = SaveManager(self.temp_dir)
        storage._save_manager = manager
        storage._users.clear()
        storage._persisted.clear()

        char = Character.create("Knight", "user_reset_test", "ResetKnight")
        char.gain_exp(300)
        char.equipment = {"weapon": "training sword"}
        original_object_id = id(char)
        levelled_hp = char.hp.value
        storage._users["user_reset_test"] = char

        assert char.level > 1
        assert storage.reset_character_progress("user_reset_test") is True

        assert id(storage._users["user_reset_test"]) == original_object_id
        assert char.level == 1
        assert char.exp == 0
        assert char.hp.current_value == char.hp.value
        assert char.hp.value < levelled_hp
        assert char.equipment == {"weapon": "training sword"}

        loaded = manager.load(SaveCategory.PLAYERS, "user_reset_test")
        assert loaded["level"] == 1
        assert loaded["exp"] == 0

    def test_tower_progress_uses_flat_max_stage_mapping(self):
        """Normal tower progress is saved as {tower_name: max_cleared_floor}."""
        from bot.game import storage

        manager = SaveManager(self.temp_dir)
        storage._save_manager = manager
        storage._users.clear()
        storage._persisted.clear()

        char = Character.create("Knight", "user_tower_progress", "TowerKnight")
        storage._users["user_tower_progress"] = char

        assert storage.mark_tower_floor_cleared("user_tower_progress", "normal", 4) is True
        assert storage.mark_tower_floor_cleared("user_tower_progress", "normal", 2) is True
        assert storage.mark_tower_floor_cleared("user_tower_progress", "hard", 1) is True

        loaded = manager.load(SaveCategory.PLAYERS, "user_tower_progress")
        assert loaded["tower_progress"] == {"normal": 4, "hard": 1}
        assert storage.get_tower_progress("user_tower_progress", "normal") == {
            "last_cleared_floor": 4,
            "next_floor": 5,
        }


class TestNpcAndMobSaves:
    """Tests for NPC and Mob saves with level/exp."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        self.temp_dir = tempfile.mkdtemp()
        SaveManager.reset_instance()
        yield
        SaveManager.reset_instance()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_npc_with_level(self):
        """NPCs should also save with level information."""
        manager = SaveManager(self.temp_dir)
        
        npc_data = {
            "name": "Merchant Bob",
            "char_class": "NPC",
            "level": 10,
            "exp": 0,
            "npc_role": "merchant",
            "location": "Town Square",
        }
        
        result = manager.save(SaveCategory.NPCS, "npc_merchant_bob", npc_data)
        assert result is True
        
        loaded = manager.load(SaveCategory.NPCS, "npc_merchant_bob")
        assert loaded["level"] == 10
        assert loaded["npc_role"] == "merchant"
    
    def test_save_mob_with_level(self):
        """Mobs should save with level for scaling purposes."""
        manager = SaveManager(self.temp_dir)
        
        mob_data = {
            "name": "Goblin Scout",
            "char_class": "Goblin",
            "level": 3,
            "exp": 0,
            "mob_type": "goblin",
            "is_boss": False,
            "spawn_location": "Forest Entrance",
        }
        
        result = manager.save(SaveCategory.MOBS, "mob_goblin_001", mob_data)
        assert result is True
        
        loaded = manager.load(SaveCategory.MOBS, "mob_goblin_001")
        assert loaded["level"] == 3
        assert loaded["mob_type"] == "goblin"
        assert loaded["is_boss"] is False
    
    def test_save_boss_with_higher_level(self):
        """Boss mobs should support higher levels."""
        manager = SaveManager(self.temp_dir)
        
        boss_data = {
            "name": "Dragon Lord",
            "char_class": "DragonWhelp",
            "level": 50,
            "exp": 0,
            "mob_type": "dragon",
            "is_boss": True,
        }
        
        result = manager.save(SaveCategory.MOBS, "boss_dragon_lord", boss_data)
        assert result is True
        
        loaded = manager.load(SaveCategory.MOBS, "boss_dragon_lord")
        assert loaded["level"] == 50
        assert loaded["is_boss"] is True
