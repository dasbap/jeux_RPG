from _class._event.fight import Character, Fight

class Duel(Fight):
    def __init__(self, player1: Character, player2: Character):
        super().__init__(team_1=[player1], team_2=[player2])
        self.bot_entity = []
        self.playable_entity = []
        self.team_active : int = 0
        self.controlled_entities: dict[str, list[Character]] = {
            "controlled": self.playable_entity,
            "bot": self.bot_entity
        }
    
    def add_to_controlled_entities(self, entity: Character, key: str) -> None:
        """Ajoute une entité à la liste correspondante dans controlled_entities."""
        if key not in self.controlled_entities:
            raise ValueError(f"Invalid key '{key}'. Must be 'controlled' or 'bot'.")
        self.controlled_entities[key].append(entity)

    def start(self):
        while not self.end_fight():
            self.round()
            self.team_active = (self.team_active + 1) %2
    
    def round(self):
        for character in self.get_team():
            if not isinstance(character, Character) : pass
            print(f"{character.name} turn:")
            if character in self.controlled_entities["controlled"]:
                print(f"you can use {character.get_skill_dict()} or rest")
                action_user = input("what do you do : ")
                if action_user.lower() == "rest":
                    character.gain_energie(5)
                    continue
                skill = character.get_skill(action_user)
                target_list : list[Character] = self.get_team() + self.get_opposing_team()
                
                target_names = [t.name for t in target_list] 

                target = input(f"You can target: {', '.join(target_names)}\nWho do you target: ")
                selected_target = next((t for t in target_list if t.name == target), None)
                
                skill.action(character, selected_target)
                continue
            if character in self.controlled_entities["bot"]:
                print(f"{character.name} turn:")
                action_bot = any[self.get_opposing_team()]
                print(action_bot)
                skill = character.get_skill(action_bot["skill"])
                selected_target = next((t for t in self.get_team() + self.get_opposing_team() if t.name == action_bot["target"]), None)
                skill.action(character, selected_target)
                continue

    def end_fight(self) -> bool:
        """Checks if one of the teams is completely defeated."""
        return not any(player.is_alive() for player in self.team["team_1"]) or not any(player.is_alive() for player in self.team["team_2"])

    def player_action(self, player: Character, action_user: str, target: Character):
        """Handles the player's action in a round."""
        if action_user.lower() == "rest":
            player.gain_energie(5)
            return f"{player.name} rests and regenerates HP."

        try:
            skill = player.get_skill(action_user)
        except KeyError:
            return f"Skill '{action_user}' not found. Turn skipped."

        pass_target = False 

        for mod in self.controlled_entities:
            entity = self.controlled_entities[mod]

            if any(character.name == target.name for character in entity):
                pass_target = True
        
        if not pass_target:
            raise ValueError(f"{target.name} is not a fighter or not controlled.")
        
        print(skill.get_action(player, target))
        print(target)
        return f"{player.name} use {skill.name} on {target.name}"
    
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
    
    def get_team(self) -> dict[str,list[Character]]:
        """Returns the list of characters in both teams."""
        return self.team[f"team_{self.team_active + 1}"]
