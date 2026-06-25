from jeuxRPG._class.character import Character


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
