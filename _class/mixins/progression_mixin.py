"""
Progression management mixin for Character class.

Handles experience, leveling up, and stat upgrades.
"""

from collections import defaultdict
from copy import deepcopy
from typing import TYPE_CHECKING, Dict

from jeuxRPG.i18n import t
from jeuxRPG._class.res.character.stats.basic_stat import (
    HP, Endurance, Force, Intelligence, Sagesse
)

if TYPE_CHECKING:
    from jeuxRPG._class.character import Character


class ProgressionMixin:
    """
    Mixin providing progression-related functionality.
    
    Handles:
    - Experience gain
    - Level up mechanics
    - Stat upgrades on level up
    - XP drop on death
    """
    
    def drop_xp(self: 'Character', killer: 'Character') -> str:
        """
        Handle XP drop when character is defeated.
        
        Args:
            killer: Character who defeated this character
            
        Returns:
            Result message string
        """
        get_xp_reward = getattr(self, "get_xp_reward", None)
        xp_given = get_xp_reward() if callable(get_xp_reward) else self.level * 50 + self.exp
        killer.gain_exp(xp_given)
        self.exp = 0
        self.level = max(1, self.level - 5)
        return t("progression.defeated_xp", killer=killer.name, amount=xp_given, defeated=self.name)

    def gain_exp(self: 'Character', amount: int) -> str:
        """
        Gain experience points, potentially leveling up multiple times.
        
        Args:
            amount: Amount of XP to gain
            
        Returns:
            Result message string
            
        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("XP must be positive")

        self.exp += amount
        messages = [t("progression.gained_xp", name=self.name, amount=amount)]

        # Level up repeatedly while XP is sufficient
        while self.can_level_up():
            level_msg = self.level_up()
            if level_msg:
                messages.append(level_msg)

        return " ".join(messages)
    
    def can_level_up(self: 'Character') -> bool:
        """Check if character has enough XP to level up."""
        return self.exp >= self._required_exp_for_next_level()

    def _required_exp_for_next_level(self: 'Character') -> int:
        """Calculate XP needed for next level."""
        return self.level * 100

    def level_up(self: 'Character') -> str:
        """
        Récursivement augmente le niveau du personnage si assez d'XP.
        Cumule les bonus dans self.tmp.
        Retourne un message final unique.
        """
        if not hasattr(self, "tmp"):
            self.tmp = {
                "start_level": self.level,
                "stats": defaultdict(int),
                "energies": defaultdict(int),
                "new_energies": []
            }

        if not self.can_level_up():
            if self.level == self.tmp["start_level"]:
                needed_xp = self._required_exp_for_next_level() - self.exp
                return t("progression.need_more_xp", name=self.name, amount=needed_xp)

            # Construction du message final unique
            final_msg = [t("progression.level_up", name=self.name, from_level=self.tmp['start_level'], to_level=self.level)]

            for stat, value in self.tmp["stats"].items():
                final_msg.append(t("progression.stat_up", stat_name=stat, value=value))
            for energy, value in self.tmp["energies"].items():
                final_msg.append(t("progression.energy_up", energy_name=energy, value=value))
            for energy_type in self.tmp["new_energies"]:
                final_msg.append(t("progression.new_energy", energy_type=energy_type))

            del self.tmp
            return "\n".join(final_msg)

        self.exp -= self._required_exp_for_next_level()
        self.level += 1
        
        for level_skills_dict in self.class_skills_dict.keys():
            if level_skills_dict == "level " + str(self.level):
                self.skills.update(deepcopy(self.class_skills_dict[level_skills_dict]))
        
        upgrades: Dict[int, Dict] = self.class_table["upgrade_stats"]
        for threshold in sorted(upgrades.keys()):
            if self.level < threshold:
                continue
            upgrade_data = upgrades[threshold]

            for stat_type, value in upgrade_data.items():
                if stat_type in (HP, Force, Endurance, Intelligence, Sagesse):
                    stat = self.get_stat(stat_type.__name__)
                    stat.upgrade_base_value(value)
                    self.tmp["stats"][stat_type.__name__] += value

            if "Energie" in upgrade_data:
                for energy_type, value in upgrade_data["Energie"].items():
                    energy = self.get_energie(energy_type)
                    energy.upgrade_base_value(value)
                    self.tmp["energies"][energy_type.__name__] += value

            if "new" in upgrade_data and "Energie" in upgrade_data["new"]:
                for energy_type, base_value in upgrade_data["new"]["Energie"].items():
                    self.add_energie(energy_type(base_value))
                    self.tmp["new_energies"].append(energy_type.__name__)
                upgrade_data.pop("new")

        return self.level_up()
