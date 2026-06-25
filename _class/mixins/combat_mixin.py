"""
Combat management mixin for Character class.

Handles attack, heal actions, and combat flow.
"""

from typing import TYPE_CHECKING, Optional, Tuple

from jeuxRPG.i18n import t
from jeuxRPG._class.res.classType import SkillType

if TYPE_CHECKING:
    from jeuxRPG._class.character import Character


class CombatMixin:
    """
    Mixin providing combat-related functionality.
    
    Handles:
    - Attack actions
    - Heal actions
    - Combat flow management
    """
    
    def attack(
        self: 'Character', 
        target: 'Character', 
        skill_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Perform an attack action against target.
        
        Args:
            target: Character to attack
            skill_name: Optional specific skill to use
            
        Returns:
            Tuple of (success, message)
        """
        success = False
        message = t("combat.no_attack_skill")
        
        if skill_name:
            success, message = self.use_skill(skill_name, target)
        else:
            for skill in reversed(self.get_available_skills().values()):
                if skill.skill_type != SkillType.DAMAGE:
                    continue
                success, message = self.use_skill(skill.name, target)
                if success:
                    break
        
        updates = self._update_status()
        if isinstance(updates, list) and updates:
            extra_msgs = [m for m, _ in updates if m]
            if extra_msgs:
                message = f"{message}  {' '.join(extra_msgs)}"
        return success, message

    def heal(
        self: 'Character', 
        target: 'Character', 
        skill_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Perform a heal action on target.
        
        Args:
            target: Character to heal
            skill_name: Optional specific skill to use
            
        Returns:
            Tuple of (success, message)
        """
        if target.hp.current_value == target.hp.value:
            return False, t("combat.target_full_hp", name=target.name)
            
        success = False
        message = t("combat.no_heal_skill")
        
        if skill_name:
            success, message = self.use_skill(skill_name, target)
        else:
            # Try to use most powerful available heal skill
            for skill in reversed(self.get_available_skills().values()):
                if skill.skill_type != SkillType.HEAL:
                    continue
                success, message = self.use_skill(skill.name, target)
                if success:
                    break
                    
        return success, message
