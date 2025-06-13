
from random import choice, shuffle
from typing import List, Optional, Union

from _class.character import Character
from _class.res.classType import SkillType
from _class.res.team.alliance import Alliance
from _class.res.team.team import Team


class Fight:
    """
    Manages a battle between alliances of attackers and defenders.
    All participants are grouped into Alliance instances that don't modify
    their original team affiliations.
    """
    
    def __init__(
        self,
        attackers: Union[List[Union[Character, Team]], Character, Team],
        defenders: Union[List[Union[Character, Team]], Character, Team],
        name: str = ""
    ) -> None:
        """Initialize a fight with participants grouped into Alliances."""
        self.attackers = Alliance(f"{name} Attackers", self._normalize_participants(attackers))
        self.defenders = Alliance(f"{name} Defenders", self._normalize_participants(defenders))
        self.attackers.add_enemy(self.defenders, mutual=True)
        self._winner: Optional[Alliance] = None
        self._validate_participants()
        self.round : int = 0
        self.can_play : List[Character]
        self.log_message : list[str] = []
        self._new_round()
    
    def clear_log(self) -> None:
        self.log_message = []
        
    def _normalize_participants(
        self,
        participants: Union[List[Union[Character, Team]], Character, Team]
    ) -> List[Union[Character, Team]]:
        """Normalize input into a list of Characters or Teams."""
        if participants is None:
            return []
        
        if isinstance(participants, (Character, Team)):
            return [participants]
        
        if isinstance(participants, list):
            return participants
        
        raise TypeError("Participants must be Character, Team, or list of them")
    
    def _validate_participants(self) -> None:
        """Ensure no character is on both sides."""
        attackers_chars = set(self.attackers.fighters)
        defenders_chars = set(self.defenders.fighters)
        
        common = attackers_chars & defenders_chars
        if common:
            names = ", ".join(c.name for c in common)
            raise ValueError(f"Characters cannot be on both sides: {names}")
    
    def add_attacker(self, participant: Union[Character, Team]) -> None:
        """Add a participant to the attackers alliance."""
        self._add_participant(participant, self.attackers)
    
    def add_defender(self, participant: Union[Character, Team]) -> None:
        """Add a participant to the defenders alliance."""
        self._add_participant(participant, self.defenders)
    
    def _add_participant(
        self,
        participant: Union[Character, Team],
        alliance: Alliance
    ) -> None:
        """Internal method to add participants to an alliance."""
        if isinstance(participant, (Character, Team)):
            alliance.add_member(participant)
            self._validate_participants()
        else:
            raise TypeError("Can only add Character or Team instances")
    
    def _new_round(self) -> None:
        self.can_play = self._get_alive_participant()
        self.round += 1

    def _get_alive_participant(self) -> list[Character]:
        return [c for c in self.get_all_individuals() if c.is_alive()]
    
    def who_next(self) -> Character:
        can_play = self.can_play
        can_play = [player for player in can_play if player.is_alive()]
        if can_play == [] : return None
        return choice(can_play)

    def get_all_individuals(self) -> List[Character]:
        """Get all unique characters involved in the fight."""
        return list(set(self.attackers.fighters + self.defenders.fighters))
    
    def get_original_teams(self) -> List[Team]:
        """Get all original teams of participants (excluding alliances)."""
        teams = set()
        
        for fighter in self.get_all_individuals():
            if fighter.team:
                teams.add(fighter.team)
        
        return list(teams)
    
    def _merge_and_shuffle_fighters(self) -> List[Character]:
        """Fusionne et mélange les combattants des deux alliances sans modifier les équipes d'origine.
        
        Returns:
            Liste mélangée de tous les combattants vivants des deux côtés
        """
        # 1. Fusion des combattants vivants
        all_fighters = [
            fighter 
            for fighter in self.attackers.fighters + self.defenders.fighters 
            if fighter.is_alive()
        ]
        
        # 2. Mélange aléatoire
        import random
        random.shuffle(all_fighters)
        
        return all_fighters

    def start_round(self, rest: bool = True) -> None:
        """Start the fight between alliances."""
        can_play = self.can_play
        if not can_play:
            return

        for _ in range(len(can_play)):
            who_play = self.who_next()
            if not who_play:
                break

            if not who_play.is_alive():
                self.can_play.remove(who_play)
                self.log_message.append(f"{who_play.name} est mort et ne peut pas jouer.")
                continue

            if who_play in self.attackers:
                opponents = self.defenders.get_fighters()
                allies = self.attackers.get_fighters()
            else:
                opponents = self.attackers.get_fighters()
                allies = self.defenders.get_fighters()

            shuffle(opponents)
            for enemy in opponents:
                if not enemy.is_alive():
                    continue
                success, message = who_play.attack(enemy)
                if success:
                    self.log_message.append(message)
                    self.can_play.remove(who_play)
                    break
                else:
                    self.log_message.append(f"{who_play.name} a raté son attaque sur {enemy.name}")
            else:
                action_done = False
                shuffle(allies)
                for ally in allies:
                    for skill_name, skill in who_play.skills.items():
                        if skill.skill_type == SkillType.RESURRECT and not ally.is_alive():
                            if self.play(who_play, ally, skill_name):
                                self.log_message.append(f"{who_play.name} ressuscite {ally.name}")
                                self.can_play.remove(who_play)
                                action_done = True
                                break
                        elif skill.skill_type in (SkillType.HEAL, SkillType.BUFF) and ally.is_alive():
                            if self.play(who_play, ally, skill_name):
                                self.log_message.append(f"{who_play.name} utilise {skill_name} sur {ally.name}")
                                self.can_play.remove(who_play)
                                action_done = True
                                break
                    if action_done:
                        break

                if not action_done:
                    self.log_message.append(f"{who_play.name} ne peut rien faire ce tour-ci.")
                    self.can_play.remove(who_play)

        self.end_round(rest)

    def end_round(self, rest : bool) ->None:
        if not rest: return self._new_round()
        self.rest()
        self._new_round()
    
    def rest(self):
        for fighter in self.get_all_individuals():
            if fighter.is_alive():
                fighter.rest()

                
    def play(self, who_play : Character, target : Character, skill_name : str) -> bool:
        if not who_play in self.can_play : raise RuntimeWarning(f"{who_play.name} can't play, already play")
        if who_play.is_stun() : raise RuntimeWarning(f"{who_play.name} is stun, can't play")
        
        success, message = who_play.use_skill(skill_name,target)
        self.log_message.append(message)
        if message == '' : input("here")
        self.can_play.remove(who_play)
        return success
    
    def get_winner(self) -> Optional[Alliance]:
        """Get the winning alliance."""
        return self._winner
    
    def __str__(self) -> str:
        """String representation of the fight."""
        att_count = len(self.attackers.fighters)
        def_count = len(self.defenders.fighters)
        status = "completed" if self._winner else "ongoing"
        winner = f", winner: {self._winner.name}" if self._winner else ""
        
        return (f"Fight ({status}): {att_count} attackers vs {def_count} defenders"
                f"{winner}")

    def end(self) -> None:
        """Clean up the fight alliances."""
        self.attackers.fighters.clear()
        self.defenders.fighters.clear()
        self.clear_log()
        