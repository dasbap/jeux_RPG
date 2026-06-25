"""
Mob module for enemy characters in the RPG system.

Provides the Mob class for creating enemy characters with
customizable XP drops and level scaling.
"""

from jeuxRPG._class.character import Character
from jeuxRPG._class.res.character.table_stat_subclass import mob_table


class Mob(Character):
    """
    Enemy character class with XP drop mechanics.
    
    Mobs are non-playable characters that players can fight.
    They can be initialized with XP to set their starting level.
    
    Attributes:
        class_skills_dict: Skills available to mobs by level
        is_boss: Whether this mob is a boss (higher stats/rewards)
    """
    
    class_skills_dict = mob_table["class_skills_dict"]
    is_playable = False
    
    def __init__(self, user_id: str, name: str, xp_drop: int = 0, is_boss: bool = False):
        """
        Initialize a new Mob.
        
        Args:
            user_id: Unique identifier for this mob instance
            name: Display name of the mob
            xp_drop: Initial XP to give the mob (determines starting level)
            is_boss: Whether this is a boss mob
        """
        super().__init__(
            user_id=user_id,
            name=name,
            class_table=mob_table.copy(),
        )
        self.is_boss = is_boss
        if xp_drop > 0:
            self.gain_exp(xp_drop)
    
    def exp_for_level_up(self) -> int:
        """
        Calculate XP needed for next level.
        
        Mobs level up faster than players (10 XP per level vs 100).
        
        Returns:
            XP required for next level
        """
        return self.level * 10
    
    def get_xp_reward(self) -> int:
        """
        Calculate XP reward for defeating this mob.
        
        Boss mobs give double XP.
        
        Returns:
            XP reward value
        """
        base_xp = self.level * 50 + self.exp
        return base_xp * 2 if self.is_boss else base_xp