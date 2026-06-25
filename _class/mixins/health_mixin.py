"""
Health management mixin for Character class.

Handles HP, damage, healing, death, and resurrection.
"""

from typing import TYPE_CHECKING, Dict, List

from jeuxRPG.i18n import t

if TYPE_CHECKING:
    from jeuxRPG._class.character import Character


class HealthMixin:
    """
    Mixin providing health-related functionality.
    
    Handles:
    - HP loss and damage calculation
    - Healing
    - Death checks
    - Resurrection
    - Damage reduction computation
    """
    
    def is_alive(self: 'Character') -> bool:
        """Check if character is alive (HP > 0)."""
        return self.hp.current_value > 0
    
    def _get_reduction(self: 'Character') -> Dict[str, List[int]]:
        """Get damage reduction stats from status effects."""
        return self.status["alteration"]["Damage"]["Reduction"]
    
    def _compute_damage(self: 'Character', amount: float) -> float:
        """
        Compute final damage after applying reductions.
        
        Args:
            amount: Base damage amount
            
        Returns:
            Final damage after reductions
        """
        reduction = self._get_reduction()

        malus = sum(reduction["-"])
        resistance = sum(reduction["+"])
        multiplier = 1.0

        for percent in reduction["%"]:
            multiplier *= percent

        final_amount = (amount - resistance + malus) * multiplier
        
        return max(0, final_amount)

    def lose_hp(self: 'Character', source: 'Character', amount: int) -> str:
        """
        Reduce character's HP by specified amount.
        
        Args:
            source: Character causing the damage
            amount: Amount of damage to apply
            
        Returns:
            Result message string
            
        Raises:
            ValueError: If amount is not positive
        """
        def clamp_reduction() -> int:
            import math
            endurance = self.get_stat("Endurance").current_value
            L = 0.9
            k = 0.02
            x0 = 150
            
            return int((L / (1 + math.exp(-k * (endurance - x0)))) * 100)
        
        if amount <= 0:
            raise ValueError("HP loss must be positive")
        
        if self.is_invulnerable():
            return t("combat.invulnerable", name=self.name, attacker=source.name)
            
        if self.have_reduction():
            amount = int(self._compute_damage(amount))
        
        # Apply endurance-based damage reduction
        reduction = clamp_reduction()
        
        amount = int(amount * (1 - (reduction/100)))
        
        self.hp.current_value = max(0, self.hp.current_value - amount)

        message = t("combat.dealt_damage", attacker=source.name, damage=amount, target=self.name)
        if not self.is_alive():
            message += f" {self.drop_xp(source)}"
            self.invocations.kill_all()

        return message

    def gain_hp(self: 'Character', amount: int) -> str:
        """
        Restore character's HP by specified amount.
        
        Args:
            amount: Amount of HP to restore
            
        Returns:
            Result message string
            
        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("HP gain must be positive")

        max_heal = self.hp.value - self.hp.current_value
        actual_heal = min(amount, max_heal)
        self.hp.current_value += actual_heal

        return t("combat.healed", name=self.name, amount=actual_heal)
    
    def _check_death(self: 'Character') -> bool:
        """Check if character should die from status effects."""
        return self.status.get("Death_in", 0) == 0
    
    def resurrect(self: 'Character', reviver: 'Character') -> str:
        """
        Resurrect a defeated character.
        
        Args:
            reviver: Character performing the resurrection
            
        Returns:
            Result message string
        """
        if self.is_alive():
            return t("combat.already_alive", name=self.name)

        self.hp.current_value = self.hp.value // 2
        return t("combat.resurrected", name=self.name, reviver=reviver.name)
