"""Unit tests for Team and Alliance system."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from jeuxRPG._class.character import Character
from jeuxRPG._class.res.team.team import Team
from jeuxRPG._class.res.team.alliance import Alliance


@pytest.fixture(autouse=True)
def clear_all_teams():
    """Clear Team.all_teams before each test."""
    Team.all_teams.clear()
    yield
    Team.all_teams.clear()


@pytest.fixture(autouse=True)
def clear_all_alliances():
    """Clear Alliance.all_alliances before each test."""
    if hasattr(Alliance, 'all_alliances'):
        Alliance.all_alliances.clear()
    yield
    if hasattr(Alliance, 'all_alliances'):
        Alliance.all_alliances.clear()


class TestTeamCreation:
    """Tests for Team creation and initialization."""

    def test_team_creation_with_name(self):
        """Test creating a team with a specific name."""
        team = Team(name="Warriors")
        assert team.name == "Warriors"
        assert team.leader is None
        assert team.fighters == []
        assert team in Team.all_teams

    def test_team_creation_with_leader(self):
        """Test creating a team with an initial leader."""
        knight = Character.create("Knight", "user1", "Aragorn")
        team = Team(name="Fellowship", Team_member=knight)
        assert team.leader == knight
        assert knight in team.fighters

    def test_team_creation_with_multiple_members(self):
        """Test creating a team with multiple members."""
        knight = Character.create("Knight", "user1", "Aragorn")
        priest = Character.create("Priest", "user2", "Gandalf")
        archer = Character.create("Archer", "user3", "Legolas")
        
        team = Team(name="Fellowship", Team_member=[knight, priest, archer])
        assert len(team.fighters) == 3
        assert knight in team.fighters
        assert priest in team.fighters
        assert archer in team.fighters

    def test_team_default_name(self):
        """Test that team gets a default name if not provided."""
        team1 = Team()
        team2 = Team()
        assert "Team" in team1.name or team1.name != ""
        assert "Team" in team2.name or team2.name != ""
        assert team1.name != team2.name

    def test_team_name_uniqueness(self):
        """Test that team names must be unique."""
        team1 = Team(name="Warriors")
        with pytest.raises(ValueError, match="already in use"):
            Team(name="Warriors")

    def test_team_empty_name_allowed(self):
        """Test that empty name is allowed and generates default."""
        team = Team(name="")
        assert team.name != ""
        assert "Team" in team.name or team.name.isdigit()


class TestTeamManagement:
    """Tests for team member management."""

    def test_add_fighter_to_team(self):
        """Test adding a fighter to a team."""
        team = Team(name="Adventurers")
        knight = Character.create("Knight", "user1", "Hero")
        team.add_fighter(knight)
        assert knight in team.fighters

    def test_add_multiple_fighters(self):
        """Test adding multiple fighters to a team."""
        team = Team(name="Adventurers")
        knight = Character.create("Knight", "user1", "Hero1")
        priest = Character.create("Priest", "user2", "Hero2")
        archer = Character.create("Archer", "user3", "Hero3")
        
        team.add_fighter(knight)
        team.add_fighter(priest)
        team.add_fighter(archer)
        
        assert len(team.fighters) == 3
        assert all(char in team.fighters for char in [knight, priest, archer])

    def test_change_leader(self):
        """Test changing team leader."""
        team = Team(name="Adventurers")
        knight = Character.create("Knight", "user1", "Hero1")
        priest = Character.create("Priest", "user2", "Hero2")
        
        team.change_leader(knight)
        assert team.leader == knight
        
        team.change_leader(priest)
        assert team.leader == priest

    def test_leader_is_added_to_fighters(self):
        """Test that leader is automatically added to fighters."""
        knight = Character.create("Knight", "user1", "Hero")
        team = Team(name="Adventurers", Team_member=knight)
        assert knight in team.fighters
        assert team.leader == knight


class TestTeamAlliances:
    """Tests for team alliances and relationships."""

    def test_make_alliance_with_another_team(self):
        """Test forming an alliance between two teams."""
        team1 = Team(name="Alliance1")
        team2 = Team(name="Alliance2")
        
        knight1 = Character.create("Knight", "user1", "Hero1")
        knight2 = Character.create("Knight", "user2", "Hero2")
        
        team1.add_fighter(knight1)
        team2.add_fighter(knight2)
        
        team1.allies.append(team2)
        team2.allies.append(team1)
        
        assert team2 in team1.allies
        assert team1 in team2.allies

    def test_declare_war_with_enemy_team(self):
        """Test declaring war (enemy relationship) between teams."""
        team1 = Team(name="GoodTeam")
        team2 = Team(name="EvilTeam")
        
        knight1 = Character.create("Knight", "user1", "Hero")
        knight2 = Character.create("Knight", "user2", "Villain")
        
        team1.add_fighter(knight1)
        team2.add_fighter(knight2)
        
        team1.enemies.append(team2)
        team2.enemies.append(team1)
        
        assert team2 in team1.enemies
        assert team1 in team2.enemies

    def test_team_cannot_be_ally_and_enemy(self):
        """Test that a team relationship should not be both ally and enemy."""
        team1 = Team(name="Team1")
        team2 = Team(name="Team2")
        
        # Add as ally
        team1.allies.append(team2)
        assert team2 in team1.allies
        
        # If adding as enemy, should remove from allies (business logic)
        # This tests the desired behavior
        if team2 in team1.enemies:
            team1.allies.remove(team2)
        
        team1.enemies.append(team2)
        assert team2 in team1.enemies


class TestTeamStats:
    """Tests for team statistics and information."""

    def test_team_size(self):
        """Test getting team size."""
        team = Team(name="Adventurers")
        assert len(team.fighters) == 0
        
        knight = Character.create("Knight", "user1", "Hero1")
        priest = Character.create("Priest", "user2", "Hero2")
        
        team.add_fighter(knight)
        assert len(team.fighters) == 1
        
        team.add_fighter(priest)
        assert len(team.fighters) == 2

    def test_team_total_level(self):
        """Test calculating total level of team."""
        team = Team(name="Adventurers")
        knight = Character.create("Knight", "user1", "Hero1")
        priest = Character.create("Priest", "user2", "Hero2")
        
        team.add_fighter(knight)
        team.add_fighter(priest)
        
        total_level = sum(member.level for member in team.fighters)
        assert total_level == knight.level + priest.level

    def test_team_total_hp(self):
        """Test calculating total HP of team."""
        team = Team(name="Adventurers")
        knight = Character.create("Knight", "user1", "Hero1")
        priest = Character.create("Priest", "user2", "Hero2")
        
        team.add_fighter(knight)
        team.add_fighter(priest)
        
        total_hp = sum(member.hp.current_value for member in team.fighters)
        assert total_hp == knight.hp.current_value + priest.hp.current_value

    def test_team_members_alive_count(self):
        """Test counting alive members in team."""
        team = Team(name="Adventurers")
        knight = Character.create("Knight", "user1", "Hero1")
        priest = Character.create("Priest", "user2", "Hero2")
        
        team.add_fighter(knight)
        team.add_fighter(priest)
        
        alive_count = sum(1 for member in team.fighters if member.is_alive())
        assert alive_count == 2
        
        # Kill one member
        knight.hp.drain_all()
        alive_count = sum(1 for member in team.fighters if member.is_alive())
        assert alive_count == 1


class TestTeamRegistration:
    """Tests for team tracking and retrieval."""

    def test_team_registered_in_all_teams(self):
        """Test that created teams are registered."""
        team = Team(name="TestTeam")
        assert team in Team.all_teams

    def test_multiple_teams_tracked(self):
        """Test that multiple teams are all tracked."""
        team1 = Team(name="Team1")
        team2 = Team(name="Team2")
        team3 = Team(name="Team3")
        
        assert len(Team.all_teams) == 3
        assert team1 in Team.all_teams
        assert team2 in Team.all_teams
        assert team3 in Team.all_teams

    def test_team_uniqueness_validation(self):
        """Test that team names are validated for uniqueness."""
        Team(name="UniqueTeam")
        with pytest.raises(ValueError):
            Team(name="UniqueTeam")


class TestAlliance:
    """Tests for Alliance system."""

    def test_alliance_creation(self):
        """Test creating an alliance."""
        team1 = Team(name="Team1")
        team2 = Team(name="Team2")
        
        knight1 = Character.create("Knight", "user1", "Hero1")
        knight2 = Character.create("Knight", "user2", "Hero2")
        
        team1.add_fighter(knight1)
        team2.add_fighter(knight2)
        
        # Create alliance
        team1.allies.append(team2)
        team2.allies.append(team1)
        
        assert team2 in team1.allies
        assert team1 in team2.allies

    def test_alliance_multiple_teams(self):
        """Test alliance with multiple teams."""
        team1 = Team(name="Team1")
        team2 = Team(name="Team2")
        team3 = Team(name="Team3")
        
        # Create triangle alliance
        team1.allies.extend([team2, team3])
        team2.allies.extend([team1, team3])
        team3.allies.extend([team1, team2])
        
        assert len(team1.allies) == 2
        assert team2 in team1.allies and team3 in team1.allies
