
from typing import List, Optional, Union

from _class.character import Character


class Team():
    """Represents a team of characters with alliance and enemy relationships.
    
    Attributes:
        all_teams (List['Team']): Class attribute tracking all existing teams.
        DEFAULT_NAME_FORMAT (str): Format for default team names.
    """
    
    all_teams: List['Team'] = []
    DEFAULT_NAME_FORMAT: str = "Team {index}"
    
    def __init__(self, name: str = "", Team_member : Union[list[Character], Character] = [] ) -> None:
        """Initialize a new Team.
        
        Args:
            name: Optional name for the team. If not provided, a default name 
                    will be generated based on the number of existing teams.
                    
        Raises:
            ValueError: If the team name is already taken.
        """
        self._validate_name_uniqueness(name)
        self.leader : Character = None
        self.name = name or self._generate_default_name()
        self.fighters: List[Character] = []
        self.allies: List[Team] = []
        self.enemies: List[Team] = []
        if not isinstance(Team_member, Character):
            for member in Team_member:
                self.add_fighter(member)
        else:
            self.change_leader(Team_member)
        Team.all_teams.append(self)
    
    def _validate_name_uniqueness(self, name: str) -> None:
        """Validate that the team name is unique.
        
        Args:
            name: Proposed team name to validate.
            
        Raises:
            ValueError: If name is already taken by another team.
        """
        if name and any(team.name == name for team in Team.all_teams):
            raise ValueError(f"Team name '{name}' is already in use")
    
    def _generate_default_name(self) -> str:
        """Generate a default team name based on existing team count."""
        return self.DEFAULT_NAME_FORMAT.format(index=len(Team.all_teams) + 1)
    
    def __str__(self) -> str:
        """Return a string representation of the team."""
        return (f"Team '{self.name}': {len(self.fighters)} fighters, "
                f"{len(self.allies)} allies, {len(self.enemies)} enemies")
    
    def __repr__(self) -> str:
        """Return an unambiguous string representation of the team."""
        return f"<Team name='{self.name}' id={id(self)}>"
    
    def __contains__(self, fighter) -> bool:
        return fighter in self.get_fighters()
    
    def destroy(self) -> None:
        """Completely destroy the team and clean up all relationships.
        
        This removes all references to the team from other teams and characters.
        """
        # Remove from global team list
        if self in Team.all_teams:
            Team.all_teams.remove(self)
        
        # Clean up relationships with other teams
        for team in Team.all_teams:
            if self in team.allies:
                team.allies.remove(self)
            if self in team.enemies:
                team.enemies.remove(self)
        
        # Clean up fighter relationships
        for fighter in self.fighters:
            fighter.team = None
        
        # Clear all internal state
        self.fighters.clear()
        self.allies.clear()
        self.enemies.clear()
    
    def add_fighter(self, fighter: Character) -> None:
        """Add a fighter to the team.
        
        Args:
            fighter: The Character to add to the team.
            
        Raises:
            ValueError: If fighter is already in a different team or invalid.
            TypeError: If fighter is not a Character instance.
        """
        if not isinstance(fighter, Character):
            raise TypeError("Can only add Character instances to a team")
        
        if fighter.team is self:
            raise ValueError(f"{fighter.name} is already in this team")
        
        if fighter.team is not None:
            raise ValueError(
                f"{fighter.name} already belongs to team {fighter.team.name}"
            )
        
        self.fighters.append(fighter)
        fighter.team = self
    
    def change_leader(self, leader: Character) -> None:
        if leader.team:
            if leader.team != self:
                raise RuntimeError("Can't be the leader of a team if his not in")
            elif self.leader is leader:
                raise RuntimeError(f"{leader.name} is already the leader of {self.name}")
        else:
            self.add_fighter(leader)
        
        self.leader = leader

    
    def remove_leader(self):
        if self.leader:
            self.leader = None
        else:
            raise RuntimeError(f"the team {self.name} as no leader")
    
    def remove_fighter(self, fighter: Character) -> None:
        """Remove a fighter from the team.
        
        Args:
            fighter: The Character to remove from the team.
            
        Raises:
            ValueError: If fighter is not in this team.
        """
        if fighter not in self.fighters:
            raise ValueError(f"{fighter.name} is not in this team")
        if fighter is self.leader:
            self.remove_leader()
        self.fighters.remove(fighter)
        fighter.team = None
    
    def add_ally(self, ally: 'Team', mutual: bool = True) -> None:
        """Form an alliance with another team.
        
        Args:
            ally: The team to ally with.
            mutual: If True, the alliance will be reciprocal.
            
        Raises:
            ValueError: If teams are already allied or are enemies.
            TypeError: If ally is not a Team instance.
        """
        if not isinstance(ally, Team):
            raise TypeError("Can only form alliances with other Team instances")
        
        if ally is self:
            raise ValueError("Cannot form alliance with oneself")
        
        if ally in self.allies:
            raise ValueError(f"Already allied with {ally.name}")
        
        if ally in self.enemies:
            raise ValueError(f"Cannot ally with enemy team {ally.name}")
        
        self.allies.append(ally)
        
        if mutual:
            ally.add_ally(self, mutual=False)
    
    def remove_ally(self, ally: 'Team', mutual: bool = True) -> None:
        """Dissolve an alliance with another team.
        
        Args:
            ally: The team to remove from allies.
            mutual: If True, the dissolution will be reciprocal.
            
        Raises:
            ValueError: If teams are not currently allied.
        """
        if ally not in self.allies:
            raise ValueError(f"Not allied with {ally.name}")
        
        self.allies.remove(ally)
        
        if mutual:
            ally.remove_ally(self, mutual=False)
    
    def add_enemy(self, enemy: 'Team', mutual: bool = True) -> None:
        """Declare another team as an enemy.
        
        Args:
            enemy: The team to declare as enemy.
            mutual: If True, the enmity will be reciprocal.
            
        Raises:
            ValueError: If teams are allies.
            TypeError: If enemy is not a Team instance.
        """
        if not isinstance(enemy, Team):
            raise TypeError("Can only declare other Team instances as enemies")
        
        if enemy is self:
            raise ValueError("Cannot declare oneself as enemy")
        
        if enemy in self.enemies:
            return
        
        if enemy in self.allies:
            raise ValueError(f"Cannot declare ally {enemy.name} as enemy")
        
        self.enemies.append(enemy)
        
        if mutual:
            enemy.add_enemy(self, mutual=False)
    
    def remove_enemy(self, enemy: 'Team', mutual: bool = True) -> None:
        """Remove enmity with another team.
        
        Args:
            enemy: The team to remove from enemies.
            mutual: If True, the removal will be reciprocal.
            
        Raises:
            ValueError: If teams are not currently enemies.
        """
        if enemy not in self.enemies:
            raise ValueError(f"Not enemies with {enemy.name}")
        
        self.enemies.remove(enemy)
        
        if mutual:
            enemy.remove_enemy(self, mutual=False)
    
    def rename(self, new_name: str) -> None:
        """Change the team's name.
        
        Args:
            new_name: The new name for the team.
            
        Raises:
            ValueError: If new_name is already taken by another team.
        """
        self._validate_name_uniqueness(new_name)
        self.name = new_name
    
    def is_ally(self, ally : Union[Character, 'Team']) -> bool:
        """Check if a fighter belongs to an allied team.
        
        Args:
            ally: The Character or Team to check.
            
        Returns:
            bool: True if ally belongs to an allied team.
            
        Raises:
            TypeError: If ally is not a Character or a Team instance.
        """
            
        if isinstance(ally, Character):
            return (self == ally.team or ally.team in self.allies if ally.team else False)
        if isinstance(ally, Team):
            return ally in self.get_allies()
        raise TypeError("Can only check Character or Team instances")
    
    def is_enemy(self, fighter: Character) -> bool:
        """Check if a fighter belongs to an enemy team.
        
        Args:
            fighter: The Character to check.
            
        Returns:
            bool: True if the fighter belongs to an enemy team.
            
        Raises:
            TypeError: If fighter is not a Character instance.
        """
        if not isinstance(fighter, Character):
            raise TypeError("Can only check Character instances")
        
        return fighter.team in self.enemies if fighter.team else False
    
    def is_teammate(self, fighter: Character) -> bool:
        """Check if a fighter belongs to this team.
        
        Args:
            fighter: The Character to check.
            
        Returns:
            bool: True if the fighter belongs to this team.
            
        Raises:
            TypeError: If fighter is not a Character instance.
        """
        if not isinstance(fighter, Character):
            raise TypeError("Can only check Character instances")
        
        return fighter.team is self
    
    def get_allies(self) -> List['Team']:
        """Get a copy of the list of allied teams."""
        return self.allies.copy()
    
    def get_enemies(self) -> List['Team']:
        """Get a copy of the list of enemy teams."""
        return self.enemies.copy()
    
    def get_fighters(self) -> List[Character]:
        """Get a copy of the list of the fighter in the Team."""
        return self.fighters.copy()
    
    def merge_with(self, other: 'Team') -> None:
        """Merge another team into this one.
        
        Args:
            other: The team to merge into this one.
            
        Raises:
            TypeError: If other is not a Team instance.
            ValueError: If trying to merge with oneself.
        """
        if not isinstance(other, Team):
            raise TypeError("Can only merge with other Team instances")
        
        if other is self:
            raise ValueError("Cannot merge with oneself")
        
        # Transfer fighters
        for fighter in other.fighters.copy():
            self.add_fighter(fighter)
        
        # Transfer alliances
        for ally in other.allies.copy():
            if ally is not self and ally not in self.allies:
                self.add_ally(ally)
        
        # Transfer enmities
        for enemy in other.enemies.copy():
            if enemy is not self and enemy not in self.enemies:
                self.add_enemy(enemy)
        
        # Clean up the merged team
        Team.remove_team(other)
    
    def any_alive(self) -> bool:
        for fighter in self.get_fighters():
            if fighter.is_alive() : return True
        else:
            return False
    
    @classmethod
    def remove_team(cls, team_to_remove: 'Team') -> None:
        """Remove a team from the global team list and clean up relationships.
        
        Args:
            team_to_remove: The team to remove.
            
        Raises:
            TypeError: If team_to_remove is not a Team instance.
        """
        if not isinstance(team_to_remove, Team):
            raise TypeError("Can only remove Team instances")
        
        if team_to_remove in cls.all_teams:
            cls.all_teams.remove(team_to_remove)
        
        # Clean up relationships in other teams
        for team in cls.all_teams:
            if team_to_remove in team.allies:
                team.allies.remove(team_to_remove)
            if team_to_remove in team.enemies:
                team.enemies.remove(team_to_remove)
    
    @classmethod
    def get_team_by_name(cls, name: str) -> Optional['Team']:
        """Find a team by its name.
        
        Args:
            name: The name of the team to find.
            
        Returns:
            Optional[Team]: The team with matching name, or None if not found.
        """
        return next((team for team in cls.all_teams if team.name == name), None)
    
    @classmethod
    def team_exists(cls, name: str) -> bool:
        """Check if a team with the given name exists.
        
        Args:
            name: The name to check.
            
        Returns:
            bool: True if a team with this name exists.
        """
        return any(team.name == name for team in cls.all_teams)