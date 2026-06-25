from __future__ import annotations
from typing import TYPE_CHECKING

from jeuxRPG.i18n import t
from jeuxRPG._class.place.jobs.job import Job
from jeuxRPG._class.place.jobs.job_types import JobType, ServiceType

if TYPE_CHECKING:
    from jeuxRPG._class.place.building import Building


class NPC:
    """
    Représente un personnage non-joueur (PNJ).
    
    Contrairement aux Character, les NPC ne combattent pas mais offrent
    des services, du commerce et des quêtes.
    
    Attributes:
        name: Nom du PNJ
        job: Métier du PNJ (obligatoire)
        location: Bâtiment où se trouve le PNJ
        dialogues: Dictionnaire de dialogues par contexte
        inventory: Inventaire pour les marchands
        gold: Or possédé
        quests: Liste des quêtes disponibles
    """
    
    def __init__(
        self,
        name: str,
        job: Job,
        location: Building | None = None,
        dialogues: dict[str, list[str]] | None = None,
        inventory: list | None = None,
        gold: int = 100,
        quests: list[str] | None = None
    ):
        self.name = name
        self.job = job
        self.location = location
        self.dialogues = dialogues or self._default_dialogues()
        self.inventory = inventory or []
        self.gold = gold
        self.quests = quests or []
        
        # Lier le workplace du job au location
        if location and not job.workplace:
            job.workplace = location
    
    def _default_dialogues(self) -> dict[str, list[str]]:
        """Retourne les dialogues par défaut selon le métier."""
        job_type_key = self.job.job_type.name.lower()
        greeting_key = f"npc.greeting.{job_type_key}"
        
        # Try to get job-specific greeting, fallback to default
        greetings = t(greeting_key)
        if greetings == greeting_key:  # Key not found, use default
            greetings = t("npc.greeting.default")
        
        return {
            "greeting": greetings if isinstance(greetings, list) else [greetings],
            "farewell": t("npc.farewell"),
            "busy": t("npc.busy"),
            "no_gold": t("npc.no_gold")
        }
    
    def get_dialogue(self, context: str = "greeting") -> str:
        """Retourne un dialogue aléatoire selon le contexte."""
        import random
        dialogues = self.dialogues.get(context, self.dialogues.get("greeting", ["..."]))
        return random.choice(dialogues)
    
    def can_provide(self, service: ServiceType) -> bool:
        """Vérifie si le PNJ peut fournir un service."""
        return self.job.can_provide(service)
    
    def add_to_inventory(self, item) -> None:
        """Ajoute un objet à l'inventaire du PNJ."""
        self.inventory.append(item)
    
    def remove_from_inventory(self, item) -> bool:
        """Retire un objet de l'inventaire. Retourne True si réussi."""
        if item in self.inventory:
            self.inventory.remove(item)
            return True
        return False
    
    def add_quest(self, quest_id: str) -> None:
        """Ajoute une quête disponible."""
        if quest_id not in self.quests:
            self.quests.append(quest_id)
    
    def has_quests(self) -> bool:
        """Vérifie si le PNJ a des quêtes disponibles."""
        return len(self.quests) > 0
    
    def get_info(self) -> dict:
        """Retourne les informations du PNJ."""
        return {
            "name": self.name,
            "job": self.job.get_info(),
            "location": self.location.name if self.location else None,
            "gold": self.gold,
            "inventory_count": len(self.inventory),
            "quests_available": len(self.quests),
            "services": [s.name for s in self.job.services]
        }
    
    def __repr__(self) -> str:
        return f"NPC({self.name!r}, {self.job.job_type.name})"


# === Factory functions pour créer des PNJ courants ===

def create_blacksmith(name: str = "Forgeron", location: Building | None = None) -> NPC:
    """Crée un PNJ forgeron."""
    job = Job(name, JobType.BLACKSMITH, level=5)
    return NPC(name, job, location)


def create_innkeeper(name: str = "Aubergiste", location: Building | None = None) -> NPC:
    """Crée un PNJ aubergiste."""
    job = Job(name, JobType.INNKEEPER, level=3)
    return NPC(name, job, location)


def create_merchant(name: str = "Marchand", location: Building | None = None) -> NPC:
    """Crée un PNJ marchand."""
    job = Job(name, JobType.MERCHANT, level=4)
    return NPC(name, job, location, gold=500)


def create_priest(name: str = "Prêtre", location: Building | None = None) -> NPC:
    """Crée un PNJ prêtre."""
    job = Job(name, JobType.PRIEST, level=5)
    return NPC(name, job, location)


def create_mayor(name: str = "Maire", location: Building | None = None) -> NPC:
    """Crée un PNJ maire."""
    job = Job(name, JobType.MAYOR, level=10)
    return NPC(name, job, location, gold=1000)


def create_guard(name: str = "Garde", location: Building | None = None) -> NPC:
    """Crée un PNJ garde."""
    job = Job(name, JobType.GUARD, level=3)
    return NPC(name, job, location, gold=50)
