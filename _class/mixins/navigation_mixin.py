"""jeuxRPG navigation mixin.

Keeps *place-based* navigation (town/district/building) via :class:`Navigator`.

The old world-map coordinate system (x/y + Coords + grid movement) has been
removed in favor of higher-level positions (dimensions/lieux).
"""

from typing import TYPE_CHECKING, Optional, List, Tuple

if TYPE_CHECKING:
    from jeuxRPG._class.character import Character
    from jeuxRPG._class.place.town import Town
    from jeuxRPG._class.place.district import District
    from jeuxRPG._class.place.building import Building


class NavigationMixin:
    """
    Mixin providing navigation and location functionality.
    
    Handles:
    - Current location tracking (town/district/building)
    - World map coordinates
    - Movement between buildings, districts, and towns
    - Location history
    - Spawn mechanics
    """
    
    def _init_navigation(self: 'Character') -> None:
        """Initialize navigation system for character."""
        from jeuxRPG._class.place.navigation import Navigator
        self._navigator = Navigator()
        # Precise location metadata (level + name)
        self.location_level: str = "world"  # e.g., 'world', 'kingdom', 'town', 'district', 'building'
        self.location_name: str = ""  # Human-readable name of current level/map
    
    @property
    def navigator(self: 'Character'):
        """Get the character's navigator, initializing if needed."""
        from jeuxRPG._class.place.navigation import Navigator
        if not hasattr(self, '_navigator') or self._navigator is None:
            self._navigator = Navigator()
        return self._navigator
    
    @property
    def location(self: 'Character'):
        """Get the character's current location."""
        return self.navigator.location
    
    # === Position Info ===
    
    def where_am_i(self: 'Character') -> str:
        """
        Get the current location as a readable string.
        
        Returns:
            Full location path (e.g., "Village > Market > Blacksmith")
        """
        return self.navigator.where_am_i()
    
    def get_current_town(self: 'Character') -> Optional['Town']:
        """Get the current town, or None if in wilderness."""
        return self.navigator.get_current_town()
    
    def get_current_district(self: 'Character') -> Optional['District']:
        """Get the current district, or None if not in one."""
        return self.navigator.get_current_district()
    
    def get_current_building(self: 'Character') -> Optional['Building']:
        """Get the current building, or None if not in one."""
        return self.navigator.get_current_building()
    
    def is_in_town(self: 'Character') -> bool:
        """Check if character is in a town."""
        return self.navigator.get_current_town() is not None
    
    def is_in_building(self: 'Character') -> bool:
        """Check if character is inside a building."""
        return self.navigator.get_current_building() is not None
    
    def is_in_wilderness(self: 'Character') -> bool:
        """Check if character is in the wilderness (no town)."""
        return self.navigator.get_current_town() is None
    
    # === Movement Options ===
    
    def get_movement_options(self: 'Character') -> dict:
        """
        Get all available movement options.
        
        Returns:
            Dict with keys: 'buildings', 'districts', 'towns'
        """
        return self.navigator.get_movement_options()
    
    def can_enter(self: 'Character', building_name: str) -> bool:
        """Check if character can enter a building."""
        return self.navigator.can_enter_building(building_name)
    
    def can_go_to(self: 'Character', district_name: str) -> bool:
        """Check if character can go to a district."""
        return self.navigator.can_go_to_district(district_name)
    
    def can_travel_to(self: 'Character', town_name: str) -> bool:
        """Check if character can travel to a town."""
        return self.navigator.can_travel_to(town_name)
    
    # === Movement Actions ===
    
    def enter_building(self: 'Character', building_name: str) -> Tuple[bool, str]:
        """
        Enter a building in the current district.
        
        Args:
            building_name: Name of the building to enter
            
        Returns:
            (success, message)
        """
        return self.navigator.enter_building(building_name)
    
    def exit_building(self: 'Character') -> Tuple[bool, str]:
        """
        Exit the current building.
        
        Returns:
            (success, message)
        """
        return self.navigator.exit_building()
    
    def go_to_district(self: 'Character', district_name: str) -> Tuple[bool, str]:
        """
        Move to another district in the current town.
        
        Args:
            district_name: Name of the district to go to
            
        Returns:
            (success, message)
        """
        return self.navigator.go_to_district(district_name)
    
    def travel_to(self: 'Character', town_name: str) -> Tuple[bool, str]:
        """
        Travel to another town.
        
        Args:
            town_name: Name of the town to travel to
            
        Returns:
            (success, message)
        """
        return self.navigator.travel_to(town_name)
    
    def spawn_at(self: 'Character', town: 'Town') -> None:
        """
        Spawn the character at a town's entry point.
        
        Args:
            town: Town to spawn at
        """
        self.navigator.spawn_at(town)
        # Update precise location metadata
        self.location_level = "town"
        self.location_name = getattr(town, "name", "")
    
    # === History ===
    
    def get_travel_history(self: 'Character', last_n: int = 10) -> List[str]:
        """
        Get recent travel history.
        
        Args:
            last_n: Number of recent events to return
            
        Returns:
            List of travel events
        """
        return self.navigator.get_history(last_n)
    
    def get_navigation_info(self: 'Character') -> dict:
        """
        Get complete navigation information.
        
        Returns:
            Dict with location, type, options, and history
        """
        return self.navigator.get_info()
