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
        """Vérifie si l'un des deux groupes est complètement défait."""
        return not any(player.is_alive() for player in self.team["team_1"]) or not any(player.is_alive() for player in self.team["team_2"])

    def round(self):
        """Gère un round de combat, en alternant les équipes actives."""
        active_team_key = f"team_{self.team_active + 1}"
        active_team = self.team[active_team_key]

        for entity in active_team:
            if not isinstance(entity, Character):
                raise ValueError("Le type de joueur est invalide.")

            if not entity.is_alive():
                continue  
            
            skill_usable = entity.get_skill_dict()
            if not skill_usable:
                print(f"{entity.name} n'a aucune compétence disponible.")
                continue
            
            print(f"Compétences disponibles : {list(skill_usable.keys())}")
            action_user = input("Choisis une compétence ou tape 'rest' pour régénérer de l'énergie : ").strip()
            target_name = input(f"Choisis une cible parmi {[p.name for p in self.get_opposing_team()]} ou tape 'Me' pour toi-même : ").strip()

            if action_user.lower() == "rest":
                entity.gain_energie(5)
                print(f"{entity.name} se repose et régénère de l'énergie.")
                continue  # Passer au prochain personnage

            # Vérifie si la compétence est valide
            try:
                skill = entity.get_skill(action_user)
            except KeyError:
                print(f"Compétence '{action_user}' introuvable. Tour passé.")
                continue

            # Vérifie si la cible est un personnage valide
            target = self.get_entity_by_name(target_name)
            if target:
                # Applique l'action de la compétence
                skill.get_action(entity, target)
            else:
                print(f"{target_name} n'est pas une cible valide.")
        
        # Change l'équipe active après un round
        self.team_active = (self.team_active + 1) % 2  

    def player_action(self, player: Character, action_user: str, target: Character):
        """Gère l'action du joueur lors d'un round."""
        if action_user.lower() == "rest":
            player.gain_energie(5)
            print(f"{player.name} se repose et régénère de l'énergie.")
            return

        try:
            skill = player.get_skill(action_user)
        except KeyError:
            print(f"Compétence '{action_user}' introuvable. Tour passé.")
            return

        if not isinstance(target, Character):  # Vérification du type de la cible
            raise ValueError("La cible doit être une instance de Character.")
        
        # Applique la compétence
        skill.get_action(player, target)

    def get_entity_by_name(self, name: str) -> Character:
        """Trouve un personnage par son nom dans une équipe."""
        for team_key, team in self.team.items():
            for player in team:
                if not isinstance(player, Character):
                    raise ValueError(f"{name} n'est pas une instance valide de Character.")
                if player.name == name:
                    return player
        raise ValueError(f"{name} est inconnu. Cibles disponibles : {[p.name for t in self.team.values() for p in t]}")

    def get_opposing_team(self):
        """Retourne la liste des personnages dans l'équipe adverse."""
        return self.team[f"team_{(self.team_active + 1) % 2 + 1}"]
