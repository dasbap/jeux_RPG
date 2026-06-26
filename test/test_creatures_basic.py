from jeuxRPG._class.character import Character
from jeuxRPG._class.res.classType import DamageType, SkillType
from jeuxRPG._class.skills.skill import Skill
from jeuxRPG._class.skills.skillEffect import SkillEffect


def _damage_probe(dtype: DamageType) -> Skill:
    return Skill(
        name=f"{dtype.name.title()} Probe",
        skill_type=SkillType.DAMAGE,
        damage_type=dtype,
        effects={"damage": SkillEffect(value=12)},
        cooldown=0,
    )


def test_goblin_has_debuff_and_applies_it():
    gob = Character.create("Goblin", user_id="g1", name="Gob")
    target = Character.create("Mage", user_id="m1", name="Merlin")
    assert "Dirty Tricks" in gob.skills
    ok, msg = gob.use_skill("Dirty Tricks", target)
    assert ok is True
    # Endurance should have at least one debuff with the matching name
    debuffs = [d for d in target.get_stat("Endurance").debuffs if getattr(d, "name", None) == "Dirty Tricks"]
    assert len(debuffs) >= 1


def test_orc_rally_buffs_force_self():
    orc = Character.create("Orc", user_id="o1", name="Gor")
    base_force = orc.get_stat("Force").current_value
    assert "Rally" in orc.skills
    ok, msg = orc.use_skill("Rally")
    assert ok is True
    # Force should be >= base after buff
    assert orc.get_stat("Force").current_value >= base_force


def test_dragon_whelp_wing_buffet_stuns_target():
    drake = Character.create("DragonWhelp", user_id="d1", name="Dray")
    target = Character.create("Knight", user_id="k1", name="Arth")
    assert "Wing Buffet" in drake.skills
    ok, msg = drake.use_skill("Wing Buffet", target)
    assert ok is True
    # Target should have at least one stun alteration pending
    assert target.is_stun() is True


def test_existing_generic_creatures_are_neutral():
    for class_name in ("Goblin", "Orc", "DragonWhelp"):
        creature = Character.create(class_name, user_id=f"{class_name}_neutral", name=class_name)
        advantage = creature.class_table["advantage"]

        assert advantage["weakness"] == []
        assert advantage["resilience"] == []


def test_resistant_mobs_are_registered_and_non_playable():
    for class_name in ("PhysicalResistantMob", "MagicResistantMob", "SacredResistantMob"):
        mob = Character.create(class_name, user_id=f"{class_name}_1", name=class_name)

        assert mob.is_playable is False
        assert mob.char_class == class_name


def test_resistant_mobs_have_expected_advantages():
    expected = {
        "PhysicalResistantMob": (DamageType.PHYSICAL, DamageType.MAGIC),
        "MagicResistantMob": (DamageType.MAGIC, DamageType.SACRED),
        "SacredResistantMob": (DamageType.SACRED, DamageType.PHYSICAL),
    }

    for class_name, (resilience, weakness) in expected.items():
        mob = Character.create(class_name, user_id=f"{class_name}_adv", name=class_name)
        advantage = mob.class_table["advantage"]

        assert resilience in advantage["resilience"]
        assert weakness in advantage["weakness"]


def test_resistant_mobs_reduce_matching_damage():
    caster = Character.create("Mage", user_id="resist_caster", name="Caster")
    cases = (
        ("PhysicalResistantMob", DamageType.PHYSICAL),
        ("MagicResistantMob", DamageType.MAGIC),
        ("SacredResistantMob", DamageType.SACRED),
    )

    for class_name, damage_type in cases:
        skill = _damage_probe(damage_type)
        neutral_target = Character.create(class_name, user_id=f"{class_name}_neutral", name="Neutral")
        resistant_target = Character.create(class_name, user_id=f"{class_name}_resist", name="Resistant")
        neutral_target.class_table["advantage"] = {"weakness": [], "resilience": []}

        neutral_damage = skill.get_true_damage(caster, neutral_target)
        resisted_damage = skill.get_true_damage(caster, resistant_target)

        assert resisted_damage < neutral_damage
