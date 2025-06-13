from typing import List

from _class.res.character.alteration.alteration import Buff, DeBuff


class DefaultStat:
    """Represents a game statistic with buff/debuff management.
    
    Attributes:
        value (int): Base value of the statistic
        _current_value (int): Current modified value after buffs/debuffs
        buffs (List[Skill]): Active buffs affecting this stat
        debuffs (List[Skill]): Active debuffs affecting this stat
        name (str): Name of the statistic (defaults to class name)
    """
    
    def __init__(self, value: int) -> None:
        """Initialize the statistic with a base value.
        
        Args:
            value: Base value of the statistic (must be positive)
            name: Optional custom name for the statistic
            
        Raises:
            ValueError: If value is not a positive integer
        """
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"Stat value must be a positive integer {type(value), value}")
            
        self.value = value
        self._current_value = value
        self.buffs: List[Buff] = []
        self.debuffs: List[DeBuff] = []
        self.name = self.__class__.__name__
    
    # Magic methods ###########################################################
    
    
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (int, DefaultStat)):
            return NotImplemented
        compare_val = other if isinstance(other, int) else other.current_value
        return self.current_value == compare_val
    
    def __ne__(self, other: object) -> bool:
        return not (self == other)
    
    def __gt__(self, other: object) -> bool:
        if not isinstance(other, (int, DefaultStat)):
            return NotImplemented
        compare_val = other if isinstance(other, int) else other.current_value
        return self.current_value > compare_val
    
    def __ge__(self, other: object) -> bool:
        if not isinstance(other, (int, DefaultStat)):
            return NotImplemented
        compare_val = other if isinstance(other, int) else other.current_value
        return self.current_value >= compare_val
    
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, (int, DefaultStat)):
            return NotImplemented
        compare_val = other if isinstance(other, int) else other.current_value
        return self.current_value < compare_val
    
    def __le__(self, other: object) -> bool:
        if not isinstance(other, (int, DefaultStat)):
            return NotImplemented
        compare_val = other if isinstance(other, int) else other.current_value
        return self.current_value <= compare_val
    
    def __iadd__(self, other: int) -> 'DefaultStat':
        """Add to current value with += operator."""
        if not isinstance(other, int):
            raise TypeError("Can only add integers to stats")
        self._current_value += other
        self._clamp_current_value()
        return self
    
    def __add__(self, other: int) -> 'DefaultStat':
        """Create new stat with added base value using + operator."""
        if not isinstance(other, int):
            raise TypeError("Can only add integers to stats")
        if not other > 0:
            raise ValueError("the value must be positive")
        self.current_value += other
        self._recalculate()
        return self
    
    def __isub__(self, other: int) -> 'DefaultStat':
        """Subtract from current value with -= operator."""
        if not isinstance(other, int):
            raise TypeError("Can only subtract integers from stats")
        self._current_value = max(0, self._current_value - other)
        return self
    
    def __sub__(self, other: int) -> 'DefaultStat':
        """Create new stat with subtracted base value using - operator."""
        if not isinstance(other, int):
            raise TypeError("Can only subtract integers from stats")
        if not other > 0:
            raise ValueError("the value must be positive")
        self.current_value -= other
        self._recalculate()
        return self
    
    def __str__(self) -> str:
        """User-friendly string representation."""
        return f"{self.name}: {self.current_value}/{self.value}"
    
    def __repr__(self) -> str:
        """Developer-friendly string representation."""
        return f"{self.__class__.__name__} value={self.value}"
    
    # Property accessors ######################################################
    
    @property
    def current_value(self) -> int:
        """Get the current modified value of the statistic."""
        return self._current_value
    
    @current_value.setter
    def current_value(self, value: int) -> None:
        """Set the current value (clamped to reasonable bounds)."""
        if not isinstance(value, int):
            raise ValueError("Stat value must be an integer")
        self._current_value = max(0, min(value, self.value * 10))
        self._clamp_current_value()
    
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    # Public methods ##########################################################
    
    def change_type(self, new_type: type) -> None:
        if not issubclass(new_type, DefaultStat):
            raise TypeError(f"Can only convert to {DefaultStat} subclasses")
        self.__class__ = new_type
        self.name = self.__class__.__name__
    
    def add_buff(self, buff: Buff) -> None:
        """Add a buff and recalculate current value.
        
        Args:
            buff: The buff Buff to add
            
        Raises:
            TypeError: If buff is not a Buff instance
        """
        if not isinstance(buff, Buff):
            raise TypeError("Buffs must be Buff instances")
        self.buffs.append(buff)
        self._recalculate()
    
    def remove_buff(self, buff: object) -> bool:
        """Remove a buff if present and recalculate.
        
        Args:
            buff: The buff object to remove
            
        Returns:
            True if buff was removed, False if not found
            
        Raises:
            TypeError: If buff is not a object instance
        """
        if not isinstance(buff, object):
            raise TypeError("Buffs must be object instances")
        if buff in self.buffs:
            self.buffs.remove(buff)
            self._recalculate()
            return True
        return False
    
    def add_debuff(self, debuff: object) -> None:
        """Add a debuff and recalculate current value.
        
        Args:
            debuff: The debuff object to add
            
        Raises:
            TypeError: If debuff is not a object instance
        """
        if not isinstance(debuff, object):
            raise TypeError("Debuffs must be object instances")
        self.debuffs.append(debuff)
        self._recalculate()
    
    def set_max(self) -> None:
        self._current_value = self.value
        self._recalculate()
    
    def remove_debuff(self, debuff: object) -> bool:
        """Remove a debuff if present and recalculate.
        
        Args:
            debuff: The debuff object to remove
            
        Returns:
            True if debuff was removed, False if not found
            
        Raises:
            TypeError: If debuff is not a object instance
        """
        if not isinstance(debuff, object):
            raise TypeError("Debuffs must be object instances")
        if debuff in self.debuffs:
            self.debuffs.remove(debuff)
            self._recalculate()
            return True
        return False
    
    def clear_effects(self) -> None:
        """Remove all buffs and debuffs."""
        self.buffs.clear()
        self.debuffs.clear()
        self._recalculate()
    
    def update_base_value(self, new_value: int) -> None:
        """Update the base value and recalculate current value.
        
        Args:
            new_value: New base value for the stat
            
        Raises:
            ValueError: If new_value is not a positive integer
        """
        if not isinstance(new_value, int) or new_value < 0:
            raise ValueError("Base value must be a positive integer")
        self.value = new_value
        self._recalculate()
    
    def upgrade_base_value(self, value : int) -> None:
        if value <= 0 : raise ValueError("value must be positive")
        self.value += value
        self._recalculate()
    
    def get_effect_value(self) -> int:
        """Get the total modified value from all effects."""
        return self.current_value - self.value
    
    def end_round(self) -> None:
        for alteration in self.buffs + self.debuffs:
            alteration.decrease()

        self.buffs = [buff for buff in self.buffs if not buff.is_over()]
        self.debuffs = [debuff for debuff in self.debuffs if not debuff.is_over()]

    
    # Private methods #########################################################
    
    def _recalculate(self) -> None:
        """Recalculate current value based on base value and effects."""
        total = self.value
        # Apply buffs
        for buff in self.buffs:
            total += buff.get_value()
        
        # Apply debuffs
        for debuff in self.debuffs:
            total = max(1, total - debuff.get_value())
        
        self._current_value = total
        self._clamp_current_value()
    
    def _clamp_current_value(self) -> None:
        """Ensure current value stays within reasonable bounds."""
        self._current_value = max(0, self._current_value)
        # Optional: Add upper bound if needed for your game balance
        # self._current_value = min(self._current_value, self.value * 2)