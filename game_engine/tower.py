import random
from typing import Tuple

from jeuxRPG.game_engine.engine import GameEngine
from jeuxRPG._class.character import Character
from jeuxRPG._class.mob.mob import Mob
from jeuxRPG._class._event.confrontation.encounter.fight import Fight


class TowerRun:
    """Runs a tower-style progression where a player faces waves of mobs per floor.

    Behavior:
    - Each floor spawns N mobs (N random between `enemies_before_boss_range`).
    - Boss floors spawn a tough mob after the regular encounters.
    - Every `special_boss_interval` boss floors spawn a stronger tough mob.
    - Mobs are scaled to the floor by granting XP to reach target level.
    """

    def __init__(self, engine: GameEngine):
        self.engine = engine

    def _xp_for_level(self, level: int) -> int:
        # total XP required to reach `level` from level 1: sum_{i=1}^{level-1} i*100
        if level <= 1:
            return 0
        return 100 * (level - 1) * level // 2

    def _boost_stat(self, mob: Mob, stat_name: str, amount: int) -> None:
        if amount <= 0:
            return
        mob.get_stat(stat_name).upgrade_base_value(amount)

    def _apply_tough_boss_stats(self, mob: Mob, floor: int, boss_rank: int) -> None:
        rank = max(1, boss_rank)
        self._boost_stat(mob, "HP", 10 + floor * 4 * rank)
        self._boost_stat(mob, "Endurance", 2 + floor * rank)
        self._boost_stat(mob, "Force", 2 + ((floor + 1) // 2) * rank)

    def _make_mob(self, floor: int, idx: int, is_boss: bool = False, boss_rank: int = 1) -> Mob:
        uid = f"mob_f{floor}_{idx}_{random.randint(0,99999)}"
        name = f"Coriace L{floor}#{idx}" if is_boss else f"Mob L{floor}#{idx}"
        mob = Character.create("Mob", user_id=uid, name=name)
        # Scale mob to floor level
        boss_level_bonus = 2 + (max(1, boss_rank) - 1) * 2
        target_level = floor + (boss_level_bonus if is_boss else 0)
        xp = self._xp_for_level(target_level)
        if xp > 0:
            mob.gain_exp(xp)
        if is_boss:
            mob.is_boss = True
            mob.is_tough = True
            mob.boss_rank = max(1, boss_rank)
            self._apply_tough_boss_stats(mob, floor, mob.boss_rank)
        return mob

    def _is_boss_floor(self, floor: int, boss_start_floor: int, boss_floor_interval: int) -> bool:
        if boss_floor_interval <= 0 or floor < boss_start_floor:
            return False
        return (floor - boss_start_floor) % boss_floor_interval == 0

    def run_tour(
        self,
        player: Character,
        start_floor: int = 1,
        max_floors: int = 3,
        enemies_before_boss_range: Tuple[int, int] = (5, 8),
        boss_start_floor: int = 1,
        boss_floor_interval: int = 1,
        special_boss_interval: int = 10,
    ) -> int:
        """Run tower progression for `player` until `max_floors` or death.

        Returns last reached floor (inclusive).
        """
        floor = start_floor
        while floor <= max_floors and player.is_alive():
            # determine how many enemies before boss this floor
            min_e, max_e = enemies_before_boss_range
            count = random.randint(min_e, max_e)

            # Spawn and fight sequential mobs
            for i in range(1, count + 1):
                mob = self._make_mob(floor, i, is_boss=False)
                fight = Fight(player, mob, name=f"Floor{floor}-m{i}")
                self.engine.run_fights([fight])
                if not player.is_alive():
                    return floor

            # Boss encounter
            if self._is_boss_floor(floor, boss_start_floor, boss_floor_interval):
                boss_rank = 2 if special_boss_interval > 0 and floor % special_boss_interval == 0 else 1
                boss = self._make_mob(floor, 0, is_boss=True, boss_rank=boss_rank)
                boss_fight = Fight(player, boss, name=f"Floor{floor}-Boss")
                self.engine.run_fights([boss_fight])
                if not player.is_alive():
                    return floor

            # Advance to next floor
            floor += 1

        return floor - 1 if not player.is_alive() else floor - 1 if floor > max_floors else floor
