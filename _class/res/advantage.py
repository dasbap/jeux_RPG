
from typing import Literal, Union
from _class.res.classType import DamageType


class Advantage():
    def __init__(self):
        self.weakness : list[DamageType] = []
        self.resilience : list[DamageType] = []
    
    def __contains__(self, type : DamageType) -> bool:
        return not self.is_neutre_to(type)
    
    def __eq__(self, other : 'Advantage') -> bool:
        return self.get_weakness().sort() == other.get_weakness().sort() and self.get_resilience().sort() == other.get_resilience().sort()
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def get_weakness(self) -> list[DamageType] :
        return self.weakness.copy()
    
    def get_resilience(self) -> list[DamageType] :
        return self.weakness.copy()
    
    def get_all(self) -> dict[Union[Literal["weakness"],Literal["resilience"]], list[DamageType]]:
        return {"weakness": self.get_weakness(),"resilience":self.get_resilience()}
    
    def is_weak_to(self, type : DamageType) -> bool:
        return type in self.weakness
    
    def is_resilient_to(self, type : DamageType) -> bool:
        return type in self.resilience
    
    def is_neutre_to(self, type : DamageType) -> bool:
        return not self.is_resilient_to(type) or not self.is_weak_to(type)
    
    def add_weakness(self, type : DamageType) -> bool:
        if not self.is_neutre_to(type): raise TypeError(f"the type is not neutre for {self}")
        self.weakness.append(type)
    
    def add_resilience(self, type : DamageType) -> bool:
        if not self.is_neutre_to(type): raise TypeError(f"the type is not neutre for {self}")
        self.resilience.append(type)
    
    def del_weakness(self, type : DamageType) -> None:
        if not self.is_weak_to(type): raise TypeError(f"the type {type.name} is not in {self.weakness}")
        self.weakness.remove(type)
    
    def del_resilience(self, type : DamageType) -> None:
        if not self.is_resilient_to(type): raise TypeError(f"the type {type.name} is not in {self.resilience}")
        self.resilience.remove(type)
    
    def change_all_advantage(self) -> None:
        tmp = self.weakness
        self.weakness = self.resilience
        self.resilience = tmp
    
    def add_for_all(self, type : DamageType) -> None:
        if not self.is_resilient_to(type):
            self.add_resilience(type)
        if not self.is_weak_to(type):
            self.add_weakness(type)
    
    def is_in_both(self, type : DamageType) -> bool:
        return self.is_weak_to(type) and self.is_resilient_to(type)
    
    def change_type_advantage(self, type : DamageType) -> None:
        if self.is_in_both(type): raise TypeError(f"{type.name} is alredy in both")
        if self.is_weak_to(type):
            self.del_weakness(type)
            self.add_resilience(type)
        elif self.is_resilient_to(type):
            self.del_resilience(type)
            self.add_weakness(type)
        else:
            raise TypeError(f"{type.name} is neutre can't change the advantage")