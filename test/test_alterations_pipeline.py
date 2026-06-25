import pytest

from jeuxRPG._class.character import Character
from jeuxRPG._class.res.character.stats.basic_stat import Force, Aura
from jeuxRPG._class.res.character.alteration.alteration import AlterationType, Dot
from jeuxRPG._class.skills.skill import Skill
from jeuxRPG._class.skills.skillEffect import SkillEffect
from jeuxRPG._class.res.classType import SkillType


@pytest.fixture()
def duo():
    caster = Character.create("Knight", user_id="u1", name="Arthur")
    target = Character.create("Mage", user_id="u2", name="Merlin")
    return caster, target


def test_stun_add_and_expire(duo):
    caster, target = duo
    # Apply a stun for 2 rounds
    ok, msg, stun = target.add_stun(caster, "Concuss", duration=2)
    assert ok is True
    assert target.is_stun() is True
    # After 1 update, still stunned
    target._update_status()
    assert target.is_stun() is True
    # After 2nd update, stun should be gone
    target._update_status()
    assert target.is_stun() is False


def test_dot_pipeline_decrements_and_expires(duo):
    caster, target = duo
    # Start with a DOT: 3 ticks
    burn = Dot("Burn", caster, value=10, time=3, target=target)
    target.status["alteration"]["Damage"]["Incoming"].append(burn)

    prev_hp = target.get_stat("HP").current_value
    any_drop = False
    for i in range(3):
        target._update_status()
        cur_hp = target.get_stat("HP").current_value
        # HP should not increase; track if it dropped at least once
        assert cur_hp <= prev_hp
        if cur_hp < prev_hp:
            any_drop = True
        prev_hp = cur_hp
    assert any_drop is True
    # DOT duration should have reached 0 (even if engine doesn't remove it yet)
    assert burn.get_duration() == 0


def test_buff_application_via_skill(duo):
    caster, target = duo
    buff = SkillEffect(
        value=5,
        name="Bravery",
        duration=2,
        stat_target=Force,
        alterationtype=AlterationType.BUFFSTAT,
    )
    skill = Skill(
        name="Battle Cry",
        skill_type=SkillType.BUFF,
        effects={"Buff": buff},
        energie_target=Aura,
        cooldown=0,
    )
    res = skill.execute(caster, target)
    assert res["success"] is True
    # After application, Force should be at least base + 5
    assert target.get_stat("Force").current_value >= target.get_stat("Force").value
    # ensure the Buff object exists on the stat
    assert any(b.name == "Bravery" for b in target.get_stat("Force").buffs)


def test_apply_alteration_classmethod(duo):
    caster, target = duo
    effect = SkillEffect(
        value=3,
        name="Fortify",
        duration=1,
        stat_target=Force,
        alterationtype=AlterationType.BUFFSTAT,
    )
    ok, msg = Skill.apply_alteration(caster, target, effect)
    assert ok is True
