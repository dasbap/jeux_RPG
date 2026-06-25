import pytest

from jeuxRPG.game_engine import GameEngine
from jeuxRPG._class._event.confrontation.encounter.fight import Fight
from jeuxRPG._class.character import Character


def make_char(cls_name: str, uid: str, name: str) -> Character:
    return Character.create(cls_name, user_id=uid, name=name)


class RecordingEngine:
    def __init__(self):
        self.fights = []

    def run_fights(self, fights, timeout=None):
        self.fights.extend(fights)


def test_run_two_disjoint_fights():
    a1 = make_char("Knight", "a1", "A1")
    a2 = make_char("Orc", "a2", "A2")
    b1 = make_char("Mage", "b1", "B1")
    b2 = make_char("Goblin", "b2", "B2")

    f1 = Fight(a1, a2, name="Duel1")
    f2 = Fight(b1, b2, name="Duel2")

    engine = GameEngine()
    # should complete without raising
    engine.run_fights([f1, f2], timeout=5)

    assert f1.is_over() or f1.round >= 2
    assert f2.is_over() or f2.round >= 2


def test_prevent_character_in_multiple_fights_same_run():
    a = make_char("Knight", "u1", "Hero")
    b = make_char("Mage", "u2", "Mage")
    c = make_char("Orc", "u3", "Orc")

    f1 = Fight(a, b)
    f2 = Fight(a, c)

    engine = GameEngine()
    with pytest.raises(ValueError):
        engine.run_fights([f1, f2])


def test_tower_run_simple_sequence():
    # small deterministic tower run using a 1-enemy floor to validate flow
    random_seed = 42
    import random as _r
    _r.seed(random_seed)

    player = Character.create("Knight", user_id="p1", name="Player")
    engine = GameEngine()
    from jeuxRPG.game_engine.tower import TowerRun

    runner = TowerRun(engine)
    # run 2 floors, but set enemies_before_boss_range to (1,1) for speed
    reached = runner.run_tour(player, start_floor=1, max_floors=2, enemies_before_boss_range=(1, 1))
    assert isinstance(reached, int)


def test_tower_boss_is_tougher_than_regular_mob():
    from jeuxRPG.game_engine.tower import TowerRun

    runner = TowerRun(GameEngine())
    mob = runner._make_mob(floor=4, idx=1, is_boss=False)
    boss = runner._make_mob(floor=4, idx=0, is_boss=True)

    assert boss.is_boss is True
    assert boss.is_tough is True
    assert boss.level > mob.level
    assert boss.get_stat("HP").value > mob.get_stat("HP").value
    assert boss.get_stat("Endurance").value > mob.get_stat("Endurance").value
    assert boss.get_stat("Force").value > mob.get_stat("Force").value


def test_tower_boss_floor_interval_controls_boss_floors():
    from jeuxRPG.game_engine.tower import TowerRun

    player = Character.create("Knight", user_id="tower_player", name="Player")
    engine = RecordingEngine()
    runner = TowerRun(engine)

    reached = runner.run_tour(
        player,
        start_floor=1,
        max_floors=5,
        enemies_before_boss_range=(1, 1),
        boss_start_floor=3,
        boss_floor_interval=2,
        special_boss_interval=0,
    )

    boss_floors = [
        int(fight.defenders.fighters[0].name.split("L", 1)[1].split("#", 1)[0])
        for fight in engine.fights
        if fight.defenders.fighters and getattr(fight.defenders.fighters[0], "is_boss", False)
    ]

    assert reached == 5
    assert boss_floors == [3, 5]
