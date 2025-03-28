from ..character import Character

class Fight:
    def __init__(self, **fighters: dict[str, list[Character]]):
        """Initialise le combat avec les équipes de personnages."""
        if not fighters:
            raise ValueError("Il doit y avoir au moins une équipe.")
        
        for team_name, team_members in fighters.items():
            if not all(isinstance(player, Character) for player in team_members):
                raise ValueError(f"Tous les membres de '{team_name}' doivent être des instances de Character.")

        self.fighter = fighters
        self.team = fighters.copy()
        self.round_number = 1
