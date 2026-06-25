from __future__ import annotations
from jeuxRPG._class.place.district import District
from jeuxRPG._class.place.building import Building
from jeuxRPG._class.res.classType import Build_type, Build_state


class Town:
    """
    Représente une ville ou un village.
    
    Attributes:
        name: Nom de la ville
        population: Population totale
        wealth: Richesse de la ville
        reputation: Réputation (affecte les prix, quêtes disponibles...)
        districts: Dictionnaire des quartiers (nom -> District)
        connected_towns: Villes/villages accessibles depuis celle-ci
        entry_district: Quartier d'entrée par défaut (arrivée des voyageurs)
    """
    
    def __init__(
        self, 
        name: str, 
        population: int = 0, 
        wealth: int = 0, 
        reputation: int = 0
    ):
        self.name = name
        self.population = population
        self.wealth = wealth
        self.reputation = reputation
        self.districts: dict[str, District] = {}
        self.size: tuple[int, int] | None = None
        # Optional metadata loaded from world data (may include sizes, POIs, etc.)
        self.entry_points: list[dict] = []
        self.pois: list[dict] = []
        self.connected_towns: dict[str, Town] = {}  # nom -> Town
        self.entry_district: District | None = None

    # === Navigation entre villes ===
    
    def connect_to(self, other: Town, bidirectional: bool = True) -> None:
        """Connecte cette ville à une autre pour le voyage."""
        if other.name not in self.connected_towns:
            self.connected_towns[other.name] = other
        if bidirectional and self.name not in other.connected_towns:
            other.connected_towns[self.name] = self
    
    def disconnect_from(self, other: Town, bidirectional: bool = True) -> None:
        """Déconnecte cette ville d'une autre."""
        if other.name in self.connected_towns:
            del self.connected_towns[other.name]
        if bidirectional and self.name in other.connected_towns:
            del other.connected_towns[self.name]
    
    def can_travel_to(self, town_name: str) -> bool:
        """Vérifie si on peut voyager vers une ville."""
        return town_name in self.connected_towns
    
    def get_travel_destinations(self) -> list[str]:
        """Retourne la liste des villes accessibles."""
        return list(self.connected_towns.keys())
    
    def set_entry_district(self, district_name: str) -> bool:
        """Définit le quartier d'entrée. Retourne True si réussi."""
        district = self.districts.get(district_name)
        if district:
            self.entry_district = district
            return True
        return False

    # === Quartiers ===

    def add_district(self, district: District) -> None:
        """Ajoute un quartier à la ville."""
        if district.name not in self.districts:
            self.districts[district.name] = district
            district.town = self
            # Premier quartier = entrée par défaut
            if self.entry_district is None:
                self.entry_district = district

    def create_district(self, name: str) -> District:
        """Crée et ajoute un nouveau quartier."""
        district = District(name, town=self)
        self.add_district(district)
        return district
    
    def get_district(self, name: str) -> District | None:
        """Récupère un quartier par son nom."""
        return self.districts.get(name)
    
    def connect_districts(self, name1: str, name2: str) -> bool:
        """Connecte deux quartiers entre eux. Retourne True si réussi."""
        d1 = self.districts.get(name1)
        d2 = self.districts.get(name2)
        if d1 and d2:
            d1.connect_to(d2)
            return True
        return False

    # === Bâtiments ===

    def add_building(self, district_name: str, building: Building) -> bool:
        """Ajoute un bâtiment à un quartier. Retourne True si réussi."""
        district = self.districts.get(district_name)
        if district:
            district.add_building(building)
            return True
        return False
    
    def create_building(
        self,
        district_name: str,
        building_name: str,
        building_type: Build_type,
        level: int = 1,
        status: Build_state = Build_state.OPERATIONAL
    ) -> Building | None:
        """Crée un bâtiment dans un quartier. Retourne le bâtiment ou None."""
        district = self.districts.get(district_name)
        if district:
            return district.create_building(building_name, building_type, level, status)
        return None

    def upgrade_building(self, district_name: str, building_name: str) -> bool:
        """Améliore un bâtiment. Retourne True si réussi."""
        district = self.districts.get(district_name)
        if district:
            return district.upgrade_building(building_name)
        return False

    # === Ressources ===

    def add_resource(self, district_name: str, resource_name: str, quantity: int) -> bool:
        """Ajoute une ressource à un quartier. Retourne True si réussi."""
        district = self.districts.get(district_name)
        if district:
            district.add_resource(resource_name, quantity)
            return True
        return False

    def spend_resource(self, district_name: str, resource_name: str, quantity: int) -> bool:
        """Dépense une ressource d'un quartier. Retourne True si réussi."""
        district = self.districts.get(district_name)
        if district:
            return district.spend_resource(resource_name, quantity)
        return False
    
    # === Recherche ===
    
    def get_all_npcs(self) -> list:
        """Récupère tous les PNJ de la ville."""
        npcs = []
        for district in self.districts.values():
            npcs.extend(district.npcs)
        return npcs
    
    def get_all_buildings(self) -> list[Building]:
        """Récupère tous les bâtiments de la ville."""
        buildings = []
        for district in self.districts.values():
            buildings.extend(district.buildings.values())
        return buildings
    
    def find_npc_by_name(self, name: str):
        """Cherche un PNJ par son nom dans toute la ville."""
        for district in self.districts.values():
            npc = district.find_npc(name)
            if npc:
                return npc
        return None
    
    def find_building_by_name(self, name: str) -> Building | None:
        """Cherche un bâtiment par son nom dans toute la ville."""
        for district in self.districts.values():
            building = district.get_building(name)
            if building:
                return building
        return None
    
    def find_building_by_type(self, b_type: Build_type) -> list[Building]:
        """Cherche tous les bâtiments d'un certain type."""
        result = []
        for district in self.districts.values():
            for building in district.buildings.values():
                if building.type == b_type:
                    result.append(building)
        return result

    # === Info ===

    def get_info(self) -> dict:
        """Retourne les informations de la ville."""
        return {
            "name": self.name,
            "population": self.population,
            "wealth": self.wealth,
            "reputation": self.reputation,
            "districts": {name: d.get_info() for name, d in self.districts.items()},
            "total_buildings": len(self.get_all_buildings()),
            "total_npcs": len(self.get_all_npcs()),
            "travel_destinations": self.get_travel_destinations(),
            "entry_district": self.entry_district.name if self.entry_district else None
        }
    
    def __repr__(self) -> str:
        return f"Town({self.name!r}, pop={self.population}, {len(self.districts)} districts)"
