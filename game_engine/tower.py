import random
from typing import Callable, Iterable, Tuple

from jeuxRPG.game_engine.engine import GameEngine
from jeuxRPG._class.character import Character
from jeuxRPG._class.mob.mob import Mob
from jeuxRPG._class._event.confrontation.encounter.fight import Fight


TOWER_DIFFICULTIES = {
    "easy": {
        "level_multiplier": 0.5,
        "boss_stat_multiplier": 0.5,
        "xp_reward_multiplier": 1.15,
        "floor_heal_ratio": 0.5,
    },
    "normal": {
        "level_multiplier": 1.0,
        "boss_stat_multiplier": 1.0,
        "xp_reward_multiplier": 1.0,
        "floor_heal_ratio": 0.25,
    },
    "hard": {
        "level_multiplier": 1.35,
        "boss_stat_multiplier": 1.4,
        "xp_reward_multiplier": 1.0,
        "floor_heal_ratio": 0.0,
    },
}

TOWER_DIFFICULTY_ALIASES = {
    "facile": "easy",
    "easy": "easy",
    "normal": "normal",
    "standard": "normal",
    "difficile": "hard",
    "dur": "hard",
    "hard": "hard",
}


def normalize_tower_difficulty(value: str | None) -> str:
    key = str(value or "normal").strip().lower()
    return TOWER_DIFFICULTY_ALIASES.get(key, "normal")


class TowerRun:
    """Runs a tower-style progression where a player faces waves of mobs per floor.

    Behavior:
    - Each floor spawns N mobs (N random between `enemies_before_boss_range`).
    - Boss floors spawn a tough mob after the regular encounters, every 5 floors by default.
    - Every `special_boss_interval` boss floors spawn a stronger tough mob.
    - Mobs are scaled to the floor by granting XP to reach target level.
    - Tower mobs inherit reduced mob XP rewards and may apply tower-specific reward tuning.
    """

    def __init__(self, engine: GameEngine):
        self.engine = engine

    def _party_members(self, player: Character | Iterable[Character]) -> list[Character]:
        if isinstance(player, Character):
            return [player]
        return list(player)

    def _party_is_alive(self, party: list[Character]) -> bool:
        return any(member.is_alive() for member in party)

    def _xp_for_level(self, level: int) -> int:
        # total XP required to reach `level` from level 1: sum_{i=1}^{level-1} i*100
        if level <= 1:
            return 0
        return 100 * (level - 1) * level // 2

    def _boost_stat(self, mob: Mob, stat_name: str, amount: int) -> None:
        if amount <= 0:
            return
        mob.get_stat(stat_name).upgrade_base_value(amount)

    def _difficulty_multiplier(self, difficulty: str, setting: str) -> float:
        normalized = normalize_tower_difficulty(difficulty)
        return float(TOWER_DIFFICULTIES[normalized][setting])

    def _apply_tower_xp_reward(self, mob: Mob, difficulty: str) -> None:
        multiplier = self._difficulty_multiplier(difficulty, "xp_reward_multiplier")
        reward = max(1, round(mob.get_xp_reward() * multiplier))
        mob.get_xp_reward = lambda reward=reward: reward

    def rest_party_after_floor(self, party: Iterable[Character], difficulty: str) -> None:
        heal_ratio = self._difficulty_multiplier(difficulty, "floor_heal_ratio")
        if heal_ratio <= 0:
            return
        for member in party:
            if not member.is_alive():
                continue
            heal_amount = max(1, round(member.hp.value * heal_ratio))
            member.gain_hp(heal_amount)

    def _apply_tough_boss_stats(
        self,
        mob: Mob,
        floor: int,
        boss_rank: int,
        difficulty: str = "normal",
    ) -> None:
        rank = max(1, boss_rank)
        multiplier = self._difficulty_multiplier(difficulty, "boss_stat_multiplier")
        self._boost_stat(mob, "HP", round((10 + floor * 4 * rank) * multiplier))
        self._boost_stat(mob, "Endurance", round((2 + floor * rank) * multiplier))
        self._boost_stat(mob, "Force", round((2 + ((floor + 1) // 2) * rank) * multiplier))

    def _make_mob(
        self,
        floor: int,
        idx: int,
        is_boss: bool = False,
        boss_rank: int = 1,
        difficulty: str = "normal",
    ) -> Mob:
        difficulty = normalize_tower_difficulty(difficulty)
        uid = f"mob_f{floor}_{idx}_{random.randint(0,99999)}"
        name = f"Coriace L{floor}#{idx}" if is_boss else f"Mob L{floor}#{idx}"
        mob = Character.create("Mob", user_id=uid, name=name)
        # Scale mob to floor level and selected tower difficulty.
        boss_level_bonus = 2 + (max(1, boss_rank) - 1) * 2
        level_floor = max(1, round(floor * self._difficulty_multiplier(difficulty, "level_multiplier")))
        target_level = level_floor + (boss_level_bonus if is_boss else 0)
        xp = self._xp_for_level(target_level)
        if xp > 0:
            mob.gain_exp(xp)
        if is_boss:
            mob.is_boss = True
            mob.is_tough = True
            mob.boss_rank = max(1, boss_rank)
            self._apply_tough_boss_stats(mob, floor, mob.boss_rank, difficulty)
        self._apply_tower_xp_reward(mob, difficulty)
        return mob

    def _is_boss_floor(self, floor: int, boss_start_floor: int, boss_floor_interval: int) -> bool:
        if boss_floor_interval <= 0 or floor < boss_start_floor:
            return False
        return (floor - boss_start_floor) % boss_floor_interval == 0

    def run_tour(
        self,
        player: Character | Iterable[Character],
        start_floor: int = 1,
        max_floors: int = 3,
        enemies_before_boss_range: Tuple[int, int] = (5, 8),
        boss_start_floor: int = 5,
        boss_floor_interval: int = 5,
        special_boss_interval: int = 10,
        difficulty: str = "normal",
        on_floor_cleared: Callable[[int], None] | None = None,
    ) -> int:
        """Run tower progression for `player` until `max_floors` or death.

        Returns last reached floor (inclusive).
        """
        party = self._party_members(player)
        if not party:
            return max(0, int(start_floor) - 1)

        difficulty = normalize_tower_difficulty(difficulty)
        floor = max(1, int(start_floor))
        max_floors = int(max_floors)
        while floor <= max_floors and self._party_is_alive(party):
            # determine how many enemies before boss this floor
            min_e, max_e = enemies_before_boss_range
            count = random.randint(min_e, max_e)

            # Spawn and fight sequential mobs
            for i in range(1, count + 1):
                mob = self._make_mob(floor, i, is_boss=False, difficulty=difficulty)
                fight = Fight(party, mob, name=f"Floor{floor}-m{i}")
                self.engine.run_fights([fight])
                if not self._party_is_alive(party):
                    return floor

            # Boss encounter
            if self._is_boss_floor(floor, boss_start_floor, boss_floor_interval):
                boss_rank = 2 if special_boss_interval > 0 and floor % special_boss_interval == 0 else 1
                boss = self._make_mob(floor, 0, is_boss=True, boss_rank=boss_rank, difficulty=difficulty)
                boss_fight = Fight(party, boss, name=f"Floor{floor}-Boss")
                self.engine.run_fights([boss_fight])
                if not self._party_is_alive(party):
                    return floor

            if on_floor_cleared is not None:
                on_floor_cleared(floor)

            self.rest_party_after_floor(party, difficulty)

            # Advance to next floor
            floor += 1

        return floor - 1
