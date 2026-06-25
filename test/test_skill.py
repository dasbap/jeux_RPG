"""Unit tests for Skill class and mechanics."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from jeuxRPG._class.skills.skill import Skill
from jeuxRPG._class.skills.skillEffect import SkillEffect
from jeuxRPG._class.res.classType import SkillType, DamageType
from jeuxRPG._class.res.character.stats.basic_stat import Mana, Force, Intelligence, Aura
from jeuxRPG._class.character import Character


@pytest.fixture(autouse=True)
def clear_all_skills():
    """Clear Skill.all_Skills before each test."""
    Skill.all_Skills.clear()
    yield
    Skill.all_Skills.clear()


@pytest.fixture
def test_skill():
    """Fixture providing a simple test skill."""
    return Skill(
        name="TestAttack",
        skill_type=SkillType.DAMAGE,
        effects={
            "damage": SkillEffect(
                name="damage_effect",
                value=20,
                alterationtype=None,
                stat_target=Force,
                duration=0,
                invocation=None
            )
        },
        require_target=True,
        can_target_others=True,
        energie_cost=10,
        damage_type=DamageType.PHYSICAL,
        energie_target=Aura,
        cooldown=0,
        description="A test attack skill"
    )


class TestSkillCreation:
    """Tests for Skill creation and initialization."""

    def test_skill_creation(self, test_skill):
        """Test skill is created with correct attributes."""
        assert test_skill.name == "TestAttack"
        assert test_skill.skill_type == SkillType.DAMAGE
        assert test_skill.energie_cost == 10
        assert test_skill.cooldown == 0
        assert test_skill.current_cooldown == 0

    def test_skill_negative_energie_cost_raises(self):
        """Test negative energy cost raises ValueError."""
        with pytest.raises(ValueError, match="Les coûts ne peuvent pas être négatifs"):
            Skill(
                name="BadSkill",
                skill_type=SkillType.DAMAGE,
                effects={},
                energie_cost=-10,
                energie_target=Aura
            )

    def test_skill_negative_cooldown_raises(self):
        """Test negative cooldown raises ValueError."""
        with pytest.raises(ValueError, match="Le cooldown ne peut pas être négatif"):
            Skill(
                name="BadSkill",
                skill_type=SkillType.DAMAGE,
                effects={},
                cooldown=-5,
                energie_target=Aura
            )


class TestSkillCooldown:
    """Tests for skill cooldown mechanics."""

    def test_skill_is_ready_initially(self, test_skill):
        """Test skill is ready when cooldown is 0."""
        assert test_skill.is_ready() is True

    def test_skill_setcooldown(self, test_skill):
        """Test setcooldown sets current_cooldown to cooldown value."""
        test_skill.cooldown = 3
        test_skill.setcooldown()
        assert test_skill.current_cooldown == 3

    def test_skill_setcooldown_not_ready_raises(self, test_skill):
        """Test setcooldown raises RuntimeError if already on cooldown."""
        test_skill.cooldown = 3
        test_skill.current_cooldown = 2
        with pytest.raises(RuntimeError, match="cooldown is not ready"):
            test_skill.setcooldown()

    def test_skill_update_cooldown(self, test_skill):
        """Test update_cooldown decrements cooldown."""
        test_skill.current_cooldown = 2
        test_skill.update_cooldown()
        assert test_skill.current_cooldown == 1

    def test_skill_reset_cooldown(self, test_skill):
        """Test reset_cooldown resets to 0."""
        test_skill.current_cooldown = 5
        test_skill.reset_cooldown()
        assert test_skill.current_cooldown == 0


class TestSkillEnergie:
    """Tests for skill energy checks."""

    def test_can_afford_with_enough_energie(self, test_skill):
        """Test can_afford returns True with sufficient energy."""
        knight = Character.create("Knight", "user123", "TestKnight")
        assert test_skill.can_afford(knight) is True

    def test_can_afford_with_insufficient_energie(self, test_skill):
        """Test can_afford returns False with insufficient energy."""
        knight = Character.create("Knight", "user123", "TestKnight")
        aura = knight.get_energie(Aura)
        aura.current_value = 5  # Less than skill cost (10)
        assert test_skill.can_afford(knight) is False

    def test_can_afford_with_invalid_caster(self, test_skill):
        """Test can_afford returns False if caster doesn't have energy."""
        assert test_skill.can_afford(None) is False


class TestSkillRepr:
    """Tests for skill string representation."""

    def test_skill_repr(self, test_skill):
        """Test __repr__ returns readable format."""
        repr_str = repr(test_skill)
        assert "TestAttack" in repr_str
        assert "cost: 10" in repr_str
        assert "cooldown: 0" in repr_str

    def test_skill_str(self, test_skill):
        """Test __str__ returns readable format."""
        str_str = str(test_skill)
        assert "TestAttack" in str_str
        assert "Cooldown: 0" in str_str


class TestSkillRegistration:
    """Tests for skill registration in all_Skills class variable."""

    def test_skill_registered_in_all_skills(self, test_skill):
        """Test skill is registered in Skill.all_Skills."""
        assert test_skill in Skill.all_Skills

    def test_get_skill_by_name(self, test_skill):
        """Test get_skill_by_name retrieves registered skill."""
        found = Skill.get_skill_by_name("TestAttack")
        assert found == test_skill

    def test_get_skill_by_name_not_found(self):
        """Test get_skill_by_name raises ValueError if not found."""
        with pytest.raises(ValueError, match="not found"):
            Skill.get_skill_by_name("NonExistentSkill")
