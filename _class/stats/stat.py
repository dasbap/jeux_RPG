from _class.skill import Skill

class DefaultStat:
    def __init__(self, value: int):
        self.value = value
        self._current_value = value  
        self.buffs: list[Skill] = []
        self.debuffs: list[Skill] = []
        self.name = self.__class__.__name__

    def __eq__(self, value):
        return self._current_value == value

    def __ne__(self, value):
        return self._current_value != value

    def __gt__(self, value):
        return self._current_value > value

    def __ge__(self, value):
        return self._current_value >= value

    def __lt__(self, value):
        return self._current_value < value

    def __le__(self, value):
        return self._current_value <= value

    def __iadd__(self, value):
        if isinstance(value, int): 
            self._current_value += value
            self.check_all()  # Recalculate value after addition
            return self
        raise TypeError("L'opération += nécessite un nombre int")

    def __add__(self, other):
        if isinstance(other, int):
            return self.__class__(self.value + other) 
        raise TypeError("L'opération + nécessite un nombre")

    def __isub__(self, value):
        if isinstance(value, int):
            self._current_value = max(0, self._current_value - value)
            self.check_all()  # Recalculate value after subtraction
            return self
        raise TypeError("L'opération -= nécessite un nombre int")

    def __sub__(self, other):
        if isinstance(other, int):
            return self.__class__(max(0, self.value - other)) 
        raise TypeError("L'opération - nécessite un nombre")

    def __str__(self):
        return f"{self.name}: {self._current_value}"

    def __setattr__(self, name : str, value):
        if name == "_current_value":
            if not isinstance(value, int):
                raise ValueError("La valeur de la statistique doit être un entier")
        object.__setattr__(self, name, value) 

    @property
    def current_value(self) -> int:
        """Retourne la valeur actuelle de la statistique."""
        return self._current_value

    def change_type(self, new_type: type):
        """Change le type de l'instance actuelle."""
        return new_type(self.value)

    def add_buff(self, buff: Skill):
        """Ajoute un buff et met à jour la valeur actuelle."""
        self.buffs.append(buff)
        self.check_all()

    def remove_buff(self, buff: Skill):
        """Supprime un buff et met à jour la valeur actuelle."""
        if buff in self.buffs:
            self.buffs.remove(buff)
            self.check_all()

    def add_debuff(self, debuff: Skill):
        """Ajoute un debuff et met à jour la valeur actuelle."""
        self.debuffs.append(debuff)
        self.check_all()

    def remove_debuff(self, debuff: Skill):
        """Supprime un debuff et met à jour la valeur actuelle."""
        if debuff in self.debuffs:
            self.debuffs.remove(debuff)
            self.check_all()

    def check_all(self):
        """Recalcule la valeur actuelle en fonction des buffs et debuffs."""
        self._current_value = self.value  

        for buff in self.buffs:
            self._current_value += buff.value  

        for debuff in self.debuffs:
            self._current_value = max(1, self._current_value - debuff.value)  
    
    def update_value(self, value: int) -> None:
        """Met à jour la valeur actuelle de la statistique."""
        self.value += value
        self.check_all()
