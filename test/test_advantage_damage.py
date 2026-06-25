from jeuxRPG._class.character import Character
from jeuxRPG._class.res.advantage import Advantage
from jeuxRPG._class.res.classType import DamageType, SkillType
from jeuxRPG._class.skills.skill import Skill
from jeuxRPG._class.skills.skillEffect import SkillEffect


def make_damage_skill(name: str, dmg: int, dtype: DamageType) -> Skill:
    return Skill(
        name=name,
        skill_type=SkillType.DAMAGE,
        effects={"damage": SkillEffect(value=dmg)},
        damage_type=dtype,
        cooldown=0,
    )


def test_advantage_modifiers_increase_and_decrease():
    caster = Character.create("Mage", user_id="c1", name="Caster")
    target = Character.create("Knight", user_id="t1", name="Target")

    base_skill = make_damage_skill("Probe", 8, DamageType.MAGIC)

    # Neutral baseline: no advantage
    target.class_table["advantage"] = {"weakness": [], "resilience": []}
    neutral = base_skill.get_true_damage(caster, target)

    # Weakness: MAGIC in weakness should increase damage
    target.class_table["advantage"] = {"weakness": [DamageType.MAGIC], "resilience": []}
    weak = base_skill.get_true_damage(caster, target)

    # Resilience: MAGIC in resilience should decrease damage
    target.class_table["advantage"] = {"weakness": [], "resilience": [DamageType.MAGIC]}
    resist = base_skill.get_true_damage(caster, target)

    assert weak > neutral > resist
