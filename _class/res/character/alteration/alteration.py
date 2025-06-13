from enum import Enum
from platform import node


class AlterationType(Enum):
    INVINCIBILYTY = 0
    BUFFSTAT = 1
    DEBUFFSTAT = 2
    DOT = 3
    STUN = 4
    RESISTENCE = 5
    WEAKNESS = 6

alteration_value_less = [AlterationType.STUN,AlterationType.INVINCIBILYTY]

class Alteration():
    def __init__(self, name : str,caster, value : int, time : int, target, stat_target = None,alterationType : AlterationType = None):
        if name == "": raise ValueError("name cn't be an empty str")
        if value <= 0:
            if not alterationType in alteration_value_less :
                raise ValueError("error in Alteration.value must be positif")
        if time <= 0: raise ValueError("time can't be negative or null")
        if caster == None: raise TypeError("caster must be a Character")
        
        self.name = name
        self.caster = caster
        self.value = value
        self.duration = time
        self.target = target
        self.stat_target = stat_target
        self.type = alterationType
    
    def get_value(self) -> int:
        return self.value
    
    def get_target(self):
        return self.target
    
    def get_duration(self) -> int:
        return self.duration
    
    def get_stat_target(self):
        return self.stat_target
    
    def decrease(self) -> None:
        self.duration -= 1
        
    def get_caster(self):
        return self.caster
    
    def is_over(self) -> bool:
        if self.duration < 0 : raise RuntimeError("invalide Alteration.duration")
        return self.duration == 0
    
    def __str__(self) -> str:
        return f"{self.name} : is a {self.type.name} and change {self.stat_target.__name__} of {self.target.name} by {self.value} for {self.duration} round"
    
    def __repr__(self) -> str:
        return self.__str__()

class Buff(Alteration):
    def __init__(self, name, caster, value, time, target, stat_target):
        super().__init__(name, caster, value, time, target, stat_target, AlterationType.BUFFSTAT)

class DeBuff(Alteration):
    def __init__(self, name, caster, value, time, target, stat_target):
        super().__init__(name, caster, value, time, target, stat_target, AlterationType.DEBUFFSTAT)
    
class Dot(Alteration):
    def __init__(self, name, caster, value, time, target):
        super().__init__(name, caster, value, time, target, AlterationType.DOT)

class Stun(Alteration):
    def __init__(self, name, caster, time, target):
        super().__init__(name, caster, 0, time, target,None, AlterationType.STUN)

class Resistance(Alteration):
    def __init__(self, name, caster, value, time, target, alterationType : AlterationType.RESISTENCE):
        super().__init__(name, caster, value, time, target, alterationType)
        
