"""
Tests for the save system (SaveManager, EntitySaveData, etc.)
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from jeuxRPG._core.save import (
    SaveManager,
    SaveCategory,
    EntitySaveData,
    PlayerSaveData,
    NpcSaveData,
    MobSaveData,
)
from jeuxRPG._core.save.entity_save import EntityType


class TestSaveManager:
    """Tests for SaveManager functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SaveManager(self.temp_dir)
        SaveManager.reset_instance()  # Ensure clean state
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_creates_category_directories(self):
        """SaveManager should create subdirectories for each category."""
        for category in SaveCategory:
            category_path = Path(self.temp_dir) / category.value
            assert category_path.exists(), f"Missing directory for {category.value}"
            assert category_path.is_dir()
    
    def test_save_and_load_player(self):
        """Should save and load player data correctly."""
        player_data = {
            "name": "TestPlayer",
            "class": "Knight",
            "level": 5,
            "hp": 100,
        }
        
        # Save
        result = self.manager.save(SaveCategory.PLAYERS, "user_123", player_data)
        assert result is True
        
        # Load
        loaded = self.manager.load(SaveCategory.PLAYERS, "user_123")
        assert loaded is not None
        assert loaded["name"] == "TestPlayer"
        assert loaded["class"] == "Knight"
        assert loaded["level"] == 5
    
    def test_save_and_load_npc(self):
        """Should save and load NPC data correctly."""
        npc_data = {
            "name": "Merchant Bob",
            "role": "merchant",
            "location": "Town Square",
        }
        
        result = self.manager.save(SaveCategory.NPCS, "npc_merchant_01", npc_data)
        assert result is True
        
        loaded = self.manager.load(SaveCategory.NPCS, "npc_merchant_01")
        assert loaded is not None
        assert loaded["name"] == "Merchant Bob"
        assert loaded["role"] == "merchant"
    
    def test_save_and_load_mob(self):
        """Should save and load mob data correctly."""
        mob_data = {
            "name": "Goblin Scout",
            "type": "goblin",
            "level": 3,
            "is_boss": False,
        }
        
        result = self.manager.save(SaveCategory.MOBS, "mob_goblin_001", mob_data)
        assert result is True
        
        loaded = self.manager.load(SaveCategory.MOBS, "mob_goblin_001")
        assert loaded is not None
        assert loaded["type"] == "goblin"
    
    def test_load_nonexistent_returns_none(self):
        """Loading a non-existent entity should return None."""
        loaded = self.manager.load(SaveCategory.PLAYERS, "does_not_exist")
        assert loaded is None
    
    def test_delete_entity(self):
        """Should delete saved entities."""
        self.manager.save(SaveCategory.PLAYERS, "to_delete", {"name": "Delete Me"})
        assert self.manager.exists(SaveCategory.PLAYERS, "to_delete")
        
        result = self.manager.delete(SaveCategory.PLAYERS, "to_delete")
        assert result is True
        assert not self.manager.exists(SaveCategory.PLAYERS, "to_delete")
    
    def test_delete_nonexistent_returns_false(self):
        """Deleting non-existent entity should return False."""
        result = self.manager.delete(SaveCategory.PLAYERS, "never_existed")
        assert result is False
    
    def test_exists_check(self):
        """exists() should correctly report save file presence."""
        assert not self.manager.exists(SaveCategory.NPCS, "test_npc")
        
        self.manager.save(SaveCategory.NPCS, "test_npc", {"name": "Test"})
        assert self.manager.exists(SaveCategory.NPCS, "test_npc")
    
    def test_list_ids(self):
        """list_ids should return all entity IDs in a category."""
        # Save multiple entities
        self.manager.save(SaveCategory.PLAYERS, "player_1", {"name": "One"})
        self.manager.save(SaveCategory.PLAYERS, "player_2", {"name": "Two"})
        self.manager.save(SaveCategory.PLAYERS, "player_3", {"name": "Three"})
        
        ids = self.manager.list_ids(SaveCategory.PLAYERS)
        assert len(ids) == 3
        assert "player_1" in ids
        assert "player_2" in ids
        assert "player_3" in ids
    
    def test_load_all(self):
        """load_all should return all entities in a category."""
        self.manager.save(SaveCategory.NPCS, "npc_1", {"name": "NPC One"})
        self.manager.save(SaveCategory.NPCS, "npc_2", {"name": "NPC Two"})
        
        all_npcs = self.manager.load_all(SaveCategory.NPCS)
        assert len(all_npcs) == 2
        assert all_npcs["npc_1"]["name"] == "NPC One"
        assert all_npcs["npc_2"]["name"] == "NPC Two"
    
    def test_clear_category(self):
        """clear_category should delete all saves in a category."""
        self.manager.save(SaveCategory.MOBS, "mob_1", {"name": "Mob 1"})
        self.manager.save(SaveCategory.MOBS, "mob_2", {"name": "Mob 2"})
        assert len(self.manager.list_ids(SaveCategory.MOBS)) == 2
        
        count = self.manager.clear_category(SaveCategory.MOBS)
        assert count == 2
        assert len(self.manager.list_ids(SaveCategory.MOBS)) == 0
    
    def test_load_full_includes_metadata(self):
        """load_full should return complete payload with metadata."""
        self.manager.save(
            SaveCategory.PLAYERS,
            "player_meta",
            {"name": "Meta Player"},
            metadata={"source": "test", "version": 2},
        )
        
        full = self.manager.load_full(SaveCategory.PLAYERS, "player_meta")
        assert full is not None
        assert full["id"] == "player_meta"
        assert full["category"] == "players"
        assert full["data"]["name"] == "Meta Player"
        assert full["metadata"]["source"] == "test"
        assert full["metadata"]["version"] == 2
    
    def test_sanitize_id_with_special_chars(self):
        """IDs with special characters should be sanitized for filesystem."""
        # Discord user IDs are usually numeric, but test edge cases
        weird_id = "user/with\\bad:chars"
        self.manager.save(SaveCategory.PLAYERS, weird_id, {"name": "Weird"})
        
        # Should be able to load with the same ID
        loaded = self.manager.load(SaveCategory.PLAYERS, weird_id)
        assert loaded is not None
        assert loaded["name"] == "Weird"
    
    def test_singleton_pattern(self):
        """get_instance should return the same instance."""
        SaveManager.reset_instance()
        
        instance1 = SaveManager.get_instance(self.temp_dir)
        instance2 = SaveManager.get_instance(self.temp_dir)
        
        assert instance1 is instance2
        
        SaveManager.reset_instance()


class TestEntitySaveData:
    """Tests for EntitySaveData and subclasses."""
    
    def test_entity_save_data_to_dict(self):
        """EntitySaveData should convert to dict properly."""
        data = EntitySaveData(
            entity_id="123",
            entity_type=EntityType.PLAYER.value,
            name="Test Hero",
            char_class="Knight",
            level=10,
            exp=5000,
        )
        
        result = data.to_dict()
        assert result["entity_id"] == "123"
        assert result["entity_type"] == "player"
        assert result["name"] == "Test Hero"
        assert result["char_class"] == "Knight"
        assert result["level"] == 10
        assert result["updated_at"]  # Should be set
    
    def test_entity_save_data_from_dict(self):
        """EntitySaveData should be created from dict."""
        input_data = {
            "entity_id": "456",
            "entity_type": "npc",
            "name": "Bob the Merchant",
            "char_class": "NPC",
            "level": 1,
            "exp": 0,
            "stats": {"force": 5, "intelligence": 10},
        }
        
        entity = EntitySaveData.from_dict(input_data)
        assert entity.entity_id == "456"
        assert entity.name == "Bob the Merchant"
        assert entity.stats == {"force": 5, "intelligence": 10}
    
    def test_player_save_data_fields(self):
        """PlayerSaveData should have player-specific fields."""
        player = PlayerSaveData(
            entity_id="discord_user_123",
            entity_type=EntityType.PLAYER.value,
            name="Hero",
            char_class="Mage",
            discord_user_id="discord_user_123",
            discord_username="Hero#1234",
            wins=10,
            losses=2,
            gold=500,
        )
        
        result = player.to_dict()
        assert result["discord_user_id"] == "discord_user_123"
        assert result["discord_username"] == "Hero#1234"
        assert result["wins"] == 10
        assert result["gold"] == 500
    
    def test_npc_save_data_fields(self):
        """NpcSaveData should have NPC-specific fields."""
        npc = NpcSaveData(
            entity_id="npc_001",
            entity_type=EntityType.NPC.value,
            name="Shopkeeper",
            char_class="NPC",
            npc_role="merchant",
            location_town="Starting Village",
            shop_inventory=[{"item": "sword", "price": 100}],
        )
        
        result = npc.to_dict()
        assert result["npc_role"] == "merchant"
        assert result["location_town"] == "Starting Village"
        assert len(result["shop_inventory"]) == 1
    
    def test_mob_save_data_fields(self):
        """MobSaveData should have mob-specific fields."""
        mob = MobSaveData(
            entity_id="mob_goblin_001",
            entity_type=EntityType.MOB.value,
            name="Goblin Scout",
            char_class="Goblin",
            mob_type="goblin",
            is_boss=False,
            aggro_range=15.0,
            loot_table_id="loot_goblin_common",
        )
        
        result = mob.to_dict()
        assert result["mob_type"] == "goblin"
        assert result["is_boss"] is False
        assert result["aggro_range"] == 15.0
        assert result["loot_table_id"] == "loot_goblin_common"
    
    def test_boss_mob_save_data(self):
        """Boss mobs should have is_boss=True."""
        boss = MobSaveData(
            entity_id="boss_dragon_001",
            entity_type=EntityType.BOSS.value,
            name="Elder Dragon",
            char_class="DragonWhelp",
            mob_type="dragon",
            is_boss=True,
        )
        
        result = boss.to_dict()
        assert result["is_boss"] is True
        assert result["entity_type"] == "boss"


class TestCategoryIsolation:
    """Test that categories are properly isolated."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SaveManager(self.temp_dir)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_same_id_different_categories(self):
        """Same ID in different categories should be independent."""
        self.manager.save(SaveCategory.PLAYERS, "entity_001", {"type": "player"})
        self.manager.save(SaveCategory.NPCS, "entity_001", {"type": "npc"})
        self.manager.save(SaveCategory.MOBS, "entity_001", {"type": "mob"})
        
        player = self.manager.load(SaveCategory.PLAYERS, "entity_001")
        npc = self.manager.load(SaveCategory.NPCS, "entity_001")
        mob = self.manager.load(SaveCategory.MOBS, "entity_001")
        
        assert player["type"] == "player"
        assert npc["type"] == "npc"
        assert mob["type"] == "mob"
    
    def test_clear_category_isolates(self):
        """Clearing one category should not affect others."""
        self.manager.save(SaveCategory.PLAYERS, "p1", {"name": "Player"})
        self.manager.save(SaveCategory.NPCS, "n1", {"name": "NPC"})
        
        self.manager.clear_category(SaveCategory.PLAYERS)
        
        assert not self.manager.exists(SaveCategory.PLAYERS, "p1")
        assert self.manager.exists(SaveCategory.NPCS, "n1")
