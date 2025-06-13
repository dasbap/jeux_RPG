from typing import List, Optional, Union

from _class.character import Character
from _class.res.team.team import Team


class Alliance(Team):
    """
    Special type of Team that doesn't modify Character.team references.
    Used for temporary groupings in fights.
    """
    
    def __init__(self, name: str = "", members: List[Union[Character, Team]] = None) -> None:
        """Initialize an Alliance without modifying Character.team references."""
        self.name = name or f"Alliance-{len(Team.all_teams) + 1}"
        self.fighters: List[Character] = []
        self.allies: List[Team] = []
        self.enemies: List[Team] = []
        self.leader: Optional[Character] = None
        
        if members:
            for member in members:
                self.add_member(member)
    
    def add_member(self, member: Union[Character, Team]) -> None:
        """Add a member to the alliance without changing its team affiliation."""
        if isinstance(member, Character):
            if member not in self.fighters:
                self.fighters.append(member)
        elif isinstance(member, Team):
            for fighter in member.fighters:
                if fighter not in self.fighters:
                    self.fighters.append(fighter)
        else:
            raise TypeError("Alliance members must be Character or Team instances")
    
    def remove_member(self, member: Union[Character, Team]) -> None:
        """Remove a member from the alliance."""
        if isinstance(member, Character):
            if member in self.fighters:
                self.fighters.remove(member)
        elif isinstance(member, Team):
            for fighter in member.fighters:
                if fighter in self.fighters:
                    self.fighters.remove(fighter)
    
    def __contains__(self, fighter):
        is_in = super().__contains__(fighter)
        if not is_in:
            is_in = fighter in self.get_allies()
        return is_in
    
    def __str__(self) -> str:
        return f"Alliance '{self.name}' ({len(self.fighters)} members)"