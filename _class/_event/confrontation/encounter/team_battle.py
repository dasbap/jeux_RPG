

from random import shuffle
from typing import List, Union

from _class._event.confrontation.encounter.fight import Fight
from _class.character import Character
from _class.res.team.alliance import Alliance
from _class.res.team.team import Team


class TeamBattle:
    def __init__(self, *teams: Union[List['Team'], 'Team']):
        """Initialize a team battle with multiple teams or team lists.
        
        Args:
            *teams: Variable number of teams or lists of teams participating in the battle
        """
        if len(teams) < 2:
            raise RuntimeError("At least 2 teams required for battle")
        
        self.teams: List['Team'] = []
        for t in teams:
            if isinstance(t, list):
                self.teams.extend(t)
            else:
                self.teams.append(t)
        
        self.fights: List['Fight'] = []
        self.alliances: List['Alliance'] = []
        self._format_battle()
    
    def _format_battle(self) -> None:
        """Organise les équipes en alliances et configure les combats"""
        tmp_alliances: List['Alliance'] = []
        
        for team in self.teams:
            if any(team in alliance.get_allies() for alliance in tmp_alliances):
                continue
                
            allies = {team} | set(team.get_allies())
            
            related_alliances = [
                a for a in tmp_alliances
                if any(ally in a.get_allies() for ally in allies)
            ]
            
            if related_alliances:
                main_alliance = related_alliances[0]
                for alliance in related_alliances[1:]:
                    for member in alliance.get_allies():
                        main_alliance.add_member(member)
                    tmp_alliances.remove(alliance)
                
                for ally in allies:
                    if ally not in main_alliance.get_allies():
                        main_alliance.add_member(ally)
            else:
                alliance_name = f"Alliance-{len(tmp_alliances)+1}"
                new_alliance = Alliance(alliance_name)
                for ally in allies:
                    new_alliance.add_member(ally)
                    new_alliance.add_ally(ally)
                tmp_alliances.append(new_alliance)
        
        self.alliances = tmp_alliances
        self._setup_fights()
    
    def _setup_fights(self) -> None:
        """Configure les combats entre alliances ennemies"""
        self.fights.clear()
        
        for i, alliance1 in enumerate(self.alliances):
            for alliance2 in self.alliances[i+1:]:
                if self._are_enemies(alliance1, alliance2):
                    fight_name = f"{alliance1.name} vs {alliance2.name}"
                    self.fights.append(Fight(alliance1, alliance2, fight_name))
                    alliance1.add_enemy(alliance2)
    
    def _are_enemies(self, a1: 'Alliance', a2: 'Alliance') -> bool:
        """Détermine si deux alliances sont ennemies (non-alliées par défaut)"""
        if a1 == a2:
            return False
            
        # Crée un set des alliés pour une recherche plus rapide
        a2_allies = {team for team in a2.get_allies()}
        
        # Vérifie si au moins un membre de a1 est allié avec un membre de a2
        for team1 in a1.get_allies():
            if team1 in a2_allies:
                return False
                
        # Aucune alliance trouvée, donc elles sont ennemies
        return True
    
    def get_team_alliance(self, team: 'Team') -> 'Alliance':
        """Trouve l'alliance d'une équipe"""
        for alliance in self.alliances:
            if team in alliance.get_allies():
                return alliance
        raise ValueError(f"Team {team} not found in any alliance")
    
    def is_over(self) -> bool:
        """Vérifie si la bataille est terminée"""
        alliance_fighter_alive : list[Character] = []
        for alliance in self.alliances:
            for fighter in alliance.get_fighters():
                if fighter.is_alive():
                    alliance_fighter_alive.append(fighter)
                    
        for fighter in alliance_fighter_alive:
            for other_fighter in alliance_fighter_alive:
                if fighter == other_fighter: continue
                if fighter.team not in self.get_team_alliance(other_fighter.team).get_enemies():
                    return False
        return True
    
    def auto_battle(self):
        shuffle(self.fights)
        for fight in self.fights:
            fight.start_round(False)
        if not self.is_over():
            for fight in self.fights:
                fight.rest()
                self.auto_battle()