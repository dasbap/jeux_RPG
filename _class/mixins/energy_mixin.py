"""
Energy management mixin for Character class.

Handles energy systems, consumption, regeneration, and management.
"""

from typing import TYPE_CHECKING, List, Type

from jeuxRPG.i18n import t

if TYPE_CHECKING:
    from jeuxRPG._class.character import Character
    from jeuxRPG._class.res.character.stats.basic_stat import Energie


class EnergyMixin:
    """
    Mixin providing energy-related functionality.
    
    Handles:
    - Energy consumption
    - Energy regeneration
    - Energy type management (add, change, get)
    """
    
    def has_required_energie(self: 'Character', skill) -> bool:
        """
        Check if character has enough energy to use skill.
        
        Args:
            skill: Skill to check
            
        Returns:
            True if enough energy, False otherwise
        """
        try:
            energie = self.get_energie(skill.energie_target)
            return energie.current_value >= skill.energie_cost
        except (TypeError, AttributeError):
            return False

    def consume_energie(self: 'Character', amount: int, energie_type: Type['Energie']) -> None:
        """
        Consume specified amount of energy.
        
        Args:
            amount: Amount to consume
            energie_type: Type of energy to consume
            
        Raises:
            ValueError: If not enough energy available
        """
        energie = self.get_energie(energie_type)
        if energie.current_value < amount:
            raise ValueError("Not enough energy")
        energie.current_value -= amount

    def gain_energie(self: 'Character', amount: int, energie_type: Type['Energie']) -> str:
        """
        Restore specified amount of energy.
        
        Args:
            amount: Amount to restore
            energie_type: Type of energy to restore
            
        Returns:
            Result message string
            
        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("Energy gain must be positive")

        energie = self.get_energie(energie_type)
        max_gain = energie.value - energie.current_value
        actual_gain = min(amount, max_gain)
        energie.current_value += actual_gain

        return t("energy.restored", name=self.name, amount=actual_gain, energy_type=energie.name.lower())

    def add_energie(self: 'Character', energie: 'Energie') -> None:
        """
        Add new energy type to character.
        
        Args:
            energie: Energy instance to add
            
        Raises:
            ValueError: If energy type already exists
        """
        if any(isinstance(e, type(energie)) for e in self.energie):
            raise ValueError(f"{energie.name} is already in the energy's list of {self.name}")
        self.energie.append(energie)

    def change_energie(self: 'Character', old_energie: Type['Energie'], new_energie: 'Energie') -> None:
        """
        Replace one energy type with another.
        
        Args:
            old_energie: Energy type to replace
            new_energie: New energy instance
            
        Raises:
            TypeError: If old energy type doesn't exist
        """
        for i, energie in enumerate(self.energie):
            if isinstance(energie, old_energie):
                self.energie[i] = new_energie
                return
        raise TypeError(f"{old_energie.__name__} is not in the energy's list of {self.name}")

    def get_energie(self: 'Character', energie_type: Type['Energie']) -> 'Energie':
        """
        Get energy instance of specified type.
        
        Args:
            energie_type: Type of energy to retrieve
            
        Returns:
            Requested energy instance
            
        Raises:
            TypeError: If energy type doesn't exist
        """
        for energie in self.energie:
            if isinstance(energie, energie_type):
                return energie
        raise TypeError(f"{energie_type.__name__} is not in the energy's list of {self.name}")
