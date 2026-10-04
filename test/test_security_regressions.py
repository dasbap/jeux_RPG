import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from jeuxRPG._class.character import Character
from jeuxRPG._class._event.confrontation.encounter.fight import Fight
from jeuxRPG._class.res.classType import SkillType
from jeuxRPG._core.game_controller import GameController
from jeuxRPG._core.save import SaveManager, SaveCategory, EntitySaveData
from jeuxRPG.game_engine import GameEngine


@pytest.mark.parametrize("identifier", ["..", ".", "", "a/b", "a\\b", "a:b", "a\x00", "a" * 129])
def test_save_rejects_unsafe_ids(tmp_path, identifier):
    manager = SaveManager(tmp_path / "saves")
    for method in (manager.save, manager.load, manager.delete):
        with pytest.raises(ValueError):
            if method == manager.save:
                method(SaveCategory.PLAYERS, identifier, {})
            else:
                method(SaveCategory.PLAYERS, identifier)
    assert not (tmp_path / "saves" / "character.json").exists()


def test_save_rejects_symlink_escape_and_preserves_prior_data(tmp_path):
    manager = SaveManager(tmp_path / "saves")
    outside = tmp_path / "outside"
    outside.mkdir()
    (manager.base_path / "players" / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        manager.save(SaveCategory.PLAYERS, "escape", {})
    manager.save(SaveCategory.PLAYERS, "safe", {"hp": 10})
    assert manager.save(SaveCategory.PLAYERS, "safe", {"bad": object()}) is False
    assert manager.load(SaveCategory.PLAYERS, "safe") == {"hp": 10}
    assert not list(outside.iterdir())


def test_deleted_player_is_not_listed(tmp_path):
    manager = SaveManager(tmp_path)
    manager.save(SaveCategory.PLAYERS, "player", {})
    manager.delete(SaveCategory.PLAYERS, "player")
    assert "player" not in manager.list_ids(SaveCategory.PLAYERS)


def test_legacy_controller_rejects_paths(tmp_path):
    controller = GameController()
    controller.set_save_path(str(tmp_path))
    for method in (controller.create_save, controller.load_save, controller.del_save):
        with pytest.raises(ValueError):
            method("../../victim")


def test_character_serialization_uses_stat_values():
    character = Character.create("Knight", "test", "Chevalier")
    saved = EntitySaveData.from_character(character)
    assert saved.stats["force"] == character.force.current_value


def test_invalid_combat_target_does_not_consume_turn():
    actor = Character.create("Knight", "actor", "Chevalier")
    enemy = Character.create("Mage", "enemy", "Mage")
    stranger = Character.create("Knight", "stranger", "Tiers")
    fight = Fight(actor, enemy)
    skill = next(name for name, skill in actor.skills.items() if skill.skill_type == SkillType.DAMAGE)
    assert fight.play(actor, stranger, skill) is False
    assert actor in fight.can_play
    assert fight.play(actor, actor, skill) is False
    assert actor in fight.can_play


def test_resurrection_can_target_defeated_ally():
    priest = Character.create("Priest", "priest", "Prêtre")
    ally = Character.create("Knight", "ally", "Allié")
    from jeuxRPG._class.skills.skill import Skill
    priest.skills["Revive"] = Skill("Audit Revive", SkillType.RESURRECT, {}, energie_target=type(priest.energie[0]))
    ally.hp.current_value = 0
    success, _ = priest.use_skill("Revive", ally)
    assert success
    assert ally.is_alive()


def test_reservation_is_atomic_across_threads():
    engine = GameEngine()
    actor = Character.create("Knight", "actor", "Chevalier")
    enemy = Character.create("Mage", "enemy", "Mage")
    fight = Fight(actor, enemy)
    barrier = threading.Barrier(2)
    def reserve(_):
        barrier.wait()
        try:
            return engine._reserve([fight])
        except ValueError:
            return None
    with ThreadPoolExecutor(2) as pool:
        assert sum(result is not None for result in pool.map(reserve, range(2))) == 1


def test_async_engine_works_inside_existing_loop():
    async def run():
        actor = Character.create("Knight", "actor", "Chevalier")
        enemy = Character.create("Goblin", "enemy", "Gobelin")
        engine = GameEngine()
        await engine.run_fights_async([Fight(actor, enemy)], timeout=5)
        assert not engine._active_characters
        with pytest.raises(RuntimeError, match="run_fights_async"):
            engine.run_fights([])
    asyncio.run(run())


def test_repeated_cancellation_waits_for_worker_before_releasing_participants():
    started = threading.Event()
    release = threading.Event()
    class SlowFight:
        def __init__(self):
            self.cleaned = False
        def get_all_individuals(self):
            return [Character.create("Knight", "locked_actor", "Acteur")]
        def is_over(self):
            return False
        def start_round(self, rest):
            started.set()
            release.wait(3)
        def end(self):
            self.cleaned = True
    async def run():
        engine = GameEngine()
        fight = SlowFight()
        task = asyncio.create_task(engine.run_fights_async([fight]))
        await asyncio.to_thread(started.wait, 2)
        assert started.is_set()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert "locked_actor" in engine._active_characters
        assert not fight.cleaned
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert fight.cleaned
        assert not engine._active_characters
    try:
        asyncio.run(run())
    finally:
        release.set()
