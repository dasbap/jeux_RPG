import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest

from jeuxRPG._class.character import Character
from jeuxRPG._class.res.team.team import Team
from jeuxRPG._class._event.confrontation.encounter.fight import Fight
from jeuxRPG._class.res.character.stats.basic_stat import Aura
from jeuxRPG.game_engine import GameEngine


def test_negative_energy_cannot_generate_energy():
    knight = Character.create("Knight", "energy", "Knight")
    before = knight.get_energie(Aura).current_value
    with pytest.raises(ValueError):
        knight.consume_energie(-10, Aura)
    assert knight.get_energie(Aura).current_value == before


def test_death_rewards_are_not_repeated():
    attacker = Character.create("Knight", "attacker", "Attacker")
    victim = Character.create("Goblin", "victim", "Victim")
    victim.lose_hp(attacker, 100000)
    progression = (attacker.level, attacker.exp)
    victim.lose_hp(attacker, 100000)
    assert (attacker.level, attacker.exp) == progression


def test_merge_transfers_members_and_destroy_clears_leader():
    first = Character.create("Knight", "merge1", "First")
    second = Character.create("Mage", "merge2", "Second")
    left = Team("regression-left", first)
    right = Team("regression-right", second)
    try:
        left.merge_with(right)
        assert second.team is left
        assert right not in Team.all_teams
        assert left.get_fighters() == [first, second]
        left.destroy()
        assert first.team is None
        assert second.team is None
        assert left.leader is None
    finally:
        left.destroy()
        right.destroy()


def test_rejected_participant_does_not_corrupt_fight():
    first = Character.create("Knight", "fight1", "First")
    second = Character.create("Mage", "fight2", "Second")
    fight = Fight(first, second)
    with pytest.raises(ValueError):
        fight.add_defender(first)
    assert fight.defenders.fighters == [second]
    fight.end()


def test_engine_registration_is_atomic():
    engine = GameEngine()
    barrier = Barrier(2)
    release = Event()

    class StubFight:
        def get_all_individuals(self):
            return [type("Participant", (), {"get_id": lambda self: "shared"})()]

    def reserve():
        barrier.wait(timeout=5)
        try:
            engine._check_overlaps([StubFight()])
        except ValueError:
            return False
        release.wait(timeout=5)
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(reserve)
        second = pool.submit(reserve)
        release.set()
        assert sorted([first.result(), second.result()]) == [False, True]


def test_cli_launch_and_invalid_arguments():
    result = subprocess.run([sys.executable, "-m", "jeuxRPG", "--floors", "2"], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert '"completed": true' in result.stdout
    result = subprocess.run([sys.executable, "-m", "jeuxRPG", "--floors", "0"], capture_output=True, text=True, timeout=15)
    assert result.returncode == 2


def test_damage_over_time_expires_and_simultaneous_stuns_expire():
    from jeuxRPG._class.res.character.alteration.alteration import Dot, Stun, AlterationType

    source = Character.create("Knight", "dot-source", "Source")
    target = Character.create("Knight", "dot-target", "Target")
    dot = Dot("Poison", source, 10, 1, target)
    assert dot.type is AlterationType.DOT
    target.status["alteration"]["Damage"]["Incoming"].append(dot)
    target.status["alteration"]["stun"].extend([Stun("A", source, 1, target), Stun("B", source, 1, target)])
    target._update_status()
    hp = target.hp.current_value
    assert not target.status["alteration"]["Damage"]["Incoming"]
    assert not target.is_stun()
    target._update_status()
    assert target.hp.current_value == hp
