
from random import choice, shuffle
from typing import List, Optional, Union

from jeuxRPG._class.character import Character
from jeuxRPG._class.res.classType import SkillType
from jeuxRPG._class.res.team.alliance import Alliance
from jeuxRPG._class.res.team.team import Team
from jeuxRPG.i18n import t


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
        individuals: List[Character] = []
        seen: set[int] = set()
        for fighter in self.attackers.fighters + self.defenders.fighters:
            marker = id(fighter)
            if marker in seen:
                continue
            seen.add(marker)
            individuals.append(fighter)
        return individuals
    
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

            # Skip turn if stunned, but still tick status so stun can expire
            if who_play.is_stun():
                try:
                    updates = who_play._update_status()
                    if isinstance(updates, list):
                        extra_msgs = [m for m, _ in updates if m]
                        if extra_msgs:
                            self.log_message.append(" ".join(extra_msgs))
                except Exception:
                    pass
                self.log_message.append(f"{who_play.name} est étourdi et saute son tour.")
                if who_play in self.can_play:
                    self.can_play.remove(who_play)
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
                                if who_play in self.can_play:
                                    self.can_play.remove(who_play)
                                action_done = True
                                break
                        elif skill.skill_type in (SkillType.HEAL, SkillType.BUFF) and ally.is_alive():
                            if self.play(who_play, ally, skill_name):
                                self.log_message.append(f"{who_play.name} utilise {skill_name} sur {ally.name}")
                                if who_play in self.can_play:
                                    self.can_play.remove(who_play)
                                action_done = True
                                break
                    if action_done:
                        break

                if not action_done:
                    self.log_message.append(f"{who_play.name} ne peut rien faire ce tour-ci.")
                    if who_play in self.can_play:
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
        # If the actor already played this round, treat as no-op (avoid raising during auto-battle loops)
        if who_play not in self.can_play:
            return False
        if who_play.is_stun():
            # Keep explicit signal for tests expecting a stun prevention behavior
            raise RuntimeWarning(f"{who_play.name} is stun, can't play")

        success, message = who_play.use_skill(skill_name, target)
        self.log_message.append(message)
        if message == '':
            # Debug hook left from older flow; keep safe but non-blocking
            pass
        self.can_play.remove(who_play)
        return success
    
    def get_winner(self) -> Optional[Alliance]:
        """Get the winning alliance."""
        return self._winner
    
    def __str__(self) -> str:
        """String representation of the fight."""
        att_count = len(self.attackers.fighters)
        def_count = len(self.defenders.fighters)
        
        if self._winner:
            return t("fight.str_completed", att_count=att_count, def_count=def_count, 
                     winner=self._winner.name)
        else:
            return t("fight.str_ongoing", att_count=att_count, def_count=def_count)

    def end(self) -> None:
        """Clean up the fight alliances."""
        self.attackers.fighters.clear()
        self.defenders.fighters.clear()
        self.clear_log()

    def is_over(self) -> bool:
        """Determine whether the fight has ended and set the winner.

        A fight is over when one side has no living fighters, or when both
        sides have no living fighters.
        """
        attackers_alive = any(f.is_alive() for f in self.attackers.fighters)
        defenders_alive = any(f.is_alive() for f in self.defenders.fighters)

        if not attackers_alive and not defenders_alive:
            self._winner = None
            return True
        if attackers_alive and not defenders_alive:
            self._winner = self.attackers
            return True
        if defenders_alive and not attackers_alive:
            self._winner = self.defenders
            return True
        return False
