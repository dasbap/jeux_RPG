"""
fight.py

Ce module contient la classe Fight, qui gère un combat entre des personnages
et/ou des équipes. Il prend en charge l'ajout de participants, leur catégorisation 
(comme attaquants ou défenseurs), et fournit des utilitaires pour accéder à 
l'ensemble des combattants impliqués dans un combat.
"""

from typing import List, Union
from ..res.team import Character, Team


class Fight:
    """Représente un combat entre des attaquants et des défenseurs.

    Les attaquants et les défenseurs peuvent être des personnages individuels 
    (Character) ou des équipes (Team). Tous les personnages impliqués, qu'ils 
    soient seuls ou dans une équipe, sont comptabilisés comme participants.

    Attributs :
        attackers (List[Union[Character, Team]]): Liste des attaquants.
        defenders (List[Union[Character, Team]]): Liste des défenseurs.
        participants (List[Character]): Tous les personnages individuels impliqués.
    """
    
    def __init__(
        self,
        attackers: Union[List[Character], List[Team], Character, Team],
        defenders: Union[List[Character], List[Team], Character, Team]
    ) -> None:
        """Initialise le combat avec attaquants et défenseurs.

        Args:
            attackers: Un ou plusieurs Characters ou Teams attaquants.
            defenders: Un ou plusieurs Characters ou Teams défenseurs.

        Raises:
            TypeError: Si des types non valides sont fournis.
            ValueError: S'il y a moins de 2 participants valides.
        """
        self.attackers = self._normalize_participants(attackers, "attackers")
        self.defenders = self._normalize_participants(defenders, "defenders")
        self.participants = self._get_all_individuals()

        if len(self.participants) < 2:
            raise ValueError("A fight requires at least 2 participants")

    def _normalize_participants(
        self,
        participants: Union[List[Union[Character, Team]], Union[Character, Team]],
        role: str
    ) -> List[Union[Character, Team]]:
        """Normalise l'entrée participants en une liste.

        Args:
            participants: Participant unique ou liste de participants.
            role: Nom du rôle pour les messages d'erreur.

        Returns:
            Liste normalisée des participants.

        Raises:
            TypeError: Si un type non attendu est détecté.
            ValueError: Si la liste est vide.
        """
        if isinstance(participants, (Character, Team)):
            return [participants]

        if isinstance(participants, list):
            if not participants:
                raise ValueError(f"{role} list cannot be empty")

            for p in participants:
                if not isinstance(p, (Character, Team)):
                    raise TypeError(
                        f"All {role} must be Character or Team instances, got {type(p).__name__}"
                    )
            return participants

        raise TypeError(
            f"{role} must be Character, Team or list of them, got {type(participants).__name__}"
        )

    def _get_all_individuals(self) -> List[Character]:
        """Retourne tous les personnages individuels impliqués dans le combat.

        Returns:
            Liste des personnages uniques (sans doublons).
        """
        individuals = []

        for participant in self.attackers + self.defenders:
            if isinstance(participant, Character):
                if participant not in individuals:
                    individuals.append(participant)
            elif isinstance(participant, Team):
                for fighter in participant.fighters:
                    if fighter not in individuals:
                        individuals.append(fighter)

        return individuals

    def get_attackers(self) -> List[Character]:
        """Retourne la liste des personnages attaquants.

        Returns:
            Liste de Characters côté attaquants.
        """
        return self._get_individuals_from_side(self.attackers)

    def get_defenders(self) -> List[Character]:
        """Retourne la liste des personnages défenseurs.

        Returns:
            Liste de Characters côté défenseurs.
        """
        return self._get_individuals_from_side(self.defenders)

    def _get_individuals_from_side(
        self,
        side: List[Union[Character, Team]]
    ) -> List[Character]:
        """Extrait tous les personnages individuels d’un côté.

        Args:
            side: Liste d’objets Character ou Team.

        Returns:
            Liste de tous les Characters présents dans ce groupe.
        """
        individuals = []

        for participant in side:
            if isinstance(participant, Character):
                individuals.append(participant)
            else:
                individuals.extend(participant.fighters)

        return individuals

    def add_attacker(self, attacker: Union[Character, Team]) -> None:
        """Ajoute un attaquant au combat.

        Args:
            attacker: Character ou Team à ajouter.

        Raises:
            TypeError: Si le type n'est pas valide.
            ValueError: Si le participant est déjà présent.
        """
        self._add_participant(attacker, self.attackers)
        self.participants = self._get_all_individuals()

    def add_defender(self, defender: Union[Character, Team]) -> None:
        """Ajoute un défenseur au combat.

        Args:
            defender: Character ou Team à ajouter.

        Raises:
            TypeError: Si le type n'est pas valide.
            ValueError: Si le participant est déjà présent.
        """
        self._add_participant(defender, self.defenders)
        self.participants = self._get_all_individuals()

    def _add_participant(
        self,
        participant: Union[Character, Team],
        side: List[Union[Character, Team]]
    ) -> None:
        """Ajoute un participant à une des deux équipes.

        Args:
            participant: Le Character ou Team à ajouter.
            side: La liste (attaque ou défense) à modifier.

        Raises:
            TypeError: Si ce n'est ni un Character ni un Team.
            ValueError: Si déjà présent dans le groupe.
        """
        if not isinstance(participant, (Character, Team)):
            raise TypeError("Can only add Character or Team instances")

        if participant in side:
            name = participant.name if hasattr(participant, 'name') else str(participant)
            raise ValueError(f"{name} is already in this side")

        side.append(participant)

    def get_teams_involved(self) -> List[Team]:
        """Retourne toutes les équipes uniques impliquées dans le combat.

        Returns:
            Liste d'objets Team.
        """
        teams = []

        for participant in self.attackers + self.defenders:
            if isinstance(participant, Team):
                if participant not in teams:
                    teams.append(participant)
            elif isinstance(participant, Character) and participant.team:
                if participant.team not in teams:
                    teams.append(participant.team)

        return teams

    def is_attacker(self, character: Character) -> bool:
        """Vérifie si un personnage est du côté des attaquants.

        Args:
            character: Personnage à tester.

        Returns:
            True si attaquant, False sinon.
        """
        return character in self.get_attackers()

    def is_defender(self, character: Character) -> bool:
        """Vérifie si un personnage est du côté des défenseurs.

        Args:
            character: Personnage à tester.

        Returns:
            True si défenseur, False sinon.
        """
        return character in self.get_defenders()

    def __str__(self) -> str:
        """Retourne une représentation textuelle du combat.

        Returns:
            Chaîne de résumé du combat.
        """
        att_count = len(self.get_attackers())
        def_count = len(self.get_defenders())
        teams = self.get_teams_involved()

        return (f"Fight: {att_count} attackers vs {def_count} defenders "
                f"({len(teams)} teams involved)")
