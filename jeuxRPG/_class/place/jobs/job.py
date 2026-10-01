from __future__ import annotations
from typing import TYPE_CHECKING
from jeuxRPG._class.place.jobs.job_types import JobType, ServiceType

if TYPE_CHECKING:
    from jeuxRPG._class.place.building import Building


class Job:
    """
    Représente un métier que peut exercer un joueur ou un PNJ.
    
    Attributes:
        name: Nom affiché du métier (ex: "Forgeron du village")
        job_type: Type de métier (JobType enum)
        level: Niveau de maîtrise (1-100)
        exp: Expérience dans ce métier
        services: Liste des services que ce métier peut offrir
        recipes: Liste des recettes/crafts disponibles
        workplace: Bâtiment où le métier est exercé (optionnel)
    """
    
    MAX_LEVEL = 100
    EXP_PER_LEVEL = 100  # Exp nécessaire par niveau
    
    def __init__(
        self,
        name: str,
        job_type: JobType,
        level: int = 1,
        exp: int = 0,
        services: list[ServiceType] | None = None,
        recipes: list[str] | None = None,
        workplace: Building | None = None
    ):
        self.name = name
        self.job_type = job_type
        self.level = max(1, min(level, self.MAX_LEVEL))
        self.exp = exp
        self.services = services or self._default_services()
        self.recipes = recipes or []
        self.workplace = workplace
    
    def _default_services(self) -> list[ServiceType]:
        """Retourne les services par défaut selon le type de métier."""
        defaults = {
            JobType.BLACKSMITH: [ServiceType.SELL, ServiceType.BUY, ServiceType.CRAFT, ServiceType.REPAIR],
            JobType.ALCHEMIST: [ServiceType.SELL, ServiceType.BUY, ServiceType.CRAFT],
            JobType.ENCHANTER: [ServiceType.UPGRADE, ServiceType.CRAFT],
            JobType.MERCHANT: [ServiceType.BUY, ServiceType.SELL],
            JobType.INNKEEPER: [ServiceType.REST, ServiceType.SELL],
            JobType.PRIEST: [ServiceType.HEAL, ServiceType.BLESS],
            JobType.GUARD: [],
            JobType.MAYOR: [ServiceType.QUEST],
            JobType.BANKER: [ServiceType.STORE],
            JobType.SCHOLAR: [ServiceType.TEACH, ServiceType.QUEST],
        }
        return defaults.get(self.job_type, [])
    
    def gain_exp(self, amount: int) -> bool:
        """
        Ajoute de l'expérience au métier.
        Retourne True si level up.
        """
        if self.level >= self.MAX_LEVEL:
            return False
        
        self.exp += amount
        leveled_up = False
        
        while self.exp >= self.EXP_PER_LEVEL and self.level < self.MAX_LEVEL:
            self.exp -= self.EXP_PER_LEVEL
            self.level += 1
            leveled_up = True
        
        return leveled_up
    
    def can_provide(self, service: ServiceType) -> bool:
        """Vérifie si ce métier peut fournir un service donné."""
        return service in self.services
    
    def add_recipe(self, recipe_id: str) -> None:
        """Ajoute une recette au métier."""
        if recipe_id not in self.recipes:
            self.recipes.append(recipe_id)
    
    def get_info(self) -> dict:
        """Retourne les informations du métier."""
        return {
            "name": self.name,
            "type": self.job_type.name,
            "level": self.level,
            "exp": self.exp,
            "exp_to_next": self.EXP_PER_LEVEL - self.exp if self.level < self.MAX_LEVEL else 0,
            "services": [s.name for s in self.services],
            "recipes_count": len(self.recipes),
            "workplace": self.workplace.name if self.workplace else None
        }
    
    def __repr__(self) -> str:
        return f"Job({self.name!r}, {self.job_type.name}, lv{self.level})"
