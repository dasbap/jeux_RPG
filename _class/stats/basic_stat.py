from .stat import DefaultStat

class Energie(DefaultStat):
    """Classe mère pour les statistiques énergétiques comme Mana, Ki, Aura, etc."""
    def __init__(self, name: str, value: int):
        super().__init__(value)
        self.name = name  
    
    def __str__(self):
        return f"{self.name}: {self.current_value}"

class HP(DefaultStat):
    def __init__(self, value: int):
        super().__init__(value)
        self.name = "HP"


class Force(DefaultStat):
    def __init__(self, value: int):
        super().__init__(value)
        self.name = "Force"

class Endurance(DefaultStat):
    def __init__(self, value: int):
        super().__init__(value)
        self.name = "Endurance"

class Intelligence(DefaultStat):
    def __init__(self, value: int):
        super().__init__(value)
        self.name = "Intelligence"

class Sagesse(DefaultStat):
    def __init__(self, value: int):
        super().__init__(value)
        self.name = "Sagesse"

class Mana(Energie):
    def __init__(self, value: int):
        super().__init__("Mana", value)

class Aura(Energie):
    def __init__(self, value: int):
        super().__init__("Aura", value)

class Ki(Energie):
    def __init__(self, value: int):
        super().__init__("Ki", value)

class Foie(Energie):
    def __init__(self, value: int):
        super().__init__("Foie", value)
