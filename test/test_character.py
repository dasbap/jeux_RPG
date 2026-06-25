"""Unit tests for Character class and related functionality."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from jeuxRPG._class.character import Character, CharacterMeta
from jeuxRPG._class.sub_character.knight import Knight
from jeuxRPG._class.res.character.stats.basic_stat import HP, Force, Intelligence, Mana, Energie


class TestCharacterCreation:
    """Tests for Character creation and initialization."""

    def test_character_create_factory_method(self):
        """Test Character.create factory method with valid class name."""
        char = Character.create("Knight", "user123", "TestKnight")
        assert char is not None
        assert char.name == "TestKnight"
        assert char.user_id == "user123"
        assert char.level == 1
        assert char.exp == 0

    def test_character_create_invalid_class(self):
        """Test Character.create raises ValueError for unknown class."""
        with pytest.raises(ValueError, match="Unknown class"):
            Character.create("UnknownClass", "user123", "Test")

    def test_character_init_empty_user_id(self):
        """Test Character.__init__ raises ValueError for empty user_id."""
        with pytest.raises(ValueError, match="user_id must be a non-empty string"):
            Knight("", "TestKnight")

    def test_character_init_invalid_user_id_type(self):
        """Test Character.__init__ raises ValueError for non-string user_id."""
        with pytest.raises(ValueError, match="user_id must be a non-empty string"):
            Knight(123, "TestKnight")


class TestCharacterStats:
    """Tests for character stats and attributes."""

    def test_character_has_initial_stats(self):
        """Test character has all required stats after initialization."""
        char = Character.create("Knight", "user123", "TestKnight")
        assert char.hp is not None
        assert char.force is not None
        assert char.endurance is not None
        assert char.intelligence is not None
        assert char.sagesse is not None
        assert len(char.energie) > 0

    def test_get_stat_by_name(self):
        """Test get_stat returns correct stat by name."""
        char = Character.create("Knight", "user123", "TestKnight")
        hp_stat = char.get_stat("HP")
        assert isinstance(hp_stat, HP)
        assert hp_stat.current_value > 0

    def test_get_stat_invalid_name(self):
        """Test get_stat raises TypeError for unknown stat."""
        char = Character.create("Knight", "user123", "TestKnight")
        with pytest.raises(TypeError, match="not found in character stats"):
            char.get_stat("InvalidStat")


class TestCharacterLife:
    """Tests for character life and death mechanics."""

    def test_character_is_alive_initial(self):
        """Test character is alive on creation."""
        char = Character.create("Knight", "user123", "TestKnight")
        assert char.is_alive() is True

    def test_character_lose_hp(self):
        """Test character loses HP correctly."""
        char = Character.create("Knight", "user123", "TestKnight")
        attacker = Character.create("Knight", "attacker", "Attacker")
        initial_hp = char.hp.current_value
        char.lose_hp(attacker, 20)
        assert char.hp.current_value < initial_hp

    def test_character_gain_hp(self):
        """Test character gains HP correctly."""
        char = Character.create("Knight", "user123", "TestKnight")
        char.hp.current_value = 5
        char.gain_hp(10)
        assert char.hp.current_value == 15

    def test_character_gain_hp_does_not_exceed_max(self):
        """Test HP gain does not exceed max value."""
        char = Character.create("Knight", "user123", "TestKnight")
        initial_max = char.hp.value
        char.hp.current_value = initial_max - 5
        char.gain_hp(50)
        assert char.hp.current_value == char.hp.value


class TestCharacterExperience:
    """Tests for character experience and leveling."""

    def test_character_gain_exp(self):
        """Test character gains experience and levels up."""
        char = Character.create("Knight", "user123", "TestKnight")
        initial_level = char.level
        initial_exp = char.exp
        char.gain_exp(100)
        assert char.level > initial_level
        assert char.exp == 0

    def test_character_gain_exp_negative_raises(self):
        """Test gain_exp raises ValueError for negative amount."""
        char = Character.create("Knight", "user123", "TestKnight")
        with pytest.raises(ValueError, match="XP must be positive"):
            char.gain_exp(-50)

    def test_character_can_level_up(self):
        """Test can_level_up checks for sufficient XP."""
        char = Character.create("Knight", "user123", "TestKnight")
        assert char.can_level_up() is False
        char.exp = char._required_exp_for_next_level()
        assert char.can_level_up() is True


class TestCharacterEnergie:
    """Tests for character energy system."""

    def test_character_has_energie(self):
        """Test character has energy after initialization."""
        char = Character.create("Knight", "user123", "TestKnight")
        assert len(char.energie) > 0

    def test_get_energie_by_type(self):
        """Test get_energie returns correct energy by type."""
        char = Character.create("Knight", "user123", "TestKnight")
        energie = char.energie[0]
        energie_type = type(energie)
        retrieved = char.get_energie(energie_type)
        assert isinstance(retrieved, energie_type)

    def test_get_energie_invalid_type(self):
        """Test get_energie raises TypeError for unknown type."""
        char = Character.create("Knight", "user123", "TestKnight")
        with pytest.raises(TypeError, match="not in the energy's list"):
            # Try to get an energy type that doesn't exist
            class FakeEnergie(Energie):
                pass
            char.get_energie(FakeEnergie)

    def test_consume_energie(self):
        """Test character consumes energy."""
        char = Character.create("Knight", "user123", "TestKnight")
        energie = char.energie[0]
        initial = energie.current_value
        char.consume_energie(5, type(energie))
        assert energie.current_value == initial - 5

    def test_consume_energie_insufficient(self):
        """Test consume_energie raises ValueError if insufficient."""
        char = Character.create("Knight", "user123", "TestKnight")
        energie = char.energie[0]
        energie.current_value = 2
        with pytest.raises(ValueError, match="Not enough energy"):
            char.consume_energie(10, type(energie))


class TestCharacterString:
    """Tests for character string representation."""

    def test_character_str(self):
        """Test __str__ returns reasonable string."""
        char = Character.create("Knight", "user123", "TestKnight")
        str_repr = str(char)
        assert "TestKnight" in str_repr
        assert "lvl" in str_repr
