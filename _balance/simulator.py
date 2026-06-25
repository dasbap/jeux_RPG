from __future__ import annotations

import json
import random
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple, Iterable

from jeuxRPG._class._event.confrontation.encounter.fight import Fight
from jeuxRPG._class.character import Character
from jeuxRPG._class.sub_character import __all__ as CLASS_NAMES
from jeuxRPG._class.res.classType import SkillType


@dataclass
class SideStats:
    wins: int = 0
    rounds: int = 0
    damage_dealt: int = 0
    hp_lost: int = 0
    energy_spent: Dict[str, int] = field(default_factory=dict)
    skill_usage: Dict[str, int] = field(default_factory=dict)


@dataclass
class DuelStats:
    class_a: str = ""
    class_b: str = ""
    fights: int = 0
    draws: int = 0
    side_a: SideStats = field(default_factory=SideStats)
    side_b: SideStats = field(default_factory=SideStats)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_a": self.class_a,
            "class_b": self.class_b,
            "fights": self.fights,
            "draws": self.draws,
            "side_a": {
                "wins": self.side_a.wins,
                "rounds": self.side_a.rounds,
                "damage_dealt": self.side_a.damage_dealt,
                "hp_lost": self.side_a.hp_lost,
                "energy_spent": self.side_a.energy_spent,
                "skill_usage": self.side_a.skill_usage,
            },
            "side_b": {
                "wins": self.side_b.wins,
                "rounds": self.side_b.rounds,
                "damage_dealt": self.side_b.damage_dealt,
                "hp_lost": self.side_b.hp_lost,
                "energy_spent": self.side_b.energy_spent,
                "skill_usage": self.side_b.skill_usage,
            },
        }


class _ActionTracker:
    """Monkey-patch Character methods to track energy spend and damage."""

    def __init__(self) -> None:
        self.side_by_obj: Dict[Character, str] = {}
        self.energy_spent: Dict[str, Dict[str, int]] = {"A": {}, "B": {}}
        self.skill_usage: Dict[str, Dict[str, int]] = {"A": {}, "B": {}}
        self.damage_dealt: Dict[str, int] = {"A": 0, "B": 0}
        self.hp_lost: Dict[str, int] = {"A": 0, "B": 0}
        self._orig_use_skill = None
        self._orig_lose_hp = None

    def set_sides(self, a: Character, b: Character) -> None:
        self.side_by_obj = {a: "A", b: "B"}

    def _wrap_use_skill(self):
        orig = Character.use_skill
        tracker = self

        def wrapped(obj: Character, skill_name: str, target: Character | None = None):
            # Pre-read for energy target and cost
            try:
                skill = obj.get_skill(skill_name)
                energie_cost = getattr(skill, "energie_cost", 0) or 0
                energie_target = getattr(skill, "energie_target", None)
                energie_name = getattr(energie_target, "__name__", "?") if energie_target else "?"
            except Exception:
                energie_cost, energie_name = 0, "?"

            ok, msg = orig(obj, skill_name, target)
            if ok:
                side = tracker.side_by_obj.get(obj)
                if side:
                    tracker.energy_spent[side][energie_name] = tracker.energy_spent[side].get(energie_name, 0) + int(energie_cost)
                    tracker.skill_usage[side][skill_name] = tracker.skill_usage[side].get(skill_name, 0) + 1
            return ok, msg

        return wrapped

    def _wrap_lose_hp(self):
        orig = Character.lose_hp

        tracker = self

        def wrapped(obj: Character, source: Character, amount: int) -> str:
            hp_before = obj.get_stat("HP").current_value
            msg = orig(obj, source, amount)
            hp_after = obj.get_stat("HP").current_value
            delta = max(0, hp_before - hp_after)
            side_self = tracker.side_by_obj.get(obj)
            side_src = tracker.side_by_obj.get(source)
            if side_src:
                tracker.damage_dealt[side_src] += delta
            if side_self:
                tracker.hp_lost[side_self] += delta
            return msg

        return wrapped

    def __enter__(self):
        self._orig_use_skill = Character.use_skill
        self._orig_lose_hp = Character.lose_hp
        Character.use_skill = self._wrap_use_skill()
        Character.lose_hp = self._wrap_lose_hp()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._orig_use_skill:
            Character.use_skill = self._orig_use_skill
        if self._orig_lose_hp:
            Character.lose_hp = self._orig_lose_hp


def simulate_duel(class_a: str, class_b: str, matches: int = 25, seed: int | None = None, max_rounds: int = 100) -> DuelStats:
    if seed is not None:
        random.seed(seed)

    stats = DuelStats(class_a, class_b)
    for i in range(matches):
        a = Character.create(class_a, user_id=f"A{i}", name=f"{class_a}_A{i}")
        b = Character.create(class_b, user_id=f"B{i}", name=f"{class_b}_B{i}")
        f = Fight(a, b, name=f"{class_a} vs {class_b} #{i}")

        with _ActionTracker() as t:
            t.set_sides(a, b)
            rounds = 0
            while a.is_alive() and b.is_alive() and rounds < max_rounds:
                f.start_round(rest=True)
                rounds += 1

            stats.fights += 1
            stats.side_a.rounds += rounds
            stats.side_b.rounds += rounds
            # Winner
            if a.is_alive() and not b.is_alive():
                stats.side_a.wins += 1
            elif b.is_alive() and not a.is_alive():
                stats.side_b.wins += 1
            else:
                stats.draws += 1

            # Aggregate tracked metrics
            for k, v in t.energy_spent["A"].items():
                stats.side_a.energy_spent[k] = stats.side_a.energy_spent.get(k, 0) + v
            for k, v in t.energy_spent["B"].items():
                stats.side_b.energy_spent[k] = stats.side_b.energy_spent.get(k, 0) + v
            for k, v in t.skill_usage["A"].items():
                stats.side_a.skill_usage[k] = stats.side_a.skill_usage.get(k, 0) + v
            for k, v in t.skill_usage["B"].items():
                stats.side_b.skill_usage[k] = stats.side_b.skill_usage.get(k, 0) + v
            stats.side_a.damage_dealt += t.damage_dealt["A"]
            stats.side_b.damage_dealt += t.damage_dealt["B"]
            stats.side_a.hp_lost += t.hp_lost["A"]
            stats.side_b.hp_lost += t.hp_lost["B"]

    return stats


def simulate_matrix(class_names: List[str] | None = None, matches_per_pair: int = 25, seed: int | None = 42) -> Dict[str, Any]:
    classes = class_names or list(CLASS_NAMES)
    results: Dict[str, Any] = {"pairs": [], "summary": {}}

    per_class = {c: {"wins": 0, "losses": 0, "draws": 0, "damage_dealt": 0, "energy_spent": {}, "rounds": 0} for c in classes}

    for ca in classes:
        for cb in classes:
            if ca == cb:
                continue
            duel = simulate_duel(ca, cb, matches=matches_per_pair, seed=seed)
            results["pairs"].append(duel.to_dict())

            # Aggregate per-class (A perspective)
            A = per_class[ca]
            B = per_class[cb]
            A["wins"] += duel.side_a.wins
            A["losses"] += duel.side_b.wins
            A["draws"] += duel.draws
            B["wins"] += duel.side_b.wins
            B["losses"] += duel.side_a.wins
            B["draws"] += duel.draws
            A["damage_dealt"] += duel.side_a.damage_dealt
            B["damage_dealt"] += duel.side_b.damage_dealt
            A["rounds"] += duel.side_a.rounds
            B["rounds"] += duel.side_b.rounds
            for k, v in duel.side_a.energy_spent.items():
                A["energy_spent"][k] = A["energy_spent"].get(k, 0) + v
            for k, v in duel.side_b.energy_spent.items():
                B["energy_spent"][k] = B["energy_spent"].get(k, 0) + v

    # Build summary with efficiency indicators
    summary: Dict[str, Any] = {}
    for cls, agg in per_class.items():
        total = agg["wins"] + agg["losses"] + agg["draws"]
        win_rate = (agg["wins"] / total) if total else 0.0
        # damage per energy (sum energies)
        energy_total = sum(agg["energy_spent"].values()) or 1
        dmg_per_energy = agg["damage_dealt"] / energy_total
        rounds_avg = (agg["rounds"] / total) if total else 0.0
        summary[cls] = {
            "total_matches": total,
            "wins": agg["wins"],
            "losses": agg["losses"],
            "draws": agg["draws"],
            "win_rate": win_rate,
            "damage_per_energy": dmg_per_energy,
            "avg_rounds": rounds_avg,
            "energy_spent": agg["energy_spent"],
        }

    results["summary"] = summary
    return results


def analyze_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Produce balancing hints based on simple thresholds."""
    hints: List[str] = []
    # Thresholds (tweakable)
    WINRATE_HIGH = 0.60
    WINRATE_LOW = 0.40
    DMG_PER_ENERGY_HIGH = 2.0  # arbitrary baseline

    for cls, s in summary.items():
        wr = s.get("win_rate", 0.0)
        dpe = s.get("damage_per_energy", 0.0)
        if wr > WINRATE_HIGH:
            hints.append(f"{cls}: win_rate {wr:.0%} is high → consider nerfing damage or increasing costs")
        elif wr < WINRATE_LOW:
            hints.append(f"{cls}: win_rate {wr:.0%} is low → consider buffing survivability or damage")
        if dpe > DMG_PER_ENERGY_HIGH:
            hints.append(f"{cls}: damage/energy {dpe:.2f} is high → increase energy cost or reduce damage")

    return {"hints": hints}


def write_report(report: Dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


def run_matrix_to_file(matches_per_pair: int = 10, out_path: str | Path = ".data/balance/report.json") -> Path:
    res = simulate_matrix(matches_per_pair=matches_per_pair)
    hints = analyze_summary(res["summary"])
    res["analysis"] = hints
    out = Path(out_path)
    write_report(res, out)
    return out


# ------------------------- Advanced modes -----------------------------------

class _ForceSkill:
    """Force characters in `forced_objs` to use `skill_name` when attacking."""

    def __init__(self, skill_name: str, forced_objs: Iterable[Character]):
        self.skill_name = skill_name
        self.forced_objs = set(forced_objs)
        self._orig_attack = None

    def _wrap_attack(self):
        orig = Character.attack
        forced_set = set(self.forced_objs)
        forced_skill = self.skill_name

        def wrapped(obj: Character, target: Character, skill_name: str | None = None):
            if obj in forced_set:
                try:
                    _ = obj.get_skill(forced_skill)
                    return obj.use_skill(forced_skill, target)
                except Exception:
                    pass
            return orig(obj, target, skill_name)

        return wrapped

    def __enter__(self):
        self._orig_attack = Character.attack
        Character.attack = self._wrap_attack()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._orig_attack:
            Character.attack = self._orig_attack


def _set_advantage_for_mode(defender: Character, damage_type: Any, mode: str) -> None:
    mode = (mode or "neutral").lower()
    if mode == "neutral":
        defender.class_table["advantage"] = {"weakness": [], "resilience": []}
    elif mode == "weak":
        defender.class_table["advantage"] = {"weakness": [damage_type], "resilience": []}
    elif mode in {"resist", "resilience"}:
        defender.class_table["advantage"] = {"weakness": [], "resilience": [damage_type]}


def simulate_skill_duel(
    class_a: str,
    class_b: str,
    skill_name: str | None,
    matches: int = 25,
    seed: int | None = None,
    max_rounds: int = 100,
    force_side: str = "none",
    advantage_mode: str = "neutral",  # neutral | weak | resist | all
) -> Dict[str, Any]:
    modes = [advantage_mode]
    if advantage_mode.lower() == "all":
        modes = ["neutral", "weak", "resist"]

    out: Dict[str, Any] = {"class_a": class_a, "class_b": class_b, "skill": skill_name, "modes": {}}
    for mode in modes:
        if seed is not None:
            random.seed(seed)
        duel_stats = DuelStats(class_a, class_b)
        for i in range(matches):
            a = Character.create(class_a, user_id=f"A{i}", name=f"{class_a}_A{i}")
            b = Character.create(class_b, user_id=f"B{i}", name=f"{class_b}_B{i}")

            # Reset both sides' inherent class advantages to neutral for controlled tests
            try:
                a.class_table["advantage"] = {"weakness": [], "resilience": []}
                b.class_table["advantage"] = {"weakness": [], "resilience": []}
            except Exception:
                pass

            # Determine damage type for advantage setup
            dmg_type = None
            if skill_name:
                try:
                    sk = a.get_skill(skill_name)
                    # Skill stores damage type as `DamageType` (capital D)
                    dmg_type = getattr(sk, "DamageType", None)
                except Exception:
                    dmg_type = None
            else:
                # Infer the natural attack damage type from the first usable damage skill
                try:
                    for sk in reversed(list(a.get_available_skills().values())):
                        if getattr(sk, "skill_type", None) == SkillType.DAMAGE:
                            dmg_type = getattr(sk, "DamageType", None)
                            if dmg_type is not None:
                                break
                except Exception:
                    dmg_type = None

            # Apply requested advantage mode (impact on defender against the forced skill)
            if dmg_type is not None:
                _set_advantage_for_mode(b, dmg_type, mode)

            fs = (force_side or "NONE").strip().upper()
            force_skill = fs not in {"NONE", "NO", "OFF"}
            if fs in {"A", "LEFT"}:
                forced_objs = {a}
            elif fs in {"B", "RIGHT"}:
                forced_objs = {b}
            elif fs in {"BOTH", "ALL"}:
                forced_objs = {a, b}
            else:
                forced_objs = {a}

            skill_ctx = _ForceSkill(skill_name, forced_objs) if (force_skill and skill_name) else nullcontext()
            with _ActionTracker() as t, skill_ctx:
                t.set_sides(a, b)
                label = f" (skill {skill_name})" if skill_name else ""
                f = Fight(a, b, name=f"{class_a} vs {class_b}{label}")
                rounds = 0
                while a.is_alive() and b.is_alive() and rounds < max_rounds:
                    f.start_round(rest=True)
                    rounds += 1

                duel_stats.fights += 1
                duel_stats.side_a.rounds += rounds
                duel_stats.side_b.rounds += rounds
                if a.is_alive() and not b.is_alive():
                    duel_stats.side_a.wins += 1
                elif b.is_alive() and not a.is_alive():
                    duel_stats.side_b.wins += 1
                else:
                    duel_stats.draws += 1

                for k, v in t.energy_spent["A"].items():
                    duel_stats.side_a.energy_spent[k] = duel_stats.side_a.energy_spent.get(k, 0) + v
                for k, v in t.energy_spent["B"].items():
                    duel_stats.side_b.energy_spent[k] = duel_stats.side_b.energy_spent.get(k, 0) + v
                for k, v in t.skill_usage["A"].items():
                    duel_stats.side_a.skill_usage[k] = duel_stats.side_a.skill_usage.get(k, 0) + v
                for k, v in t.skill_usage["B"].items():
                    duel_stats.side_b.skill_usage[k] = duel_stats.side_b.skill_usage.get(k, 0) + v
                duel_stats.side_a.damage_dealt += t.damage_dealt["A"]
                duel_stats.side_b.damage_dealt += t.damage_dealt["B"]
                duel_stats.side_a.hp_lost += t.hp_lost["A"]
                duel_stats.side_b.hp_lost += t.hp_lost["B"]

        out["modes"][mode] = duel_stats.to_dict()
    return out


def simulate_one_vs_all(class_name: str, matches: int = 25, seed: int | None = 42) -> Dict[str, Any]:
    classes = [c for c in CLASS_NAMES if c != class_name]
    results: Dict[str, Any] = {"class": class_name, "vs": []}
    for other in classes:
        results["vs"].append(simulate_duel(class_name, other, matches=matches, seed=seed).to_dict())
    return results
