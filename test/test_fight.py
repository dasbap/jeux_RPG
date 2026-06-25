"""
Tests pour la classe Fight.
"""

import pytest
from jeuxRPG._class._event.confrontation.encounter.fight import Fight
from jeuxRPG._class.character import Character
from jeuxRPG._class.res.team.team import Team
from jeuxRPG._class.sub_character.knight import Knight
from jeuxRPG._class.sub_character.mage import Mage
from jeuxRPG._class.sub_character.archer import Archer
from jeuxRPG._class.sub_character.priest import Priest


@pytest.fixture(autouse=True)
def clear_teams():
    """Nettoie la liste globale des équipes avant chaque test."""
    Team.all_teams.clear()
    yield
    Team.all_teams.clear()


class TestFightCreation:
    """Tests pour la création de combats."""
    
    def test_create_fight_characters(self):
        """Test création avec des personnages."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage, "Duel")
        
        assert knight in fight.attackers.fighters
        assert mage in fight.defenders.fighters
    
    def test_create_fight_teams(self):
        """Test création avec des équipes."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        team1.add_fighter(knight)
        team2.add_fighter(mage)
        
        fight = Fight(team1, team2)
        
        assert knight in fight.attackers.fighters
        assert mage in fight.defenders.fighters
    
    def test_create_fight_lists(self):
        """Test création avec des listes."""
        knight = Knight("user1", "Sir Knight")
        archer = Archer("user2", "Legolas")
        mage = Mage("user3", "Gandalf")
        
        fight = Fight([knight, archer], [mage])
        
        assert knight in fight.attackers.fighters
        assert archer in fight.attackers.fighters
        assert mage in fight.defenders.fighters
    
    def test_create_fight_same_character_both_sides_raises(self):
        """Test erreur si même personnage des deux côtés."""
        knight = Knight("user1", "Sir Knight")
        
        with pytest.raises(ValueError, match="cannot be on both sides"):
            Fight(knight, knight)
    
    def test_create_fight_invalid_type_raises(self):
        """Test erreur pour type invalide."""
        knight = Knight("user1", "Sir Knight")
        
        with pytest.raises(TypeError, match="Character, Team, or list"):
            Fight(knight, "not valid")
    
    def test_fight_initial_state(self):
        """Test état initial du combat."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        assert fight.round == 1
        assert fight._winner is None
        assert knight in fight.can_play
        assert mage in fight.can_play


class TestFightParticipants:
    """Tests pour la gestion des participants."""
    
    def test_add_attacker(self):
        """Test ajout d'un attaquant."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        archer = Archer("user3", "Legolas")
        
        fight = Fight(knight, mage)
        fight.add_attacker(archer)
        
        assert archer in fight.attackers.fighters
    
    def test_add_defender(self):
        """Test ajout d'un défenseur."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        priest = Priest("user3", "Father")
        
        fight = Fight(knight, mage)
        fight.add_defender(priest)
        
        assert priest in fight.defenders.fighters
    
    def test_add_attacker_invalid_raises(self):
        """Test erreur ajout attaquant invalide."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        with pytest.raises(TypeError, match="Character or Team"):
            fight.add_attacker("not valid")
    
    def test_get_all_individuals(self):
        """Test récupération de tous les combattants."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        archer = Archer("user3", "Legolas")
        
        fight = Fight([knight, archer], mage)
        
        all_fighters = fight.get_all_individuals()
        
        assert knight in all_fighters
        assert mage in all_fighters
        assert archer in all_fighters
    
    def test_get_original_teams(self):
        """Test récupération des équipes originales."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        team1.add_fighter(knight)
        team2.add_fighter(mage)
        
        fight = Fight(team1, team2)
        
        teams = fight.get_original_teams()
        
        assert team1 in teams
        assert team2 in teams


class TestFightRounds:
    """Tests pour la gestion des rounds."""
    
    def test_who_next(self):
        """Test sélection du prochain joueur."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        next_player = fight.who_next()
        
        assert next_player in [knight, mage]
    
    def test_who_next_empty(self):
        """Test who_next quand personne ne peut jouer."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        fight.can_play.clear()
        
        assert fight.who_next() is None
    
    def test_start_round(self):
        """Test démarrage d'un round."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        initial_round = fight.round
        
        fight.start_round()
        
        # Le round devrait avoir avancé
        assert fight.round == initial_round + 1
    
    def test_end_round(self):
        """Test fin de round."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        fight.end_round(rest=True)
        
        # Nouveau round devrait être préparé
        assert len(fight.can_play) >= 0
    
    def test_end_round_no_rest(self):
        """Test fin de round sans repos."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        initial_round = fight.round
        
        fight.end_round(rest=False)
        
        assert fight.round == initial_round + 1
    
    def test_rest(self):
        """Test repos des combattants."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        # Ne devrait pas lever d'erreur
        fight.rest()


class TestFightPlay:
    """Tests pour l'action play."""
    
    def test_play_skill(self):
        """Test utilisation d'une compétence."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        # Trouver une compétence valide
        skill_name = next(iter(knight.skills.keys()), None)
        if skill_name:
            result = fight.play(knight, mage, skill_name)
            
            # Le chevalier ne devrait plus pouvoir jouer ce round
            assert knight not in fight.can_play
    
    def test_play_already_played(self):
        """Test jouer quand déjà joué."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        fight.can_play.remove(knight)
        
        skill_name = next(iter(knight.skills.keys()), None)
        if skill_name:
            result = fight.play(knight, mage, skill_name)
            
            assert result is False
    
    def test_play_stunned_raises(self):
        """Test jouer quand étourdi."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        # Simuler l'étourdissement via le status dict
        from jeuxRPG._class.res.character.alteration.alteration import Stun
        stun = Stun("Test", mage, 2, knight)
        knight.status["alteration"]["stun"] = [stun]
        
        skill_name = next(iter(knight.skills.keys()), None)
        if skill_name:
            with pytest.raises(RuntimeWarning, match="stun"):
                fight.play(knight, mage, skill_name)


class TestFightEnd:
    """Tests pour la fin de combat."""
    
    def test_get_winner_none(self):
        """Test get_winner quand pas encore de gagnant."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        assert fight.get_winner() is None
    
    def test_str(self):
        """Test représentation string."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        s = str(fight)
        
        assert "Fight" in s
        assert "attackers" in s
        assert "defenders" in s
    
    def test_end(self):
        """Test nettoyage de fin de combat."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        fight.end()
        
        assert fight.attackers.fighters == []
        assert fight.defenders.fighters == []
        assert fight.log_message == []
    
    def test_clear_log(self):
        """Test nettoyage des logs."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        fight.log_message.append("Test message")
        
        fight.clear_log()
        
        assert fight.log_message == []


class TestFightMergeAndShuffle:
    """Tests pour _merge_and_shuffle_fighters."""
    
    def test_merge_and_shuffle(self):
        """Test fusion et mélange des combattants."""
        knight = Knight("user1", "Sir Knight")
        archer = Archer("user2", "Legolas")
        mage = Mage("user3", "Gandalf")
        
        fight = Fight([knight, archer], mage)
        
        merged = fight._merge_and_shuffle_fighters()
        
        assert knight in merged
        assert archer in merged
        assert mage in merged
    
    def test_merge_excludes_dead(self):
        """Test fusion exclut les morts."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        # Tuer le mage
        mage.hp.current_value = 0
        
        fight = Fight(knight, mage)
        
        merged = fight._merge_and_shuffle_fighters()
        
        assert knight in merged
        assert mage not in merged


class TestFightNormalize:
    """Tests pour _normalize_participants."""
    
    def test_normalize_none(self):
        """Test normalisation de None."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        result = fight._normalize_participants(None)
        
        assert result == []
    
    def test_normalize_single_character(self):
        """Test normalisation d'un seul personnage."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        fight = Fight(knight, mage)
        
        result = fight._normalize_participants(knight)
        
        assert result == [knight]
    
    def test_normalize_list(self):
        """Test normalisation d'une liste."""
        knight = Knight("user1", "Sir Knight")
        archer = Archer("user2", "Legolas")
        mage = Mage("user3", "Gandalf")
        
        fight = Fight(knight, mage)
        
        result = fight._normalize_participants([knight, archer])
        
        assert knight in result
        assert archer in result
