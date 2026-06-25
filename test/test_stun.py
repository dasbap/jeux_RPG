"""
Tests pour le système de Stun.
"""

import pytest
from jeuxRPG._class.character import Character
from jeuxRPG._class.sub_character.knight import Knight
from jeuxRPG._class.sub_character.mage import Mage
from jeuxRPG._class.sub_character.dragon_whelp import DragonWhelp
from jeuxRPG._class.res.character.alteration.alteration import Stun, AlterationType


class TestStunApplication:
    """Tests pour l'application du stun."""
    
    def test_add_stun_success(self):
        """Test ajout d'un stun avec succès."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        success, message, stun = knight.add_stun(mage, "Coup de bouclier", 2)
        
        assert success is True
        assert "stunned" in message
        assert "2 rounds" in message
        assert stun is not None
        assert stun.duration == 2
    
    def test_add_stun_single_round(self):
        """Test message singulier pour 1 round."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        success, message, stun = knight.add_stun(mage, "Quick stun", 1)
        
        assert "1 round!" in message
        assert "rounds" not in message
    
    def test_add_stun_invalid_duration(self):
        """Test stun avec durée invalide."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        success, message, stun = knight.add_stun(mage, "Bad stun", 0)
        
        assert success is False
        assert "positive" in message
        assert stun is None
    
    def test_add_stun_negative_duration(self):
        """Test stun avec durée négative."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        success, message, stun = knight.add_stun(mage, "Bad stun", -1)
        
        assert success is False
        assert stun is None


class TestStunStatus:
    """Tests pour la vérification du statut stun."""
    
    def test_is_stun_false_initially(self):
        """Test qu'un personnage n'est pas étourdi au départ."""
        knight = Knight("user1", "Sir Knight")
        
        assert knight.is_stun() is False
        assert knight.is_stunned() is False
    
    def test_is_stun_after_stun(self):
        """Test is_stun après application d'un stun."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        knight.add_stun(mage, "Test stun", 2)
        
        assert knight.is_stun() is True
        assert knight.is_stunned() is True
    
    def test_get_stuns(self):
        """Test récupération des stuns actifs."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        knight.add_stun(mage, "Stun 1", 2)
        knight.add_stun(mage, "Stun 2", 3)
        
        stuns = knight.get_stuns()
        
        assert len(stuns) == 2
    
    def test_get_stuns_returns_copy(self):
        """Test que get_stuns retourne une copie."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        knight.add_stun(mage, "Test stun", 2)
        
        stuns = knight.get_stuns()
        stuns.clear()
        
        assert knight.is_stun() is True
    
    def test_get_stun_duration(self):
        """Test récupération de la durée de stun restante."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        knight.add_stun(mage, "Short stun", 1)
        knight.add_stun(mage, "Long stun", 5)
        
        duration = knight.get_stun_duration()
        
        assert duration == 5  # Le plus long
    
    def test_get_stun_duration_no_stun(self):
        """Test durée de stun quand pas étourdi."""
        knight = Knight("user1", "Sir Knight")
        
        duration = knight.get_stun_duration()
        
        assert duration == 0


class TestStunRemoval:
    """Tests pour la suppression du stun."""
    
    def test_remove_stun(self):
        """Test suppression d'un stun spécifique."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        _, _, stun = knight.add_stun(mage, "Test stun", 2)
        
        result = knight.remove_stun(stun)
        
        assert result is True
        assert knight.is_stun() is False
    
    def test_remove_stun_not_found(self):
        """Test suppression d'un stun non présent."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        stun = Stun("Fake stun", mage, 2, knight)
        
        result = knight.remove_stun(stun)
        
        assert result is False
    
    def test_clear_stuns(self):
        """Test suppression de tous les stuns."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        knight.add_stun(mage, "Stun 1", 2)
        knight.add_stun(mage, "Stun 2", 3)
        
        count = knight.clear_stuns()
        
        assert count == 2
        assert knight.is_stun() is False
    
    def test_clear_stuns_empty(self):
        """Test clear_stuns quand pas de stun."""
        knight = Knight("user1", "Sir Knight")
        
        count = knight.clear_stuns()
        
        assert count == 0


class TestStunExpiration:
    """Tests pour l'expiration du stun."""
    
    def test_stun_decreases(self):
        """Test que le stun diminue à chaque tour."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        _, _, stun = knight.add_stun(mage, "Test stun", 3)
        
        stun.decrease()
        
        assert stun.duration == 2
    
    def test_stun_expires(self):
        """Test que le stun expire après sa durée."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        _, _, stun = knight.add_stun(mage, "Test stun", 1)
        
        stun.decrease()
        
        assert stun.is_over() is True
    
    def test_is_stun_filters_expired(self):
        """Test que is_stun ignore les stuns expirés."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        _, _, stun = knight.add_stun(mage, "Test stun", 1)
        stun.decrease()  # Expire le stun
        
        # Le stun est expiré mais toujours dans la liste
        assert stun.is_over() is True
        # is_stun devrait filtrer les expirés
        assert knight.is_stun() is False


class TestStunInCombat:
    """Tests pour le stun en combat."""
    
    def test_dragon_whelp_wing_buffet_stuns(self):
        """Test que Wing Buffet du Dragon Whelp applique un stun."""
        dragon = DragonWhelp("user1", "Drogon")
        knight = Knight("user2", "Sir Knight")
        
        # Wing Buffet devrait appliquer un stun
        success, message = dragon.use_skill("Wing Buffet", knight)
        
        if success:
            assert knight.is_stun() is True


class TestStunClass:
    """Tests pour la classe Stun elle-même."""
    
    def test_stun_creation(self):
        """Test création d'un objet Stun."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        stun = Stun("Test Stun", mage, 3, knight)
        
        assert stun.name == "Test Stun"
        assert stun.caster == mage
        assert stun.duration == 3
        assert stun.target == knight
        assert stun.type == AlterationType.STUN
    
    def test_stun_value_is_zero(self):
        """Test que la valeur du stun est toujours 0."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        stun = Stun("Test Stun", mage, 3, knight)
        
        assert stun.value == 0
    
    def test_stun_get_methods(self):
        """Test les méthodes get du stun."""
        knight = Knight("user1", "Sir Knight")
        mage = Mage("user2", "Gandalf")
        
        stun = Stun("Test Stun", mage, 3, knight)
        
        assert stun.get_caster() == mage
        assert stun.get_target() == knight
        assert stun.get_duration() == 3
        assert stun.get_value() == 0
