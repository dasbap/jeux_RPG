"""Unit tests for Factory and GameController."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from jeuxRPG._core.factory.factory import Factory
from jeuxRPG._core.factory.Character_factory import Character_factory
from jeuxRPG._core.object_creation import ObjectCreation
from jeuxRPG._core.game_controller import GameController
from jeuxRPG._class.character import Character
import tempfile
import json
import os


class TestFactory:
    """Tests for Factory class."""

    def test_factory_initialization(self):
        """Test factory initializes empty."""
        factory = Factory()
        assert factory.factorys == []
        assert factory.last_create is None

    def test_factory_add(self):
        """Test adding factory to Factory."""
        factory = Factory()
        char_factory = Character_factory()
        factory.add(char_factory)
        assert char_factory in factory.factorys

    def test_factory_add_duplicate_class_ignored(self):
        """Test adding same factory class twice is ignored."""
        factory = Factory()
        char_factory1 = Character_factory()
        char_factory2 = Character_factory()
        factory.add(char_factory1)
        factory.add(char_factory2)
        # Should only have one
        assert len(factory.factorys) == 1

    def test_factory_get(self):
        """Test get retrieves factory by type."""
        factory = Factory()
        char_factory = Character_factory()
        factory.add(char_factory)
        retrieved = factory.get(Character_factory)
        assert retrieved == char_factory

    def test_factory_get_by_name(self):
        """Test get_by_name retrieves factory by class name."""
        factory = Factory()
        char_factory = Character_factory()
        factory.add(char_factory)
        retrieved = factory.get_by_name("Character_factory")
        assert retrieved == char_factory

    def test_factory_get_by_name_not_found(self):
        """Test get_by_name returns None if not found."""
        factory = Factory()
        result = factory.get_by_name("NonExistent")
        assert result is None


class TestCharacterFactory:
    """Tests for Character_factory."""

    def test_character_factory_creation(self):
        """Test Character_factory initializes."""
        char_factory = Character_factory()
        assert isinstance(char_factory, ObjectCreation)
        assert char_factory.object_target is None

    def test_character_factory_set_object_target(self):
        """Test setting object target updates attribute_required."""
        char_factory = Character_factory()
        # Use Knight as the target class
        knight_instance = Character.create("Knight", "test_id", "TestKnight")
        char_factory.set_object_target(knight_instance.__class__)
        assert char_factory.object_target == knight_instance.__class__
        assert char_factory.attribute_required["class_name"] == knight_instance.__class__.__name__

    def test_character_factory_invalid_attribute_keys(self):
        """Test set_attribute_required validates keys."""
        char_factory = Character_factory()
        with pytest.raises(ValueError, match="Keys must be exactly"):
            char_factory.set_attribute_required(invalid_key="value")

    def test_character_factory_invalid_attribute_values(self):
        """Test set_attribute_required validates values are strings."""
        char_factory = Character_factory()
        with pytest.raises(TypeError, match="All values must be strings"):
            char_factory.set_attribute_required(id=123, name="Test", class_name="Knight")


class TestGameController:
    """Tests for GameController."""

    def test_game_controller_initialization(self):
        """Test GameController initializes correctly."""
        controller = GameController()
        assert controller.save_path == ""
        assert controller.memory["creation"] == []
        assert controller.memory["last creation"] is None

    def test_game_controller_set_save_path(self):
        """Test set_save_path updates path."""
        controller = GameController()
        path = "/test/path"
        result = controller.set_save_path(path)
        assert result is True
        assert controller.save_path == path

    def test_game_controller_create_save(self):
        """Test create_save creates JSON file."""
        controller = GameController()
        with tempfile.TemporaryDirectory() as tmpdir:
            controller.set_save_path(tmpdir)
            result = controller.create_save(1, name="TestChar", level=5)
            assert result is True
            
            # Verify file was created
            filepath = os.path.join(tmpdir, "id_1.json")
            assert os.path.isfile(filepath)
            
            # Verify contents
            with open(filepath, "r") as f:
                data = json.load(f)
            assert data["id"] == 1
            assert data["data"]["name"] == "TestChar"

    def test_game_controller_load_save(self):
        """Test load_save retrieves saved data."""
        controller = GameController()
        with tempfile.TemporaryDirectory() as tmpdir:
            controller.set_save_path(tmpdir)
            controller.create_save(1, name="TestChar", level=5)
            
            loaded = controller.load_save(1)
            assert loaded is not None
            assert loaded["id"] == 1
            assert loaded["data"]["name"] == "TestChar"

    def test_game_controller_load_save_not_found(self):
        """Test load_save returns None if file doesn't exist."""
        controller = GameController()
        with tempfile.TemporaryDirectory() as tmpdir:
            controller.set_save_path(tmpdir)
            loaded = controller.load_save(999)
            assert loaded is None

    def test_game_controller_del_save(self):
        """Test del_save removes file."""
        controller = GameController()
        with tempfile.TemporaryDirectory() as tmpdir:
            controller.set_save_path(tmpdir)
            controller.create_save(1, name="TestChar")
            
            result = controller.del_save(1)
            assert result is True
            
            # Verify file is gone
            filepath = os.path.join(tmpdir, "id_1.json")
            assert not os.path.isfile(filepath)

    def test_game_controller_create_save_no_path(self):
        """Test create_save returns False if no path set."""
        controller = GameController()
        result = controller.create_save(1, name="Test")
        assert result is False

    def test_game_controller_load_save_no_path(self):
        """Test load_save returns None if no path set."""
        controller = GameController()
        result = controller.load_save(1)
        assert result is None

    def test_game_controller_add_factory(self):
        """Test add_factory registers factory."""
        controller = GameController()
        # Factory already has one Character_factory from __init_factory
        # Verify it can be retrieved
        retrieved = controller.factory.get(Character_factory)
        assert retrieved is not None
        assert isinstance(retrieved, Character_factory)

    def test_game_controller_memory_tracking(self):
        """Test memory tracks creations."""
        controller = GameController()
        with tempfile.TemporaryDirectory() as tmpdir:
            controller.set_save_path(tmpdir)
            controller.create_save(1, name="First")
            controller.create_save(2, name="Second")
            
            assert len(controller.memory["creation"]) == 2
            assert controller.memory["last creation"]["id"] == 2

    def test_game_controller_factory_create_with_string(self):
        """Test factory_create with string type name."""
        controller = GameController()
        controller.factory_create("Character_factory", id="user1", name="TestChar", class_name="Knight")
        assert controller.memory["last creation"] is not None
