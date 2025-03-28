from ..character import Character

class Fight:
    def __init__(self, **fighters: dict[str, list[Character]]):
        """Initializes the fight with teams of characters."""
        if not fighters:
            raise ValueError("At least one team must be provided.")
        
        for team_name, team_members in fighters.items():
            if not all(isinstance(player, Character) for player in team_members):
                raise ValueError(f"All members of '{team_name}' must be Character instances.")

        self.fighter = fighters
        self.team = fighters.copy()
        self.round_number = 1
