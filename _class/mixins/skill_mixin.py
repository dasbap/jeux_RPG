"""
Skill management mixin for Character class.

Handles skill acquisition, usage, and availability.
"""

from typing import TYPE_CHECKING, Dict, Optional, Tuple

from jeuxRPG._class.res.classType import SkillType
from jeuxRPG._class.skills.skill import Skill

if TYPE_CHECKING:
    from jeuxRPG._class.character import Character


class SkillMixin:
    """
    Mixin providing skill-related functionality.
    
    Handles:
    - Skill retrieval
    - Skill usage with validation
    - Available skills listing
    """
    
    def get_skill(self: 'Character', skill_name: str) -> Skill:
        """
        Get skill by name.
        
        Args:
            skill_name: Name of skill to retrieve
            
        Returns:
            Requested Skill object
            
        Raises:
            KeyError: If skill doesn't exist
        """
        if skill := self.skills.get(skill_name):
            return skill
        raise KeyError(f"Skill '{skill_name}' not found for {self.name}")

    def use_skill(
        self: 'Character', 
        skill_name: str, 
        target: Optional['Character'] = None
    ) -> Tuple[bool, str]:
        """
        Attempt to use a skill, with comprehensive checks and execution.
        
        Args:
            skill_name: Name of skill to use
            target: Optional target character (default: None)
            
        Returns:
            Tuple of (success, message) where:
            - success: Boolean indicating if skill was used
            - message: String describing result
            
        The method performs the following checks in order:
        1. Skill existence
        2. Energy requirements
        3. Cooldown status
        4. Target validity (if required)
        5. Skill execution
        """
        try:
            # Get the skill instance
            skill = self.get_skill(skill_name)
            
            # Check energy requirements
            if not self.has_required_energie(skill):
                return False, f"Not enough energy to use {skill_name}"
                
            # Check cooldown status
            if not skill.is_ready():
                remaining = skill.cooldown - skill.current_cooldown
                return False, f"{skill.name} is on cooldown ({remaining} rounds remaining)"
            
            # Validate target if skill requires one
            if skill.requires_target and target is None:
                return False, f"{skill.name} requires a target"
                
            # Check if target is valid (alive and not self for harmful skills)
            if target is not None:
                if not target.is_alive():
                    return False, f"Cannot target defeated {target.name}"
                if skill.skill_type == SkillType.DAMAGE and target is self:
                    return False, "Cannot damage yourself"
                if skill.skill_type == SkillType.HEAL and target is not self and not skill.can_target_others:
                    return False, f"{skill.name} can only target self"

            # Execute the skill
            result = skill.execute(self, target)
            return result["success"], result["message"]
        except KeyError:
            return False, f"Unknown skill: {skill_name}"
        except Exception as e:
            return False, f"Skill failed: {str(e)}"

    def get_available_skills(self: 'Character') -> Dict[str, Skill]:
        """Get dictionary of all available skills."""
        return self.skills.copy()
    
    def rest(self: 'Character') -> str:
        """Restore energy and reduce skill cooldowns."""
        # Regenerate energy
        for energie in self.energie:
            energie.regenerate()
        
        # Reduce skill cooldowns
        for skill in self.skills.values():
            skill.update_cooldown()
        return ""
