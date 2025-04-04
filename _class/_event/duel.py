from _class._event.fight import Character, Fight
import random
from ..skill import Skill

class Duel(Fight):
    def __init__(self, player1: Character, player2: Character):
        super().__init__(team_1=[player1], team_2=[player2])
        self.bot_entity = []
        self.playable_entity = []
        self.team_active: int = 0
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
            self.team_active = (self.team_active + 1) % 2
    
    def round(self):
        for character in self.get_team():
            if not isinstance(character, Character):
                continue
            
            print(f"{character.name}'s turn:")
            
            if character in self.controlled_entities["controlled"]:
                print(f"You can use {character.get_skill_dict()} or rest")
                action_user = input("What do you do: ")
                
                if action_user.lower() == "rest":
                    character.gain_energie(5)
                    continue
                
                try:
                    skill = character.get_skill(action_user)
                except KeyError:
                    print(f"Skill '{action_user}' not found. Turn skipped.")
                    continue
                
                target_list: list[Character] = self.get_opposing_team() + self.get_team()
                target_names = [t.name for t in target_list if t.is_alive()]
                
                target = input(f"You can target: {', '.join(target_names)}\nWho do you target: ")
                selected_target = next((t for t in target_list if t.name == target), None)
                
                if selected_target is None:
                    print("Invalid target. Turn skipped.")
                    continue
                
                skill.action(character, selected_target)
                continue
            
            if character in self.controlled_entities["bot"]:
                print(f"{character.name}'s turn:")
                
                focus_bot: Character = next((char for char in self.get_opposing_team() if char.is_alive()), None)
                
                if focus_bot is None:
                    raise ValueError("Aucun personnage vivant trouvé dans l'équipe adverse.")
                
                print(f"{character.name} will attack {focus_bot.name}")
                
                if not character.class_skills_dict:
                    raise ValueError(f"{character.name} doesn't have any skills.")
                
                skill_list = []
                for skills in character.class_skills_dict.values():
                    skill_list.extend(skills)
                
                if not skill_list:
                    raise ValueError(f"{character.name} has no available skills.")
                
                skill: Skill = random.choice(skill_list)
                skill.action(character, focus_bot)
                continue

    
    def end_fight(self) -> bool:
        """Checks if one of the teams is completely defeated."""
        return not any(player.is_alive() for player in self.teams["team_1"]) or not any(player.is_alive() for player in self.teams["team_2"])
    
    def player_action(self, player: Character, action_user: str, target: Character):
        """Handles the player's action in a round."""
        if action_user.lower() == "rest":
            player.gain_energie(5)
            return f"{player.name} rests and regenerates HP."
        
        try:
            skill = player.get_skill(action_user)
        except KeyError:
            return f"Skill '{action_user}' not found. Turn skipped."
        
        if target not in sum(self.controlled_entities.values(), []):
            raise ValueError(f"{target.name} is not a valid target.")
        
        skill.action(player, target)
        return f"{player.name} uses {skill.name} on {target.name}"
    
    def get_entity_by_name(self, name: str) -> Character:
        """Finds a character by name in any team."""
        for team_key, team in self.teams.items():
            for player in team:
                if player.name == name:
                    return player
        raise ValueError(f"{name} is unknown. Available targets: {[p.name for t in self.teams.values() for p in t]}")
    
    def get_opposing_team(self) -> list[Character]:
        """Returns the opposing team's characters."""
        return self.teams[f"team_{(self.team_active + 1) % 2 + 1}"]
    
    def get_team(self) -> list[Character]:
        """Returns the active team's characters."""
        return self.teams[f"team_{self.team_active + 1}"]
