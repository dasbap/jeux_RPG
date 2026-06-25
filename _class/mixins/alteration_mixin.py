"""
Alteration management mixin for Character class.

Handles buffs, debuffs, stuns, status effects, and damage over time.
"""

from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Tuple, Type

from jeuxRPG._class.res.character.alteration import alteration as alteration_file
from jeuxRPG._class.res.character.stats.stat import DefaultStat

if TYPE_CHECKING:
    from jeuxRPG._class.character import Character
    from jeuxRPG._class.skills.skillEffect import SkillEffect


class AlterationMixin:
    """
    Mixin providing alteration-related functionality.
    
    Handles:
    - Buffs and debuffs
    - Stun effects
    - Damage over time (DoT)
    - Invulnerability
    - Damage reduction
    - Status effect updates
    """
    
    def add_alteration(
        self: 'Character', 
        origin: 'Character', 
        skill_effect: 'SkillEffect'
    ) -> Tuple[bool, str, alteration_file.Alteration]:
        """
        Add an alteration (buff/debuff/...) to the character.
        
        Args:
            origin: Character who caused the alteration
            skill_effect: Effect to apply
            
        Returns:
            Tuple of (success, message, Alteration)
        """
        if skill_effect.alterationtype == alteration_file.AlterationType.BUFFSTAT:
            return self.buff_stat(
                origin, skill_effect.name, skill_effect.stat_target, 
                skill_effect.value, skill_effect.duration
            )
        elif skill_effect.alterationtype == alteration_file.AlterationType.DEBUFFSTAT:
            return self.debuff_stat(
                origin, skill_effect.name, skill_effect.stat_target, 
                skill_effect.value, skill_effect.duration
            )
        elif skill_effect.alterationtype == alteration_file.AlterationType.STUN:
            return self.add_stun(origin, skill_effect.name, skill_effect.duration)
        raise NotImplementedError("Unsupported alteration type")
    
    def add_stun(
        self: 'Character', 
        origin: 'Character', 
        stun_name: str, 
        duration: int
    ) -> Tuple[bool, str, Optional[alteration_file.Stun]]:
        """
        Apply a stun effect to this character.
        
        Args:
            origin: Character who caused the stun
            stun_name: Name of the stun effect
            duration: Duration in rounds
            
        Returns:
            Tuple of (success, message, Stun or None)
        """
        if duration <= 0:
            return False, f"Stun duration must be positive", None
            
        try:
            stun = alteration_file.Stun(stun_name, origin, duration, self)
            self.status["alteration"]["stun"].append(stun)
            plural = "s" if duration > 1 else ""
            return True, f"💫 {self.name} was stunned by {origin.name} for {duration} round{plural}!", stun
        except Exception as e:
            return False, f"Failed to apply stun: {e}", None
    
    def remove_stun(self: 'Character', stun: alteration_file.Stun) -> bool:
        """
        Remove a specific stun effect.
        
        Args:
            stun: The stun effect to remove
            
        Returns:
            True if removed, False if not found
        """
        stun_list = self.status["alteration"].get("stun", [])
        if stun in stun_list:
            stun_list.remove(stun)
            return True
        return False
    
    def clear_stuns(self: 'Character') -> int:
        """
        Remove all stun effects from this character.
        
        Returns:
            Number of stuns removed
        """
        stun_list = self.status["alteration"].get("stun", [])
        count = len(stun_list)
        stun_list.clear()
        return count
    
    def get_stuns(self: 'Character') -> List[alteration_file.Stun]:
        """
        Get all active stun effects.
        
        Returns:
            List of active Stun objects
        """
        return self.status["alteration"].get("stun", []).copy()
    
    def get_stun_duration(self: 'Character') -> int:
        """
        Get the remaining duration of the longest stun.
        
        Returns:
            Maximum remaining stun duration, or 0 if not stunned
        """
        stuns = self.get_stuns()
        if not stuns:
            return 0
        return max(stun.get_duration() for stun in stuns)
    
    def debuff_stat(
        self: 'Character', 
        origin: 'Character', 
        debuff_name: str, 
        stat_target: Type[DefaultStat], 
        value: int, 
        duration: int
    ) -> Tuple[bool, str, alteration_file.DeBuff]:
        """
        Apply a debuff to a character stat.
        
        Args:
            origin: Character who caused the debuff
            debuff_name: Name of the debuff
            stat_target: Type of stat to debuff
            value: Amount to decrease the stat
            duration: Duration in rounds
            
        Returns:
            Tuple of (success, message, DeBuff or None)
        """
        try:
            stat = self.get_stat(stat_target.__name__)
            debuff = alteration_file.DeBuff(debuff_name, origin, value, duration, self, stat_target)
            stat.add_debuff(debuff)
            self.status["alteration"]["debuff"].append(debuff)
            return True, f"{self.name} was debuffed with {debuff_name}, the stat {stat_target.__name__} gets -{value} for {duration} rounds", debuff
        except Exception as e:
            return False, f"Error in debuff_stat: {e}", None

    def buff_stat(
        self: 'Character', 
        origin: 'Character', 
        buff_name: str, 
        stat_target: Type[DefaultStat], 
        value: int, 
        duration: int
    ) -> Tuple[bool, str, alteration_file.Buff]:
        """
        Apply a buff to a character stat.
        
        Args:
            origin: Character who caused the buff
            buff_name: Name of the buff
            stat_target: Type of stat to buff
            value: Amount to increase the stat
            duration: Duration in rounds
            
        Returns:
            Tuple of (success, message, Buff or None)
        """
        try:
            stat = self.get_stat(stat_target.__name__)
            buff = alteration_file.Buff(buff_name, origin, value, duration, self, stat_target)
            stat.add_buff(buff)
            self.status["alteration"]["buff"].append(buff)
            return True, f"{self.name} was buffed with {buff_name}, the stat {stat_target.__name__} gets +{value} for {duration} rounds", buff
        except Exception as e:
            return False, f"Error in buff_stat: {e}", None
    
    def is_stun(self: 'Character') -> bool:
        """
        Check if character is currently stunned.
        
        Returns:
            True if character has at least one active stun effect
        """
        stuns = self.status["alteration"].get("stun", [])
        # Filter out expired stuns
        active_stuns = [s for s in stuns if not s.is_over()]
        return len(active_stuns) > 0
    
    def is_stunned(self: 'Character') -> bool:
        """Alias for is_stun() for better readability."""
        return self.is_stun()
    
    def will_be_hit(self: 'Character') -> bool:
        """Check if character has incoming damage effects."""
        return bool(self.status["alteration"]["Damage"].get("Incoming", []))
    
    def is_invulnerable(self: 'Character') -> bool:
        """Check if character is invulnerable."""
        return bool(self.status["alteration"].get("invulnerability", []))
    
    def have_reduction(self: 'Character') -> bool:
        """Check if character has any damage reduction effects."""
        r = self.status["alteration"]["Damage"].get("Reduction", {"-": [], "+": [], "%": []})
        return any(r["-"]) or any(r["+"]) or any(r["%"])
    
    def check_state(self: 'Character') -> List[Tuple[str, bool]]:
        """
        Check all character status conditions.
        
        Returns:
            List of tuples (condition_name, is_active)
        """
        return [
            ("death", self._check_death()),
            ("stun", self.is_stun()),
            ("dot", self.will_be_hit()),
            ("invulnerability", self.is_invulnerable()),
            ("reduction", self.have_reduction())
        ]
    
    def _update_status(self: 'Character') -> List[Tuple[str, alteration_file.Alteration]]:
        """
        Update all status effects at end of round.
        
        Returns:
            List of (message, alteration) for expired effects
        """
        stats_dict: Dict[str, DefaultStat] = self.status["stats"]
        for stat in stats_dict.values():
            if isinstance(stat, DefaultStat):
                stat.end_round()
        
        # Update and remove expired alterations
        alterations_dict = self.status["alteration"]
        alteration_remove: List[Tuple[str, alteration_file.Alteration]] = []
        
        for alterations_type in ["stun", "invulnerability"]:
            alterations_type: Literal["stun", "invulnerability"]
            alterations = alterations_dict[alterations_type]
            for a in alterations:
                a.decrease()
                if a.is_over():
                    alterations.remove(a)
                    alteration_remove.append((f"{self.name} is not longuer affected by {a.name}", a))

        dot_list = alterations_dict["Damage"]["Incoming"]
        dot_list: List[alteration_file.Dot]
        for dot in dot_list:
            if not isinstance(dot, alteration_file.Dot):
                raise TypeError("a dot is not a Dot")
            self.lose_hp(dot.get_caster(), dot.value)
            dot.decrease()
        
        reduction = alterations_dict["Damage"]["Reduction"]
        for type_key in reduction:
            for res in reduction[type_key]:
                res.decrease()
                if res.is_over():
                    reduction[type_key].remove(res)
                    alteration_remove.append((f"{self.name} is not longuer affected by {res.name}", res))
        
        alteration_remove = [("", None)] if alteration_remove == [] else alteration_remove
        
        return alteration_remove
