from __future__ import annotations
from typing import TYPE_CHECKING
from jeuxRPG._class.place.building import Building
from jeuxRPG._class.res.classType import Build_type, Build_state

if TYPE_CHECKING:
    from jeuxRPG._class.place.town import Town
    from jeuxRPG._class.place.jobs.npc import NPC


class District:
    """
    Représente un quartier d'une ville.
    
    Attributes:
        name: Nom du quartier
        buildings: Dictionnaire des bâtiments (nom -> Building)
        npcs: Liste des PNJ présents dans le quartier
        guards: Liste des gardes (PNJ avec job GUARD)
        resources: Dictionnaire des ressources stockées
        town: Ville parente
        connected_districts: Quartiers accessibles depuis celui-ci
    """
    
    def __init__(self, name: str, town: Town | None = None):
        self.name = name
        self.buildings: dict[str, Building] = {}
        self.npcs: list[NPC] = []
        self.guards: list[NPC] = []
        self.resources: dict[str, int] = {}
        self.town = town
        self.connected_districts: list[District] = []

    # === Navigation ===
    
    def connect_to(self, other: District, bidirectional: bool = True) -> None:
        """Connecte ce quartier à un autre pour la navigation."""
        if other not in self.connected_districts:
            self.connected_districts.append(other)
        if bidirectional and self not in other.connected_districts:
            other.connected_districts.append(self)
    
    def disconnect_from(self, other: District, bidirectional: bool = True) -> None:
        """Déconnecte ce quartier d'un autre."""
        if other in self.connected_districts:
            self.connected_districts.remove(other)
        if bidirectional and self in other.connected_districts:
            other.connected_districts.remove(self)
    
    def can_go_to(self, district_name: str) -> bool:
        """Vérifie si on peut aller à un quartier depuis celui-ci."""
        return any(d.name == district_name for d in self.connected_districts)
    
    def get_accessible_districts(self) -> list[str]:
        """Retourne la liste des noms de quartiers accessibles."""
        return [d.name for d in self.connected_districts]
    
    def get_accessible_buildings(self) -> list[str]:
        """Retourne la liste des bâtiments accessibles dans ce quartier."""
        return list(self.buildings.keys())

    # === Bâtiments ===

    def add_building(self, building: Building) -> None:
        """Ajoute un bâtiment au quartier."""
        if building.name not in self.buildings:
            self.buildings[building.name] = building
            building.district = self
    
    def create_building(
        self, 
        name: str, 
        b_type: Build_type, 
        level: int = 1, 
        status: Build_state = Build_state.OPERATIONAL
    ) -> Building:
        """Crée et ajoute un nouveau bâtiment."""
        building = Building(name, b_type, level, status)
        self.add_building(building)
        return building
    
    def get_building(self, name: str) -> Building | None:
        """Récupère un bâtiment par son nom."""
        return self.buildings.get(name)

    def upgrade_building(self, building_name: str) -> bool:
        """Améliore un bâtiment. Retourne True si réussi."""
        building = self.buildings.get(building_name)
        if building:
            building.upgrade()
            return True
        return False

    # === PNJ ===

    def add_npc(self, npc: NPC) -> None:
        """Ajoute un PNJ au quartier."""
        if npc not in self.npcs:
            self.npcs.append(npc)
            from jeuxRPG._class.place.jobs.job_types import JobType
            if npc.job.job_type == JobType.GUARD:
                self.guards.append(npc)
    
    def remove_npc(self, npc: NPC) -> bool:
        """Retire un PNJ du quartier. Retourne True si réussi."""
        if npc in self.npcs:
            self.npcs.remove(npc)
            if npc in self.guards:
                self.guards.remove(npc)
            return True
        return False
    
    def get_npcs_by_job(self, job_type) -> list[NPC]:
        """Récupère tous les PNJ d'un certain métier."""
        return [npc for npc in self.npcs if npc.job.job_type == job_type]
    
    def find_npc(self, name: str) -> NPC | None:
        """Cherche un PNJ par son nom."""
        for npc in self.npcs:
            if npc.name.lower() == name.lower():
                return npc
        return None

    # === Ressources ===

    def add_resource(self, resource_name: str, quantity: int) -> None:
        """Ajoute une ressource au quartier."""
        if resource_name not in self.resources:
            self.resources[resource_name] = 0
        self.resources[resource_name] += quantity

    def spend_resource(self, resource_name: str, quantity: int) -> bool:
        """Dépense une ressource. Retourne True si réussi."""
        if resource_name in self.resources and self.resources[resource_name] >= quantity:
            self.resources[resource_name] -= quantity
            return True
        return False
    
    def get_resource(self, resource_name: str) -> int:
        """Retourne la quantité d'une ressource."""
        return self.resources.get(resource_name, 0)

    # === Info ===

    def get_info(self) -> dict:
        """Retourne les informations du quartier."""
        return {
            "name": self.name,
            "buildings": {name: b.get_info() for name, b in self.buildings.items()},
            "npcs": [npc.get_info() for npc in self.npcs],
            "guards_count": len(self.guards),
            "resources": self.resources,
            "town": self.town.name if self.town else None,
            "connected_to": self.get_accessible_districts()
        }
    
    def __repr__(self) -> str:
        return f"District({self.name!r}, {len(self.buildings)} buildings, {len(self.npcs)} NPCs)"
