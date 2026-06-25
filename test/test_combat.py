import pytest

from jeuxRPG._class._event.confrontation.encounter.fight import Fight
from jeuxRPG._class._event.confrontation.encounter.team_battle import TeamBattle
from jeuxRPG._class.character import Character
from jeuxRPG._class.res.team.team import Team


@pytest.fixture()
def duo_knight_mage():
    a = Character.create("Knight", user_id="u1", name="Arthur")
    b = Character.create("Mage", user_id="u2", name="Merlin")
    return a, b


def test_fight_1v1_round_progression(duo_knight_mage):
    a, b = duo_knight_mage
    f = Fight(a, b, name="Duel")

    hp_a0 = a.get_stat("HP").current_value
    hp_b0 = b.get_stat("HP").current_value

    # Use engine round resolution now that attack() is fixed
    f.start_round(rest=True)
    assert f.round >= 2
    assert len(f.log_message) > 0
    hp_a = a.get_stat("HP").current_value
    hp_b = b.get_stat("HP").current_value
    assert (hp_a < hp_a0) or (hp_b < hp_b0) or any("ne peut rien faire" in m for m in f.log_message)


def test_fight_play_specific_skill_consumes_turn(duo_knight_mage):
    a, b = duo_knight_mage
    f = Fight(a, b)

    # Ensure Knight has the expected skill
    assert "Sword Slash" in a.skills

    can_play_count = len(f.can_play)
    ok = f.play(a, b, "Sword Slash")
    assert ok is True
    # The actor should no longer be in can_play for this round
    assert len(f.can_play) == can_play_count - 1
    # Log should record an action (any damage/skill message)
    assert len(f.log_message) > 0


def test_team_battle_auto_battle_completes():
    # Create teams with two fighters each
    t1 = Team("Alpha")
    t2 = Team("Beta")

    a1 = Character.create("Knight", user_id="a1", name="A1")
    a2 = Character.create("Orc", user_id="a2", name="A2")
    b1 = Character.create("Mage", user_id="b1", name="B1")
    b2 = Character.create("Goblin", user_id="b2", name="B2")

    t1.add_fighter(a1)
    t1.add_fighter(a2)
    t2.add_fighter(b1)
    t2.add_fighter(b2)

    tb = TeamBattle(t1, t2)
    tb.auto_battle()
    assert tb.is_over() is True


def test_fight_prevents_play_when_stunned(duo_knight_mage):
    a, b = duo_knight_mage
    f = Fight(a, b)
    # Stun the actor 'a'
    ok, msg, stun = a.add_stun(a, "TestStun", duration=1)
    assert ok is True
    with pytest.raises(RuntimeWarning):
        f.play(a, b, "Sword Slash")
