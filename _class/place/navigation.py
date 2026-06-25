from __future__ import annotations
from typing import TYPE_CHECKING, Literal
from enum import Enum, auto

from jeuxRPG.i18n import t

if TYPE_CHECKING:
    from jeuxRPG._class.place.town import Town
    from jeuxRPG._class.place.district import District
    from jeuxRPG._class.place.building import Building


class LocationType(Enum):
    """Type de lieu où peut se trouver un personnage."""
    TOWN = auto()       # Dans une ville (pas de quartier précis)
    DISTRICT = auto()   # Dans un quartier
    BUILDING = auto()   # Dans un bâtiment
    WILDERNESS = auto() # En pleine nature (entre deux villes)


class Location:
    """
    Représente la position actuelle d'un personnage.
    
    Permet de savoir exactement où se trouve le joueur et de gérer
    ses déplacements entre les différents lieux.
    """
    
    def __init__(
        self,
        town: Town | None = None,
        district: District | None = None,
        building: Building | None = None
    ):
        self.town = town
        self.district = district
        self.building = building
    
    @property
    def location_type(self) -> LocationType:
        """Retourne le type de lieu actuel."""
        if self.building:
            return LocationType.BUILDING
        if self.district:
            return LocationType.DISTRICT
        if self.town:
            return LocationType.TOWN
        return LocationType.WILDERNESS
    
    @property
    def current_name(self) -> str:
        """Retourne le nom du lieu actuel."""
        if self.building:
            return self.building.name
        if self.district:
            return self.district.name
        if self.town:
            return self.town.name
        return t("nav.wilderness")
    
    def get_full_location(self) -> str:
        """Retourne la localisation complète sous forme de texte."""
        parts = []
        if self.town:
            parts.append(self.town.name)
        if self.district:
            parts.append(self.district.name)
        if self.building:
            parts.append(self.building.name)
        return " > ".join(parts) if parts else t("nav.wilderness")


class Navigator:
    """
    Gère les déplacements d'un personnage entre les lieux.
    
    Attributes:
        location: Position actuelle du personnage
    """
    
    def __init__(self, start_location: Location | None = None):
        self.location = start_location or Location()
        self._travel_history: list[str] = []
    
    # === Getters ===
    
    def where_am_i(self) -> str:
        """Retourne la description de la position actuelle."""
        return self.location.get_full_location()
    
    def get_current_town(self) -> Town | None:
        """Retourne la ville actuelle."""
        return self.location.town
    def get_current_district(self) -> District | None:
        """Retourne le quartier actuel."""
        return self.location.district
    
    def get_current_building(self) -> Building | None:
        """Retourne le bâtiment actuel."""
        return self.location.building
    
    # === Options de déplacement ===
    
    def get_movement_options(self) -> dict[str, list[str]]:
        """
        Retourne toutes les options de déplacement possibles.
        
        Returns:
            Dict avec clés: 'buildings', 'districts', 'towns'
        """
        options = {
            "buildings": [],
            "districts": [],
            "towns": []
        }
        
        # Si dans un bâtiment, on peut sortir dans le quartier
        if self.location.building and self.location.district:
            options["buildings"] = ["(sortir)"]
        
        # Si dans un quartier, on peut aller dans les bâtiments ou autres quartiers
        if self.location.district:
            options["buildings"] = self.location.district.get_accessible_buildings()
            options["districts"] = self.location.district.get_accessible_districts()
        
        # Si dans une ville (même dans un quartier), on peut voyager
        if self.location.town:
            options["towns"] = self.location.town.get_travel_destinations()
        
        return options
    
    def can_enter_building(self, building_name: str) -> bool:
        """Vérifie si on peut entrer dans un bâtiment."""
        if not self.location.district:
            return False
        return building_name in self.location.district.buildings
    
    def can_go_to_district(self, district_name: str) -> bool:
        """Vérifie si on peut aller dans un quartier."""
        if not self.location.district:
            # Si on est juste dans la ville, on peut aller n'importe quel quartier
            if self.location.town:
                return district_name in self.location.town.districts
            return False
        return self.location.district.can_go_to(district_name)
    
    def can_travel_to(self, town_name: str) -> bool:
        """Vérifie si on peut voyager vers une ville."""
        if not self.location.town:
            return False
        return self.location.town.can_travel_to(town_name)
    
    # === Déplacements ===
    
    def enter_building(self, building_name: str) -> tuple[bool, str]:
        """
        Entre dans un bâtiment.
        
        Returns:
            (success, message)
        """
        if not self.location.district:
            return False, t("nav.not_in_district")
        
        building = self.location.district.get_building(building_name)
        if not building:
            return False, t("nav.building_not_exists", building_name=building_name)
        
        from jeuxRPG._class.res.classType import Build_state
        if building.status == Build_state.DESTROY:
            return False, t("nav.building_destroyed", building_name=building_name)
        if building.status == Build_state.UNDER_CONSTRUCTION:
            return False, t("nav.building_under_construction", building_name=building_name)
        
        self.location.building = building
        self._add_history(t("nav.entered_building", building_name=building_name))
        return True, t("nav.enter_building", building_name=building_name)
    
    def exit_building(self) -> tuple[bool, str]:
        """Sort du bâtiment actuel."""
        if not self.location.building:
            return False, t("nav.not_in_building")
        
        building_name = self.location.building.name
        self.location.building = None
        self._add_history(t("nav.exited_building", building_name=building_name))
        return True, t("nav.exit_building", building_name=building_name)
    
    def go_to_district(self, district_name: str) -> tuple[bool, str]:
        """
        Va dans un autre quartier.
        
        Returns:
            (success, message)
        """
        if not self.location.town:
            return False, t("nav.not_in_town")
        
        # Sortir du bâtiment d'abord si nécessaire
        if self.location.building:
            self.exit_building()
        
        # Vérifier si le quartier est accessible
        if self.location.district and not self.can_go_to_district(district_name):
            return False, t("nav.cannot_go_district", district_name=district_name)
        
        district = self.location.town.get_district(district_name)
        if not district:
            return False, t("nav.district_not_exists", district_name=district_name)
        
        old_district = self.location.district.name if self.location.district else t("nav.from_entrance")
        self.location.district = district
        self._add_history(t("nav.district_change", from_district=old_district, to_district=district_name))
        return True, t("nav.go_to_district", district_name=district_name)
    
    def travel_to(self, town_name: str) -> tuple[bool, str]:
        """
        Voyage vers une autre ville.
        
        Returns:
            (success, message)
        """
        if not self.location.town:
            return False, t("nav.must_be_in_town")
        
        if not self.can_travel_to(town_name):
            return False, t("nav.cannot_travel", town_name=town_name)
        
        destination = self.location.town.connected_towns.get(town_name)
        if not destination:
            return False, t("nav.town_not_exists", town_name=town_name)
        
        old_town = self.location.town.name
        
        # Réinitialiser la position
        self.location.building = None
        self.location.district = destination.entry_district
        self.location.town = destination
        
        self._add_history(t("nav.travel_history", from_town=old_town, to_town=town_name))
        
        entry = destination.entry_district.name if destination.entry_district else t("nav.from_entrance")
        return True, t("nav.travel_to", town_name=town_name, entry=entry)
    
    def spawn_at(self, town: Town) -> None:
        """Place le personnage à l'entrée d'une ville (spawn initial)."""
        self.location.town = town
        self.location.district = town.entry_district
        self.location.building = None
        self._add_history(t("nav.spawn", town_name=town.name))
    
    # === Historique ===
    
    def _add_history(self, event: str) -> None:
        """Ajoute un événement à l'historique."""
        self._travel_history.append(event)
        # Garder seulement les 50 derniers
        if len(self._travel_history) > 50:
            self._travel_history = self._travel_history[-50:]
    
    def get_history(self, last_n: int = 10) -> list[str]:
        """Retourne les derniers déplacements."""
        return self._travel_history[-last_n:]
    
    # === Info ===
    
    def get_info(self) -> dict:
        """Retourne les informations de navigation."""
        return {
            "current_location": self.where_am_i(),
            "location_type": self.location.location_type.name,
            "options": self.get_movement_options(),
            "recent_history": self.get_history(5)
        }
    
    def __repr__(self) -> str:
        return f"Navigator(at={self.where_am_i()!r})"
