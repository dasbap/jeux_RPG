from _class._event.fight import Character, Fight

class Duel(Fight):
    def __init__(self, player1: Character, player2: Character):
        super().__init__(team_1=[player1], team_2=[player2])
        
        self.team_active: int = 0 
        self.bot_entity = []
        self.playable_entity = []
        
        self.controlled_entities: dict[str, list[Character]] = {
            "controlled": self.playable_entity,
            "bot": self.bot_entity
        }

    def start(self):
        while not self.end_fight():
            self.round()

    def end_fight(self) -> bool:
        """Checks if one of the teams is completely defeated."""
        return not any(player.is_alive() for player in self.team["team_1"]) or not any(player.is_alive() for player in self.team["team_2"])

    def round(self):
        """Handles a round of combat, switching active teams."""
        active_team_key = f"team_{self.team_active + 1}"
        active_team = self.team[active_team_key]

        for entity in active_team:
            if not isinstance(entity, Character):
                raise ValueError("Invalid character type.")

            if not entity.is_alive():
                continue  
            
            skill_usable = entity.get_skill_dict()
            if not skill_usable:
                print(f"{entity.name} has no skills available.")
                continue
            
            print(f"You can use: {list(skill_usable.keys())}")
            action_user = input("Choose a skill to use or type 'rest' to regenerate mana: ").strip()
            target_name = input(f"Choose your target among {[p.name for p in self.get_opposing_team()]} or type 'Me' for yourself: ").strip()

            self.player_action(entity, action_user, target_name)
        
        self.team_active = (self.team_active + 1) % 2  

    def player_action(self, player: Character, action_user: str, target: Character):
        """Handles the player's action in a round."""
        if action_user.lower() == "rest":
            player.gain_energie(5)
            return f"{player.name} rests and regenerates HP."

        try:
            skill = player.get_skill(action_user)
        except KeyError:
            return  f"Skill '{action_user}' not found. Turn skipped."

        if not target in self.controlled_entities: raise 
        
        if target:
            skill.get_action(player, target)

    def get_entity_by_name(self, name: str) -> Character:
        """Finds a character by name in any team."""
        for team_key, team in self.team.items():
            for player in team:
                if not isinstance(player, Character):
                    raise ValueError(f"Player {name} is not a valid Character instance")
                if player.name == name:
                    return player
        raise ValueError(f"{name} is unknown. Available targets: {[p.name for t in self.team.values() for p in t]}")

    def get_opposing_team(self):
        """Returns the list of characters in the opposing team."""
        return self.team[f"team_{(self.team_active + 1) % 2 + 1}"]
