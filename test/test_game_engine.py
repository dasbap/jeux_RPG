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


def test_tower_default_bosses_spawn_every_five_floors():
    from jeuxRPG.game_engine.tower import TowerRun

    player = Character.create("Knight", user_id="tower_default_boss_player", name="Player")
    engine = RecordingEngine()
    runner = TowerRun(engine)

    reached = runner.run_tour(
        player,
        start_floor=1,
        max_floors=10,
        enemies_before_boss_range=(1, 1),
    )

    boss_floors = [
        int(fight.defenders.fighters[0].name.split("L", 1)[1].split("#", 1)[0])
        for fight in engine.fights
        if fight.defenders.fighters and getattr(fight.defenders.fighters[0], "is_boss", False)
    ]

    assert reached == 10
    assert boss_floors == [5, 10]


def test_tower_run_reports_only_cleared_floors():
    from jeuxRPG.game_engine.tower import TowerRun

    player = Character.create("Knight", user_id="tower_progress_player", name="Player")
    cleared_floors = []
    runner = TowerRun(RecordingEngine())

    reached = runner.run_tour(
        player,
        start_floor=4,
        max_floors=6,
        enemies_before_boss_range=(1, 1),
        boss_floor_interval=0,
        on_floor_cleared=cleared_floors.append,
    )

    assert reached == 6
    assert cleared_floors == [4, 5, 6]


def test_tower_easy_restores_hp_after_floor():
    from jeuxRPG.game_engine.tower import TowerRun

    runner = TowerRun(GameEngine())
    player = Character.create("Knight", user_id="tower_rest_player", name="Player")
    player.lose_hp(Character.create("Mob", user_id="tower_rest_mob", name="Mob"), 10)
    damaged_hp = player.hp.current_value

    runner.rest_party_after_floor([player], "easy")

    assert player.hp.current_value > damaged_hp


def test_tower_difficulty_scales_mob_level():
    from jeuxRPG.game_engine.tower import TowerRun

    runner = TowerRun(GameEngine())

    easy_mob = runner._make_mob(floor=8, idx=1, difficulty="easy")
    hard_mob = runner._make_mob(floor=8, idx=1, difficulty="hard")

    assert hard_mob.level > easy_mob.level


def test_tower_easy_mobs_give_reduced_xp_reward():
    from jeuxRPG.game_engine.tower import TowerRun

    runner = TowerRun(GameEngine())
    mob = runner._make_mob(floor=20, idx=1, difficulty="easy")

    assert mob.get_xp_reward() < mob.level * 50


def test_tower_easy_reward_curve_keeps_knight_below_floor_level():
    from jeuxRPG._balance.simulator import simulate_tower

    report = simulate_tower(
        class_name="Knight",
        difficulty="easy",
        floors=20,
        start_floor=1,
        enemies_per_floor=1,
        seed=42,
        resolution="reward_curve",
    )

    assert report["completed"] is True
    assert 10 <= report["final_level"] <= 15
