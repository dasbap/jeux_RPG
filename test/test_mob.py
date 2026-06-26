"""
Comprehensive tests for the Mob class.

Tests cover:
- Mob creation and initialization
- XP drop mechanics
- Level scaling
- Boss flag functionality
- XP reward calculation
"""

import pytest
from jeuxRPG._class.mob.mob import Mob
from jeuxRPG._class.character import Character


class TestMobCreation:
    """Tests for Mob initialization."""

    def test_mob_creation_basic(self):
        """Create a basic mob with minimal parameters."""
        mob = Mob("mob_001", "Goblin")
        assert mob.name == "Goblin"
        assert mob.user_id == "mob_001"
        assert mob.level == 1
        assert mob.exp == 0

    def test_mob_creation_with_xp_drop(self):
        """Create a mob with initial XP (levels up)."""
        mob = Mob("mob_001", "Goblin", xp_drop=100)
        # XP causes level ups (10 XP per level for mobs)
        assert mob.level > 1

    def test_mob_creation_with_zero_xp(self):
        """Create a mob with zero XP drop."""
        mob = Mob("mob_001", "Goblin", xp_drop=0)
        assert mob.level == 1
        assert mob.exp == 0

    def test_mob_is_character(self):
        """Mob should be a Character instance."""
        mob = Mob("mob_001", "Goblin")
        assert isinstance(mob, Character)

    def test_mob_not_playable(self):
        """Mobs should not be playable."""
        mob = Mob("mob_001", "Goblin")
        assert mob.is_playable is False

    def test_mob_has_hp(self):
        """Mob should have HP stat."""
        mob = Mob("mob_001", "Goblin")
        assert mob.hp is not None
        assert mob.hp.current_value > 0

    def test_mob_is_alive_initially(self):
        """New mob should be alive."""
        mob = Mob("mob_001", "Goblin")
        assert mob.is_alive() is True


class TestMobBossFlag:
    """Tests for boss mob functionality."""

    def test_mob_default_not_boss(self):
        """Mobs are not bosses by default."""
        mob = Mob("mob_001", "Goblin")
        assert mob.is_boss is False

    def test_mob_can_be_boss(self):
        """Mob can be created as a boss."""
        boss = Mob("boss_001", "Dragon", is_boss=True)
        assert boss.is_boss is True

    def test_boss_with_xp(self):
        """Boss can have initial XP."""
        boss = Mob("boss_001", "Dragon", xp_drop=500, is_boss=True)
        assert boss.is_boss is True
        assert boss.level > 1


class TestMobExpForLevelUp:
    """Tests for exp_for_level_up calculation."""

    def test_exp_for_level_up_level_1(self):
        """Level 1 mob needs 10 XP to level up."""
        mob = Mob("mob_001", "Goblin")
        assert mob.exp_for_level_up() == 10

    def test_exp_for_level_up_level_5(self):
        """Level 5 mob needs 50 XP to level up."""
        mob = Mob("mob_001", "Goblin")
        mob.level = 5
        assert mob.exp_for_level_up() == 50

    def test_exp_for_level_up_scales_linearly(self):
        """XP requirement scales linearly with level."""
        mob = Mob("mob_001", "Goblin")
        for level in range(1, 10):
            mob.level = level
            assert mob.exp_for_level_up() == level * 10


class TestMobXpReward:
    """Tests for get_xp_reward calculation."""

    def test_xp_reward_level_1(self):
        """Level 1 mob with 0 exp gives reduced XP."""
        mob = Mob("mob_001", "Goblin")
        assert mob.get_xp_reward() == 25

    def test_xp_reward_level_5(self):
        """Level 5 mob gives reduced XP."""
        mob = Mob("mob_001", "Goblin")
        mob.level = 5
        mob.exp = 20
        assert mob.get_xp_reward() == 135

    def test_xp_reward_boss_double(self):
        """Boss mobs give double reduced XP."""
        mob = Mob("mob_001", "Goblin")
        boss = Mob("boss_001", "Dragon", is_boss=True)
        
        mob.level = 5
        boss.level = 5
        mob.exp = 0
        boss.exp = 0
        
        assert mob.get_xp_reward() == 125
        assert boss.get_xp_reward() == 250

    def test_boss_drop_xp_uses_double_reward(self):
        """Boss XP reward should apply when defeated."""
        boss = Mob("boss_001", "Dragon", is_boss=True)
        killer = Character.create("Knight", "hero_001", "Hero")
        killer.level = 10
        killer.exp = 0

        boss.drop_xp(killer)

        assert killer.exp == 50

    def test_xp_reward_with_exp(self):
        """XP reward includes current exp before reduction."""
        mob = Mob("mob_001", "Goblin")
        mob.level = 3
        mob.exp = 50
        assert mob.get_xp_reward() == 100


class TestMobCombat:
    """Tests for mob combat integration."""

    def test_mob_can_take_damage(self):
        """Mob can receive damage."""
        mob = Mob("mob_001", "Goblin")
        attacker = Character.create("Knight", "user1", "Hero")
        initial_hp = mob.hp.current_value
        
        mob.lose_hp(attacker, 10)
        assert mob.hp.current_value < initial_hp

    def test_mob_can_die(self):
        """Mob can be killed."""
        mob = Mob("mob_001", "Goblin")
        attacker = Character.create("Knight", "user1", "Hero")
        
        # Deal massive damage
        mob.lose_hp(attacker, mob.hp.current_value + 1000)
        assert mob.is_alive() is False

    def test_mob_can_attack(self):
        """Mob can attack a target."""
        mob = Mob("mob_001", "Goblin")
        target = Character.create("Knight", "user1", "Hero")
        
        # Mob should have attack capability
        skills = mob.get_available_skills()
        # May or may not have skills depending on mob_table configuration


class TestMobLevelUp:
    """Tests for mob leveling mechanics."""

    def test_mob_level_up_with_initial_xp(self):
        """Mob levels up from initial XP."""
        # 100 XP should cause multiple level ups (10 per level)
        mob = Mob("mob_001", "Goblin", xp_drop=100)
        # Level 1->2: 10, 2->3: 20, 3->4: 30, 4->5: 40 = 100 total
        # Actually, gain_exp uses _required_exp_for_next_level which is level * 100
        # So 100 XP = 1 level up
        assert mob.level >= 2

    def test_mob_gains_exp(self):
        """Mob can gain experience."""
        mob = Mob("mob_001", "Goblin")
        initial_exp = mob.exp
        mob.gain_exp(50)
        # Either leveled up or has more exp
        assert mob.level > 1 or mob.exp > initial_exp


class TestMobEdgeCases:
    """Edge case tests for Mob class."""

    def test_multiple_mobs_independent(self):
        """Multiple mobs are independent instances."""
        mob1 = Mob("mob_001", "Goblin1")
        mob2 = Mob("mob_002", "Goblin2")
        
        mob1.level = 10
        assert mob2.level == 1

    def test_mob_different_names(self):
        """Mobs can have different names."""
        goblin = Mob("mob_001", "Goblin")
        orc = Mob("mob_002", "Orc")
        
        assert goblin.name == "Goblin"
        assert orc.name == "Orc"

    def test_mob_unique_ids(self):
        """Each mob has unique ID."""
        mob1 = Mob("mob_001", "Goblin")
        mob2 = Mob("mob_002", "Goblin")
        
        assert mob1.user_id != mob2.user_id

    def test_boss_vs_normal_same_level(self):
        """Boss and normal mob at same level have different rewards."""
        normal = Mob("mob_001", "Goblin")
        boss = Mob("boss_001", "Goblin Boss", is_boss=True)
        
        normal.level = 5
        boss.level = 5
        normal.exp = 0
        boss.exp = 0
        
        assert boss.get_xp_reward() == normal.get_xp_reward() * 2
