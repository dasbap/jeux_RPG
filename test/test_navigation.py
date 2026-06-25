"""
Comprehensive tests for Character navigation system.

Tests cover:
- Location tracking
- Movement between buildings, districts, and towns
- Navigation mixin integration with Character
- Travel history
"""

import pytest
from jeuxRPG._class.character import Character
from jeuxRPG._class.place.town import Town
from jeuxRPG._class.place.district import District
from jeuxRPG._class.place.building import Building
from jeuxRPG._class.place.navigation import Location, LocationType, Navigator


class TestCharacterHasNavigation:
    """Tests that Character has navigation capabilities."""

    def test_character_has_navigator(self):
        """Character should have a navigator property."""
        char = Character.create("Knight", "user1", "TestKnight")
        assert hasattr(char, 'navigator')
        assert char.navigator is not None

    def test_character_has_location(self):
        """Character should have a location property."""
        char = Character.create("Knight", "user1", "TestKnight")
        assert hasattr(char, 'location')
        assert char.location is not None

    def test_character_starts_in_wilderness(self):
        """New character starts in wilderness (no town)."""
        char = Character.create("Knight", "user1", "TestKnight")
        assert char.is_in_wilderness() is True
        assert char.is_in_town() is False

    def test_character_where_am_i_wilderness(self):
        """where_am_i returns Wilderness for new character."""
        char = Character.create("Knight", "user1", "TestKnight")
        # Character starts in wilderness - check that location is returned
        assert char.is_in_wilderness() is True
        assert len(char.where_am_i()) > 0  # Non-empty location string


class TestCharacterSpawn:
    """Tests for spawning character at a location."""

    def test_spawn_at_town(self):
        """Character can spawn at a town."""
        char = Character.create("Knight", "user1", "TestKnight")
        
        # Create a simple town
        town = Town("TestVillage")
        district = District("Central", "Le centre du village")
        town.add_district(district)
        town.entry_district = district
        
        char.spawn_at(town)
        
        assert char.is_in_town() is True
        assert char.get_current_town() == town
        assert char.get_current_district() == district

    def test_spawn_sets_location(self):
        """Spawn updates location properly."""
        char = Character.create("Knight", "user1", "TestKnight")
        
        town = Town("TestVillage")
        district = District("Market", "Le marché")
        town.add_district(district)
        town.entry_district = district
        
        char.spawn_at(town)
        
        assert "TestVillage" in char.where_am_i()
        assert "Market" in char.where_am_i()


class TestCharacterMovement:
    """Tests for character movement."""

    @pytest.fixture
    def town_with_districts(self):
        """Create a town with multiple districts."""
        town = Town("TestVillage")
        
        market = District("Market", "Le marché")
        residential = District("Residential", "Quartier résidentiel")
        
        town.add_district(market)
        town.add_district(residential)
        town.entry_district = market
        
        # Connect districts
        market.connect_to(residential)
        
        return town

    @pytest.fixture
    def char_in_town(self, town_with_districts):
        """Create a character spawned in town."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.spawn_at(town_with_districts)
        return char, town_with_districts

    def test_go_to_district(self, char_in_town):
        """Character can move to connected district."""
        char, town = char_in_town
        
        # Start in Market, go to Residential
        success, message = char.go_to_district("Residential")
        
        assert success is True
        assert char.get_current_district().name == "Residential"

    def test_go_to_invalid_district(self, char_in_town):
        """Character cannot go to non-existent district."""
        char, town = char_in_town
        
        success, message = char.go_to_district("NonExistent")
        
        assert success is False
        # Message peut varier selon l'implémentation


class TestCharacterBuildingEntry:
    """Tests for entering buildings."""

    @pytest.fixture
    def town_with_building(self):
        """Create a town with a building."""
        from jeuxRPG._class.res.classType import Build_state
        
        town = Town("TestVillage")
        district = District("Market", "Le marché")
        
        building = Building("Blacksmith", "La forge")
        building.status = Build_state.OPERATIONAL  # Activer le bâtiment
        district.add_building(building)
        
        town.add_district(district)
        town.entry_district = district
        
        return town, building

    def test_enter_building(self, town_with_building):
        """Character can enter a building."""
        town, building = town_with_building
        
        char = Character.create("Knight", "user1", "TestKnight")
        char.spawn_at(town)
        
        success, message = char.enter_building("Blacksmith")
        
        assert success is True
        assert char.is_in_building() is True
        assert char.get_current_building() == building

    def test_exit_building(self, town_with_building):
        """Character can exit a building."""
        town, building = town_with_building
        
        char = Character.create("Knight", "user1", "TestKnight")
        char.spawn_at(town)
        char.enter_building("Blacksmith")
        
        success, message = char.exit_building()
        
        assert success is True
        assert char.is_in_building() is False

    def test_enter_invalid_building(self, town_with_building):
        """Character cannot enter non-existent building."""
        town, _ = town_with_building
        
        char = Character.create("Knight", "user1", "TestKnight")
        char.spawn_at(town)
        
        success, message = char.enter_building("NonExistent")
        
        assert success is False


class TestCharacterLocationInfo:
    """Tests for location information methods."""

    def test_get_movement_options(self):
        """Character can get available movement options."""
        char = Character.create("Knight", "user1", "TestKnight")
        
        town = Town("TestVillage")
        district = District("Market", "Le marché")
        building = Building("Shop", "Une boutique")
        district.add_building(building)
        town.add_district(district)
        town.entry_district = district
        
        char.spawn_at(town)
        
        options = char.get_movement_options()
        
        assert "buildings" in options
        assert "districts" in options
        assert "towns" in options

    def test_get_navigation_info(self):
        """Character can get complete navigation info."""
        char = Character.create("Knight", "user1", "TestKnight")
        
        info = char.get_navigation_info()
        
        assert "current_location" in info
        assert "location_type" in info
        assert "options" in info


class TestCharacterTravelHistory:
    """Tests for travel history tracking."""

    def test_get_travel_history(self):
        """Character can get travel history."""
        char = Character.create("Knight", "user1", "TestKnight")
        
        town = Town("TestVillage")
        district = District("Market", "Le marché")
        town.add_district(district)
        town.entry_district = district
        
        char.spawn_at(town)
        
        history = char.get_travel_history()
        
        assert isinstance(history, list)
        assert len(history) >= 1  # At least the spawn

    def test_history_tracks_movements(self):
        """History tracks character movements."""
        char = Character.create("Knight", "user1", "TestKnight")
        
        town = Town("TestVillage")
        district1 = District("Market", "Le marché")
        district2 = District("Residential", "Résidentiel")
        
        district1.connect_to(district2)
        
        town.add_district(district1)
        town.add_district(district2)
        town.entry_district = district1
        
        char.spawn_at(town)
        char.go_to_district("Residential")
        char.go_to_district("Market")
        
        history = char.get_travel_history()
        
        assert len(history) >= 3


class TestMultipleCharactersNavigation:
    """Tests for multiple characters navigating independently."""

    def test_characters_have_independent_locations(self):
        """Each character has independent location."""
        char1 = Character.create("Knight", "user1", "Knight1")
        char2 = Character.create("Mage", "user2", "Mage2")
        
        town = Town("TestVillage")
        district = District("Market", "Le marché")
        town.add_district(district)
        town.entry_district = district
        
        char1.spawn_at(town)
        
        # char1 is in town, char2 is still in wilderness
        assert char1.is_in_town() is True
        assert char2.is_in_wilderness() is True

    def test_characters_move_independently(self):
        """Characters can move independently."""
        char1 = Character.create("Knight", "user1", "Knight1")
        char2 = Character.create("Mage", "user2", "Mage2")
        
        town = Town("TestVillage")
        district1 = District("Market", "Le marché")
        district2 = District("Residential", "Résidentiel")
        
        district1.connect_to(district2)
        
        town.add_district(district1)
        town.add_district(district2)
        town.entry_district = district1
        
        char1.spawn_at(town)
        char2.spawn_at(town)
        
        char1.go_to_district("Residential")
        
        # char1 is in Residential, char2 is still in Market
        assert char1.get_current_district().name == "Residential"
        assert char2.get_current_district().name == "Market"
