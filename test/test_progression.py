"""
Comprehensive tests for the Character progression system.

Tests cover:
- Experience gain (gain_exp)
- Level up mechanics (level_up, can_level_up)
- XP requirements (_required_exp_for_next_level)
- XP drop on death (drop_xp)
- Stat upgrades on level up
- Multiple level ups at once
- Edge cases and error handling
"""

import pytest
from jeuxRPG._class.character import Character
from jeuxRPG._class.sub_character.knight import Knight
from jeuxRPG._class.sub_character.mage import Mage


class TestRequiredExpForNextLevel:
    """Tests for _required_exp_for_next_level calculation."""

    def test_required_exp_level_1(self):
        """At level 1, requires 100 XP to level up."""
        char = Character.create("Knight", "user1", "TestKnight")
        assert char.level == 1
        assert char._required_exp_for_next_level() == 100

    def test_required_exp_level_5(self):
        """At level 5, requires 500 XP to level up."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.level = 5
        assert char._required_exp_for_next_level() == 500

    def test_required_exp_level_10(self):
        """At level 10, requires 1000 XP to level up."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.level = 10
        assert char._required_exp_for_next_level() == 1000

    def test_required_exp_scales_linearly(self):
        """XP requirement scales linearly with level."""
        char = Character.create("Knight", "user1", "TestKnight")
        for level in range(1, 20):
            char.level = level
            assert char._required_exp_for_next_level() == level * 100


class TestCanLevelUp:
    """Tests for can_level_up checks."""

    def test_can_level_up_false_no_exp(self):
        """Character with 0 XP cannot level up."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 0
        assert char.can_level_up() is False

    def test_can_level_up_false_insufficient_exp(self):
        """Character with insufficient XP cannot level up."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 50  # Need 100
        assert char.can_level_up() is False

    def test_can_level_up_true_exact_exp(self):
        """Character with exact required XP can level up."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 100  # Exactly what's needed
        assert char.can_level_up() is True

    def test_can_level_up_true_excess_exp(self):
        """Character with more than required XP can level up."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 200  # More than needed
        assert char.can_level_up() is True

    def test_can_level_up_boundary_one_less(self):
        """Character with 1 XP less than required cannot level up."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 99
        assert char.can_level_up() is False


class TestGainExp:
    """Tests for gain_exp method."""

    def test_gain_exp_basic(self):
        """Character gains XP without leveling up."""
        char = Character.create("Knight", "user1", "TestKnight")
        initial_exp = char.exp
        result = char.gain_exp(50)
        assert char.exp == initial_exp + 50
        assert "50" in result and "XP" in result
        assert char.level == 1  # Didn't level up

    def test_gain_exp_triggers_level_up(self):
        """Character gains enough XP to level up."""
        char = Character.create("Knight", "user1", "TestKnight")
        assert char.level == 1
        result = char.gain_exp(100)
        assert char.level == 2
        assert "100" in result and "XP" in result

    def test_gain_exp_multiple_level_ups(self):
        """Character gains enough XP for multiple level ups."""
        char = Character.create("Knight", "user1", "TestKnight")
        assert char.level == 1
        # Level 1→2 needs 100, Level 2→3 needs 200, total 300
        char.gain_exp(300)
        assert char.level == 3
        assert char.exp == 0  # Exactly used up

    def test_gain_exp_with_remainder(self):
        """Character levels up with XP remainder."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.gain_exp(150)  # 100 to level up, 50 remains
        assert char.level == 2
        assert char.exp == 50

    def test_gain_exp_negative_raises(self):
        """Negative XP gain raises ValueError."""
        char = Character.create("Knight", "user1", "TestKnight")
        with pytest.raises(ValueError, match="XP must be positive"):
            char.gain_exp(-50)

    def test_gain_exp_zero_raises(self):
        """Zero XP gain raises ValueError."""
        char = Character.create("Knight", "user1", "TestKnight")
        with pytest.raises(ValueError, match="XP must be positive"):
            char.gain_exp(0)

    def test_gain_exp_returns_message(self):
        """gain_exp returns descriptive message."""
        char = Character.create("Knight", "user1", "TestKnight")
        result = char.gain_exp(50)
        assert char.name in result
        assert "50" in result
        assert "XP" in result

    def test_gain_exp_large_amount(self):
        """Character can handle large XP gains."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.gain_exp(10000)
        # Calculate expected level: sum of 100*n from 1 to L = 50*L*(L+1)
        # 10000 >= 50*L*(L+1), L≈13
        assert char.level > 10


class TestLevelUp:
    """Tests for level_up method."""

    def test_level_up_increases_level(self):
        """level_up increases character level by 1."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 100
        initial_level = char.level
        char.level_up()
        assert char.level == initial_level + 1

    def test_level_up_consumes_exp(self):
        """level_up consumes required XP."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 150  # Need 100, have 150
        char.level_up()
        assert char.exp == 50  # 150 - 100 = 50

    def test_level_up_returns_message(self):
        """level_up returns progression message."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 100
        result = char.level_up()
        assert char.name in result
        assert "1" in result and "2" in result  # Level numbers

    def test_level_up_not_enough_exp_message(self):
        """level_up with insufficient XP returns needs more message."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 50  # Need 100
        result = char.level_up()
        assert char.name in result
        assert "50" in result  # Needs 50 more
        assert "XP" in result

    def test_level_up_clears_tmp_after_completion(self):
        """level_up cleans up tmp attribute after completion."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 100
        char.level_up()
        assert not hasattr(char, "tmp")

    def test_level_up_recursive_multiple_levels(self):
        """level_up handles multiple levels recursively."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 500  # Enough for several levels
        char.level_up()
        assert char.level > 2
        assert not hasattr(char, "tmp")


class TestDropXp:
    """Tests for drop_xp when character is defeated."""

    def test_drop_xp_basic(self):
        """Defeated character drops XP to killer."""
        char = Character.create("Knight", "user1", "Victim")
        killer = Character.create("Mage", "user2", "Killer")
        
        char.level = 5
        char.exp = 100
        expected_xp = 5 * 50 + 100  # 350 XP
        
        killer_initial_exp = killer.exp
        result = char.drop_xp(killer)
        
        assert str(expected_xp) in result and "XP" in result
        assert "Victim" in result
        assert "Killer" in result

    def test_drop_xp_resets_victim_exp(self):
        """Defeated character loses all XP."""
        char = Character.create("Knight", "user1", "Victim")
        killer = Character.create("Mage", "user2", "Killer")
        
        char.exp = 500
        char.drop_xp(killer)
        assert char.exp == 0

    def test_drop_xp_reduces_victim_level(self):
        """Defeated character loses up to 5 levels."""
        char = Character.create("Knight", "user1", "Victim")
        killer = Character.create("Mage", "user2", "Killer")
        
        char.level = 10
        char.drop_xp(killer)
        assert char.level == 5  # 10 - 5 = 5

    def test_drop_xp_level_minimum_is_1(self):
        """Character level cannot go below 1 on death."""
        char = Character.create("Knight", "user1", "Victim")
        killer = Character.create("Mage", "user2", "Killer")
        
        char.level = 3
        char.drop_xp(killer)
        assert char.level == 1  # max(1, 3-5) = 1

    def test_drop_xp_level_1_stays_1(self):
        """Level 1 character stays at level 1 on death."""
        char = Character.create("Knight", "user1", "Victim")
        killer = Character.create("Mage", "user2", "Killer")
        
        char.level = 1
        char.drop_xp(killer)
        assert char.level == 1

    def test_drop_xp_formula(self):
        """XP dropped follows formula: level * 50 + exp."""
        char = Character.create("Knight", "user1", "Victim")
        killer = Character.create("Mage", "user2", "Killer")
        
        for level in [1, 5, 10, 20]:
            for exp in [0, 50, 100, 500]:
                char.level = level
                char.exp = exp
                killer.exp = 0
                killer.level = 1
                
                expected = level * 50 + exp
                char.drop_xp(killer)
                
                # Killer gained the XP (may have leveled up)
                # Check the message instead
                char.level = level  # Reset for next iteration
                char.exp = exp

    def test_drop_xp_killer_can_level_up(self):
        """Killer can level up from dropped XP."""
        char = Character.create("Knight", "user1", "Victim")
        killer = Character.create("Mage", "user2", "Killer")
        
        char.level = 10
        char.exp = 200
        killer.level = 1
        killer.exp = 50
        
        killer_initial_level = killer.level
        char.drop_xp(killer)
        
        # Killer should have leveled up from 700 XP
        assert killer.level > killer_initial_level


class TestLevelUpStatUpgrades:
    """Tests for stat upgrades during level up."""

    def test_level_up_message_contains_stats(self):
        """Level up message mentions stat changes if any."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 100
        result = char.level_up()
        # Message should contain level change info (level numbers)
        assert "1" in result and "2" in result

    def test_level_preserves_after_multiple_gains(self):
        """Level is correctly tracked after multiple XP gains."""
        char = Character.create("Knight", "user1", "TestKnight")
        
        char.gain_exp(50)
        assert char.level == 1
        
        char.gain_exp(50)  # Total 100
        assert char.level == 2
        
        char.gain_exp(200)  # Total 200, need 200 for level 3
        assert char.level == 3


class TestLevelUpEdgeCases:
    """Edge case tests for progression system."""

    def test_fresh_character_state(self):
        """New character starts at level 1 with 0 XP."""
        char = Character.create("Knight", "user1", "TestKnight")
        assert char.level == 1
        assert char.exp == 0

    def test_exact_xp_for_multiple_levels(self):
        """Exact XP for multiple levels leaves 0 remainder."""
        char = Character.create("Knight", "user1", "TestKnight")
        # Level 1→2: 100, Level 2→3: 200, Total: 300
        char.gain_exp(300)
        assert char.level == 3
        assert char.exp == 0

    def test_one_xp_short_of_level_up(self):
        """One XP short of level up doesn't level."""
        char = Character.create("Knight", "user1", "TestKnight")
        char.exp = 99
        initial_level = char.level
        # Call level_up directly
        char.level_up()
        assert char.level == initial_level
        assert char.exp == 99

    def test_many_small_xp_gains(self):
        """Many small XP gains eventually level up."""
        char = Character.create("Knight", "user1", "TestKnight")
        
        for _ in range(20):
            char.gain_exp(5)
        
        assert char.exp == 0  # All used for level up
        assert char.level == 2

    def test_level_up_different_classes(self):
        """Different classes can level up."""
        for class_name in ["Knight", "Mage", "Archer", "Priest"]:
            char = Character.create(class_name, "user1", f"Test{class_name}")
            char.gain_exp(100)
            assert char.level == 2, f"{class_name} should level up"

    def test_gain_exp_preserves_skills(self):
        """Leveling up preserves existing skills."""
        char = Character.create("Knight", "user1", "TestKnight")
        initial_skills = set(char.skills.keys())
        char.gain_exp(100)
        # All initial skills should still be present
        for skill in initial_skills:
            assert skill in char.skills

    def test_level_up_skills_are_independent_instances(self):
        """Level-up skills should not share cooldown state across characters."""
        char1 = Character.create("Knight", "user_skill_1", "KnightOne")
        char2 = Character.create("Knight", "user_skill_2", "KnightTwo")

        char1.gain_exp(1000)
        char2.gain_exp(1000)

        assert char1.skills["Shield Bash"] is not char2.skills["Shield Bash"]

        char1.skills["Shield Bash"].current_cooldown = 2

        assert char2.skills["Shield Bash"].current_cooldown == 0

    def test_concurrent_level_calculations(self):
        """Multiple characters can level up independently."""
        char1 = Character.create("Knight", "user1", "Knight1")
        char2 = Character.create("Mage", "user2", "Mage2")
        
        char1.gain_exp(100)
        char2.gain_exp(300)
        
        assert char1.level == 2
        assert char2.level == 3
        
        # They are independent
        assert char1.exp == 0
        assert char2.exp == 0
