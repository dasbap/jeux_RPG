"""
Tests pour InvocationPocket et Invocation.
"""

import pytest
from jeuxRPG._class.sub_character.invocations.invocation import Invocation
from jeuxRPG._class.sub_character.invocations.squelette import Squelette
from jeuxRPG._class.res.character.invocation.invocation_pocket import InvocationPocket
from jeuxRPG._class.sub_character.necromancien import Necromancien
from jeuxRPG._class.sub_character.mage import Mage


class TestInvocationPocket:
    """Tests pour la classe InvocationPocket."""
    
    @pytest.fixture
    def master(self):
        """Crée un maître pour les tests."""
        return Necromancien("test", "TestNecro")
    
    @pytest.fixture
    def pocket(self, master):
        """Crée une poche d'invocation."""
        return InvocationPocket(master, limit=3)
    
    def test_create_pocket(self, master):
        """Test création d'une poche."""
        pocket = InvocationPocket(master, limit=5)
        
        assert pocket.master == master
        assert pocket.limit == 5
        assert pocket.invocations == []
    
    def test_add_invocation(self, pocket, master):
        """Test ajout d'une invocation."""
        invoc = Squelette(master)
        
        result = pocket.add_invocation(invoc)
        
        assert result is True
        assert invoc in pocket.invocations
    
    def test_add_invocation_limit_reached(self, master):
        """Test limite atteinte."""
        pocket = InvocationPocket(master, limit=1)
        invoc1 = Squelette(master)
        invoc2 = Squelette(master)
        
        pocket.add_invocation(invoc1)
        result = pocket.add_invocation(invoc2)
        
        assert result is False
        assert len(pocket.invocations) == 1
    
    def test_del_invocation(self, pocket, master):
        """Test suppression d'une invocation."""
        invoc = Squelette(master)
        pocket.add_invocation(invoc)
        
        pocket.del_invocation(invoc)
        
        assert invoc not in pocket.invocations
    
    def test_del_invocation_not_in_pocket(self, pocket, master):
        """Test suppression d'une invocation non présente."""
        invoc = Squelette(master)
        
        with pytest.raises(ValueError):
            pocket.del_invocation(invoc)
    
    def test_get_all(self, pocket, master):
        """Test récupération de toutes les invocations."""
        invoc1 = Squelette(master)
        invoc2 = Squelette(master)
        pocket.add_invocation(invoc1)
        pocket.add_invocation(invoc2)
        
        all_invocs = pocket.get_all()
        
        assert len(all_invocs) == 2
    
    def test_get_limit(self, pocket):
        """Test récupération de la limite."""
        assert pocket.get_limit() == 3
    
    def test_can_summon(self, pocket, master):
        """Test vérification si peut invoquer."""
        assert pocket.can_summon() is True
        
        # Remplir la poche
        for _ in range(3):
            pocket.add_invocation(Squelette(master))
        
        assert pocket.can_summon() is False
    
    def test_kill_all(self, pocket, master):
        """Test suppression de toutes les invocations."""
        pocket.add_invocation(Squelette(master))
        pocket.add_invocation(Squelette(master))
        
        pocket.kill_all()
        
        assert pocket.invocations == []
    
    def test_str(self, pocket, master):
        """Test représentation string."""
        invoc = Squelette(master)
        pocket.add_invocation(invoc)
        
        s = str(pocket)
        
        # Check that master name is in the string
        assert master.name in s


class TestInvocation:
    """Tests pour la classe Invocation."""
    
    @pytest.fixture(autouse=True)
    def clear_invocations(self):
        """Nettoyer les invocations entre les tests."""
        Invocation.all_invocation.clear()
        yield
        Invocation.all_invocation.clear()
    
    @pytest.fixture
    def master(self):
        """Crée un maître pour les tests."""
        return Necromancien("test", "TestNecro")
    
    def test_create_squelette(self, master):
        """Test création d'un squelette."""
        squelette = Squelette(master)
        
        assert squelette.master == master
        assert squelette in Invocation.all_invocation
    
    def test_default_name_format(self, master):
        """Test format du nom par défaut."""
        squelette = Squelette(master)
        
        # Le nom devrait contenir "Squelette" et le nom du maître
        assert "Squelette" in squelette.name
        assert master.name in squelette.name


class TestNecromancien:
    """Tests pour la classe Necromancien."""
    
    @pytest.fixture(autouse=True)
    def clear_invocations(self):
        """Nettoyer les invocations entre les tests."""
        Invocation.all_invocation.clear()
        yield
        Invocation.all_invocation.clear()
    
    def test_create_necromancien(self):
        """Test création d'un nécromancien."""
        necro = Necromancien("user1", "DarkMage")
        
        assert necro.name == "DarkMage"
        assert necro.is_playable is True
    
    def test_necromancien_has_invocation_pocket(self):
        """Test que le nécromancien a une poche d'invocation."""
        necro = Necromancien("user1", "DarkMage")
        
        assert hasattr(necro, 'invocations')
    
    def test_necromancien_attack_basic(self):
        """Test que le nécromancien peut attaquer."""
        necro = Necromancien("user1", "DarkMage")
        target = Mage("user2", "Target")
        
        # Exécuter une attaque
        success, message = necro.attack(target)
        
        # Devrait retourner un tuple (bool, str)
        assert isinstance(success, bool)
        assert isinstance(message, str)
