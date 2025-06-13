from _class.res.character.stats.stat import DefaultStat


class Energie(DefaultStat):
    """Classe de base pour les statistiques énergétiques.
    
    Attributes:
        name (str): Nom du type d'énergie
        max_value (int): Valeur maximale de l'énergie
        regen_rate (float): Taux de régénération par tour
    """
    
    def __init__(self, value: int, regen_rate: float = 0.3):
        """Initialise une énergie avec son nom, sa valeur et son taux de régénération.
        
        Args:
            name: Nom de l'énergie (Mana, Ki, etc.)
            value: Valeur maximale initiale
            regen_rate: Taux de régénération (fraction de max_value par tour)
        """
        super().__init__(value)
        self._regen_rate = regen_rate 
        
    @property
    def regen_rate(self) -> float:
        return self._regen_rate
        
    @regen_rate.setter
    def regen_rate(self, value: float) -> None:
        self._regen_rate = max(0.0, min(0.1, value))
        
    def regenerate(self) -> None:
        """Régénère l'énergie selon le taux de régénération."""
        regen_amount = int(self.value * self.regen_rate)
        self._current_value = min(self.value, self.current_value + regen_amount)
    
    def change_type(self,new_type):
        if not issubclass(new_type, Energie) : raise TypeError("Can only convert to Energie subclasses")
        return super().change_type(new_type)
        
    
    def is_full(self) -> bool:
        return self.current_value >= self.value
    
    def __repr__(self):
        return self.__str__()

class VitalStat(DefaultStat):
    """Classe de base pour les statistiques vitales comme les HP."""
    
    def __init__(self, value: int):
        super().__init__(value)
        
    def is_depleted(self) -> bool:
        """Vérifie si la statistique est épuisée."""
        return self.current_value <= 0
    
    def drain_all(self) -> None:
        self._current_value = 0
    
    def change_type(self, new_type):
        if not issubclass(new_type, VitalStat) : raise TypeError("Can only convert to VitalStat subclasses")
        return super().change_type(new_type)
    
    def is_full(self) -> bool:
        return self.current_value >= self.value

class AttributeStat(DefaultStat):
    """Classe de base pour les attributs de caractère (Force, Intelligence, etc.)."""
    
    def __init__(self, value: int):
        super().__init__(value)
        
    def change_type(self, new_type):
        if not issubclass(new_type, AttributeStat) : raise TypeError("Can only convert to AttributeStat subclasses")
        return super().change_type(new_type)
    def __str__(self) -> str:
        return f"{self.name}: {self.current_value}"

# Statistiques vitales --------------------------------------------------------

class HP(VitalStat):
    """Points de vie (Hit Points)."""
    
    def __init__(self, value: int):
        super().__init__(value)
        
    def heal(self, amount: int) -> int:
        """Soigne les HP et retourne le montant réel soigné."""
        if amount <= 0:
            return 0
        healed = min(amount, self.value - self.current_value)
        self._current_value += healed
        return healed

# Statistiques d'énergie -----------------------------------------------------

class Mana(Energie):
    """Énergie magique utilisée pour les sorts."""
    
    def __init__(self, value: int, regen_rate: float = 0.15):
        super().__init__(value, regen_rate)

class Aura(Energie):
    """Énergie spirituelle utilisée pour les capacités spéciales."""
    
    def __init__(self, value: int, regen_rate: float = 0.1):
        super().__init__(value, regen_rate)

class Ki(Energie):
    """Énergie interne utilisée pour les techniques martiales."""
    
    def __init__(self, value: int, regen_rate: float = 0.2):
        super().__init__(value, regen_rate)

class Foie(Energie):
    """Énergie de courage utilisée pour les capacités défensives."""
    
    def __init__(self, value: int, regen_rate: float = 0.05):
        super().__init__(value, regen_rate)

# Attributs de caractère -----------------------------------------------------

class Force(AttributeStat):
    """Force physique brute."""
    
    def __init__(self, value: int):
        super().__init__(value)

class Endurance(AttributeStat):
    """Résistance physique et capacité à endurer."""
    
    def __init__(self, value: int):
        super().__init__(value)

class Intelligence(AttributeStat):
    """Capacité cognitive et magique."""
    
    def __init__(self, value: int):
        super().__init__(value)

class Sagesse(AttributeStat):
    """Jugement, perspicacité et intuition."""
    
    def __init__(self, value: int):
        super().__init__(value)