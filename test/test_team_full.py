"""
Tests pour la classe Team.
"""

import pytest
from jeuxRPG._class.res.team.team import Team
from jeuxRPG._class.sub_character.knight import Knight
from jeuxRPG._class.sub_character.mage import Mage
from jeuxRPG._class.sub_character.archer import Archer


@pytest.fixture(autouse=True)
def clear_teams():
    """Nettoie la liste globale des équipes avant chaque test."""
    Team.all_teams.clear()
    yield
    Team.all_teams.clear()


class TestTeamCreation:
    """Tests pour la création d'équipes."""
    
    def test_create_team_with_name(self):
        """Test création avec nom."""
        team = Team("Heroes")
        
        assert team.name == "Heroes"
        assert team in Team.all_teams
    
    def test_create_team_default_name(self):
        """Test création avec nom par défaut."""
        team = Team()
        
        assert team.name == "Team 1"
    
    def test_create_team_multiple_default_names(self):
        """Test noms par défaut incrémentaux."""
        team1 = Team()
        team2 = Team()
        
        assert team1.name == "Team 1"
        assert team2.name == "Team 2"
    
    def test_create_team_duplicate_name_raises(self):
        """Test erreur pour nom dupliqué."""
        Team("Heroes")
        
        with pytest.raises(ValueError, match="already in use"):
            Team("Heroes")
    
    def test_create_team_with_single_member(self):
        """Test création avec un seul membre."""
        knight = Knight("user1", "Sir Knight")
        team = Team("Knights", knight)
        
        assert knight in team.fighters
        assert knight.team == team
        assert team.leader == knight
    
    def test_create_team_with_member_list(self):
        """Test création avec liste de membres."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        team = Team("Heroes", [knight, mage])
        
        assert knight in team.fighters
        assert mage in team.fighters


class TestTeamFighters:
    """Tests pour la gestion des combattants."""
    
    def test_add_fighter(self):
        """Test ajout d'un combattant."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        
        team.add_fighter(knight)
        
        assert knight in team.fighters
        assert knight.team == team
    
    def test_add_fighter_not_character_raises(self):
        """Test erreur pour type invalide."""
        team = Team("Heroes")
        
        with pytest.raises(TypeError, match="Character"):
            team.add_fighter("not a character")
    
    def test_add_fighter_already_in_team_raises(self):
        """Test erreur si déjà dans l'équipe."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        team.add_fighter(knight)
        
        with pytest.raises(ValueError, match="already in this team"):
            team.add_fighter(knight)
    
    def test_add_fighter_in_other_team_raises(self):
        """Test erreur si dans une autre équipe."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        knight = Knight("user1", "Sir Knight")
        team1.add_fighter(knight)
        
        with pytest.raises(ValueError, match="already belongs to team"):
            team2.add_fighter(knight)
    
    def test_remove_fighter(self):
        """Test suppression d'un combattant."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        team.add_fighter(knight)
        
        team.remove_fighter(knight)
        
        assert knight not in team.fighters
        assert knight.team is None
    
    def test_remove_fighter_not_in_team_raises(self):
        """Test erreur si pas dans l'équipe."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        
        with pytest.raises(ValueError, match="not in this team"):
            team.remove_fighter(knight)
    
    def test_get_fighters_returns_copy(self):
        """Test que get_fighters retourne une copie."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        team.add_fighter(knight)
        
        fighters = team.get_fighters()
        fighters.clear()
        
        assert knight in team.fighters
    
    def test_contains_fighter(self):
        """Test opérateur 'in'."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        team.add_fighter(knight)
        
        assert knight in team
        assert mage not in team


class TestTeamLeader:
    """Tests pour la gestion du leader."""
    
    def test_change_leader(self):
        """Test changement de leader."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        team.add_fighter(knight)
        
        team.change_leader(knight)
        
        assert team.leader == knight
    
    def test_change_leader_adds_to_team(self):
        """Test que le leader est ajouté à l'équipe."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        
        team.change_leader(knight)
        
        assert knight in team.fighters
        assert team.leader == knight
    
    def test_change_leader_from_other_team_raises(self):
        """Test erreur si leader d'une autre équipe."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        knight = Knight("user1", "Sir Knight")
        team1.add_fighter(knight)
        
        with pytest.raises(RuntimeError, match="Can't be the leader"):
            team2.change_leader(knight)
    
    def test_change_leader_already_leader_raises(self):
        """Test erreur si déjà leader."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        team.change_leader(knight)
        
        with pytest.raises(RuntimeError, match="already the leader"):
            team.change_leader(knight)
    
    def test_remove_leader(self):
        """Test suppression du leader."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        team.change_leader(knight)
        
        team.remove_leader()
        
        assert team.leader is None
    
    def test_remove_leader_no_leader_raises(self):
        """Test erreur si pas de leader."""
        team = Team("Heroes")
        
        with pytest.raises(RuntimeError, match="no leader"):
            team.remove_leader()
    
    def test_remove_fighter_removes_leader(self):
        """Test que supprimer un combattant leader retire le leader."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        team.change_leader(knight)
        
        team.remove_fighter(knight)
        
        assert team.leader is None


class TestTeamAlliances:
    """Tests pour les alliances."""
    
    def test_add_ally(self):
        """Test ajout d'un allié."""
        team1 = Team("Heroes")
        team2 = Team("Helpers")
        
        team1.add_ally(team2)
        
        assert team2 in team1.allies
        assert team1 in team2.allies  # Mutuel
    
    def test_add_ally_not_mutual(self):
        """Test alliance non mutuelle."""
        team1 = Team("Heroes")
        team2 = Team("Helpers")
        
        team1.add_ally(team2, mutual=False)
        
        assert team2 in team1.allies
        assert team1 not in team2.allies
    
    def test_add_ally_not_team_raises(self):
        """Test erreur pour type invalide."""
        team = Team("Heroes")
        
        with pytest.raises(TypeError, match="Team instances"):
            team.add_ally("not a team")
    
    def test_add_ally_self_raises(self):
        """Test erreur pour auto-alliance."""
        team = Team("Heroes")
        
        with pytest.raises(ValueError, match="oneself"):
            team.add_ally(team)
    
    def test_add_ally_already_allied_raises(self):
        """Test erreur si déjà alliés."""
        team1 = Team("Heroes")
        team2 = Team("Helpers")
        team1.add_ally(team2)
        
        with pytest.raises(ValueError, match="Already allied"):
            team1.add_ally(team2)
    
    def test_add_ally_enemy_raises(self):
        """Test erreur si ennemis."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        team1.add_enemy(team2)
        
        with pytest.raises(ValueError, match="Cannot ally with enemy"):
            team1.add_ally(team2)
    
    def test_remove_ally(self):
        """Test suppression d'un allié."""
        team1 = Team("Heroes")
        team2 = Team("Helpers")
        team1.add_ally(team2)
        
        team1.remove_ally(team2)
        
        assert team2 not in team1.allies
        assert team1 not in team2.allies
    
    def test_remove_ally_not_allied_raises(self):
        """Test erreur si pas alliés."""
        team1 = Team("Heroes")
        team2 = Team("Helpers")
        
        with pytest.raises(ValueError, match="Not allied"):
            team1.remove_ally(team2)
    
    def test_get_allies_returns_copy(self):
        """Test que get_allies retourne une copie."""
        team1 = Team("Heroes")
        team2 = Team("Helpers")
        team1.add_ally(team2)
        
        allies = team1.get_allies()
        allies.clear()
        
        assert team2 in team1.allies


class TestTeamEnemies:
    """Tests pour les ennemis."""
    
    def test_add_enemy(self):
        """Test ajout d'un ennemi."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        
        team1.add_enemy(team2)
        
        assert team2 in team1.enemies
        assert team1 in team2.enemies  # Mutuel
    
    def test_add_enemy_not_mutual(self):
        """Test ennemi non mutuel."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        
        team1.add_enemy(team2, mutual=False)
        
        assert team2 in team1.enemies
        assert team1 not in team2.enemies
    
    def test_add_enemy_not_team_raises(self):
        """Test erreur pour type invalide."""
        team = Team("Heroes")
        
        with pytest.raises(TypeError, match="Team instances"):
            team.add_enemy("not a team")
    
    def test_add_enemy_self_raises(self):
        """Test erreur pour auto-ennemi."""
        team = Team("Heroes")
        
        with pytest.raises(ValueError, match="oneself"):
            team.add_enemy(team)
    
    def test_add_enemy_already_enemy_no_error(self):
        """Test pas d'erreur si déjà ennemis."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        team1.add_enemy(team2)
        
        # Ne devrait pas lever d'erreur
        team1.add_enemy(team2)
    
    def test_add_enemy_ally_raises(self):
        """Test erreur si alliés."""
        team1 = Team("Heroes")
        team2 = Team("Helpers")
        team1.add_ally(team2)
        
        with pytest.raises(ValueError, match="Cannot declare ally"):
            team1.add_enemy(team2)
    
    def test_remove_enemy(self):
        """Test suppression d'un ennemi."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        team1.add_enemy(team2)
        
        team1.remove_enemy(team2)
        
        assert team2 not in team1.enemies
        assert team1 not in team2.enemies
    
    def test_remove_enemy_not_enemy_raises(self):
        """Test erreur si pas ennemis."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        
        with pytest.raises(ValueError, match="Not enemies"):
            team1.remove_enemy(team2)
    
    def test_get_enemies_returns_copy(self):
        """Test que get_enemies retourne une copie."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        team1.add_enemy(team2)
        
        enemies = team1.get_enemies()
        enemies.clear()
        
        assert team2 in team1.enemies


class TestTeamRelationships:
    """Tests pour les vérifications de relations."""
    
    def test_is_ally_character(self):
        """Test is_ally avec un personnage."""
        team1 = Team("Heroes")
        team2 = Team("Helpers")
        knight = Knight("user1", "Sir Knight")
        team2.add_fighter(knight)
        team1.add_ally(team2)
        
        assert team1.is_ally(knight) is True
    
    def test_is_ally_same_team(self):
        """Test is_ally avec un coéquipier."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        team.add_fighter(knight)
        team.add_fighter(mage)
        
        assert team.is_ally(knight) is True
    
    def test_is_ally_team(self):
        """Test is_ally avec une équipe."""
        team1 = Team("Heroes")
        team2 = Team("Helpers")
        team1.add_ally(team2)
        
        assert team1.is_ally(team2) is True
    
    def test_is_ally_invalid_type_raises(self):
        """Test erreur pour type invalide."""
        team = Team("Heroes")
        
        with pytest.raises(TypeError):
            team.is_ally("not valid")
    
    def test_is_enemy(self):
        """Test is_enemy."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        knight = Knight("user1", "Sir Knight")
        team2.add_fighter(knight)
        team1.add_enemy(team2)
        
        assert team1.is_enemy(knight) is True
    
    def test_is_enemy_not_character_raises(self):
        """Test erreur pour type invalide."""
        team = Team("Heroes")
        
        with pytest.raises(TypeError):
            team.is_enemy("not a character")
    
    def test_is_teammate(self):
        """Test is_teammate."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        team.add_fighter(knight)
        
        assert team.is_teammate(knight) is True
        assert team.is_teammate(mage) is False
    
    def test_is_teammate_not_character_raises(self):
        """Test erreur pour type invalide."""
        team = Team("Heroes")
        
        with pytest.raises(TypeError):
            team.is_teammate("not a character")


class TestTeamMerge:
    """Tests pour la fusion d'équipes."""
    
    def test_merge_with(self):
        """Test fusion d'équipes."""
        team1 = Team("Heroes")
        team2 = Team("Helpers")
        team3 = Team("Supporters")
        # Tester avec alliances et ennemis seulement (pas de combattants)
        team2.add_ally(team3)
        
        team1.merge_with(team2)
        
        # Les alliances sont transférées
        assert team3 in team1.allies
        assert team2 not in Team.all_teams
    
    def test_merge_not_team_raises(self):
        """Test erreur pour type invalide."""
        team = Team("Heroes")
        
        with pytest.raises(TypeError):
            team.merge_with("not a team")
    
    def test_merge_self_raises(self):
        """Test erreur pour auto-fusion."""
        team = Team("Heroes")
        
        with pytest.raises(ValueError, match="oneself"):
            team.merge_with(team)


class TestTeamUtilities:
    """Tests pour les utilitaires."""
    
    def test_any_alive_all_alive(self):
        """Test any_alive avec tous vivants."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        team.add_fighter(knight)
        
        assert team.any_alive() is True
    
    def test_any_alive_all_dead(self):
        """Test any_alive avec tous morts."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        team.add_fighter(knight)
        
        # Infliger des dégâts mortels (source nécessaire)
        attacker = Mage("enemy", "Attacker")
        knight.lose_hp(attacker, knight.hp.current_value + 1000)
        
        assert team.any_alive() is False
    
    def test_rename(self):
        """Test renommage."""
        team = Team("Heroes")
        
        team.rename("Super Heroes")
        
        assert team.name == "Super Heroes"
    
    def test_rename_duplicate_raises(self):
        """Test erreur pour nom dupliqué."""
        team1 = Team("Heroes")
        team2 = Team("Villains")
        
        with pytest.raises(ValueError, match="already in use"):
            team2.rename("Heroes")
    
    def test_destroy(self):
        """Test destruction d'équipe."""
        team = Team("Heroes")
        knight = Knight("user1", "Sir Knight")
        team.add_fighter(knight)
        
        team.destroy()
        
        assert team not in Team.all_teams
        assert knight.team is None
    
    def test_str(self):
        """Test représentation string."""
        team = Team("Heroes")
        
        s = str(team)
        
        assert "Heroes" in s
        assert "0" in s  # 0 fighters
    
    def test_repr(self):
        """Test représentation repr."""
        team = Team("Heroes")
        
        r = repr(team)
        
        assert "Team" in r
        assert "Heroes" in r


class TestTeamClassMethods:
    """Tests pour les méthodes de classe."""
    
    def test_get_team_by_name(self):
        """Test récupération par nom."""
        team = Team("Heroes")
        
        found = Team.get_team_by_name("Heroes")
        
        assert found == team
    
    def test_get_team_by_name_not_found(self):
        """Test récupération inexistante."""
        found = Team.get_team_by_name("Unknown")
        
        assert found is None
    
    def test_team_exists(self):
        """Test existence."""
        Team("Heroes")
        
        assert Team.team_exists("Heroes") is True
        assert Team.team_exists("Unknown") is False
    
    def test_remove_team(self):
        """Test suppression d'équipe."""
        team = Team("Heroes")
        
        Team.remove_team(team)
        
        assert team not in Team.all_teams
    
    def test_remove_team_cleans_relationships(self):
        """Test nettoyage des relations."""
        team1 = Team("Heroes")
        team2 = Team("Helpers")
        team1.add_ally(team2)
        
        Team.remove_team(team2)
        
        assert team2 not in team1.allies
    
    def test_remove_team_not_team_raises(self):
        """Test erreur pour type invalide."""
        with pytest.raises(TypeError):
            Team.remove_team("not a team")
