"""
Tests pour la classe Resource.
"""

import pytest
from jeuxRPG._class.res.resource_type.resource import Resource


class TestResource:
    """Tests pour la classe Resource."""
    
    def test_create_resource(self):
        """Test création d'une ressource."""
        res = Resource("Bois", 100, "matériau", "commun")
        assert res.name == "Bois"
        assert res.quantity == 100
        assert res.type == "matériau"
        assert res.rarity == "commun"
    
    def test_create_resource_defaults(self):
        """Test valeurs par défaut."""
        res = Resource("Pierre")
        assert res.quantity == 0
        assert res.type == "générique"
        assert res.rarity == "commun"
    
    def test_add_resources(self):
        """Test addition de deux ressources identiques."""
        res1 = Resource("Bois", 50, "matériau", "commun")
        res2 = Resource("Bois", 30, "matériau", "commun")
        
        result = res1 + res2
        
        assert result.quantity == 80
        assert result.name == "Bois"
    
    def test_add_resource_int(self):
        """Test addition avec un entier."""
        res = Resource("Bois", 50)
        result = res + 25
        
        assert result.quantity == 75
    
    def test_add_different_resources_raises(self):
        """Test erreur pour addition de ressources différentes."""
        res1 = Resource("Bois", 50)
        res2 = Resource("Pierre", 30)
        
        with pytest.raises(ValueError):
            res1 + res2
    
    def test_sub_resources(self):
        """Test soustraction de deux ressources identiques."""
        res1 = Resource("Bois", 50, "matériau", "commun")
        res2 = Resource("Bois", 30, "matériau", "commun")
        
        result = res1 - res2
        
        assert result.quantity == 20
    
    def test_sub_resource_int(self):
        """Test soustraction avec un entier."""
        res = Resource("Bois", 50)
        result = res - 25
        
        assert result.quantity == 25
    
    def test_sub_negative_raises(self):
        """Test erreur pour quantité négative."""
        res1 = Resource("Bois", 30)
        res2 = Resource("Bois", 50)
        
        with pytest.raises(ValueError, match="[Nn]egative|négative"):
            res1 - res2
    
    def test_sub_int_negative_raises(self):
        """Test erreur pour soustraction int négative."""
        res = Resource("Bois", 30)
        
        with pytest.raises(ValueError, match="[Nn]egative|négative"):
            res - 50
    
    def test_sub_different_resources_raises(self):
        """Test erreur pour soustraction de ressources différentes."""
        res1 = Resource("Bois", 50)
        res2 = Resource("Pierre", 30)
        
        with pytest.raises(ValueError):
            res1 - res2
    
    def test_iadd_resource(self):
        """Test addition en place avec ressource."""
        res1 = Resource("Bois", 50, "matériau", "commun")
        res2 = Resource("Bois", 30, "matériau", "commun")
        
        res1 += res2
        
        assert res1.quantity == 80
    
    def test_iadd_int(self):
        """Test addition en place avec entier."""
        res = Resource("Bois", 50)
        res += 25
        
        assert res.quantity == 75
    
    def test_iadd_invalid_raises(self):
        """Test erreur pour += invalide."""
        res = Resource("Bois", 50)
        
        with pytest.raises(ValueError, match="[Ii]nvalid|invalide"):
            res += "string"
    
    def test_isub_resource(self):
        """Test soustraction en place avec ressource."""
        res1 = Resource("Bois", 50, "matériau", "commun")
        res2 = Resource("Bois", 30, "matériau", "commun")
        
        res1 -= res2
        
        assert res1.quantity == 20
    
    def test_isub_int(self):
        """Test soustraction en place avec entier."""
        res = Resource("Bois", 50)
        res -= 25
        
        assert res.quantity == 25
    
    def test_isub_negative_raises(self):
        """Test erreur pour -= négatif."""
        res1 = Resource("Bois", 30)
        res2 = Resource("Bois", 50)
        
        with pytest.raises(ValueError, match="[Nn]egative|négative"):
            res1 -= res2
    
    def test_isub_int_negative_raises(self):
        """Test erreur pour -= int négatif."""
        res = Resource("Bois", 30)
        
        with pytest.raises(ValueError, match="[Nn]egative|négative"):
            res -= 50
    
    def test_isub_invalid_raises(self):
        """Test erreur pour -= invalide."""
        res = Resource("Bois", 50)
        
        with pytest.raises(ValueError, match="[Ii]nvalid|invalide"):
            res -= "string"
    
    def test_equality(self):
        """Test égalité de ressources."""
        res1 = Resource("Bois", 50, "matériau", "commun")
        res2 = Resource("Bois", 100, "matériau", "commun")  # Quantité différente
        
        assert res1 == res2  # Égalité basée sur nom/type/rareté, pas quantité
    
    def test_inequality(self):
        """Test inégalité de ressources."""
        res1 = Resource("Bois", 50)
        res2 = Resource("Pierre", 50)
        
        assert res1 != res2
    
    def test_inequality_type(self):
        """Test inégalité par type."""
        res1 = Resource("Bois", 50, "matériau")
        res2 = Resource("Bois", 50, "combustible")
        
        assert res1 != res2
    
    def test_str(self):
        """Test représentation string."""
        res = Resource("Bois", 50, "matériau", "rare")
        
        s = str(res)
        
        assert "50x" in s
        assert "Bois" in s
        assert "matériau" in s
        assert "rare" in s
    
    def test_repr(self):
        """Test représentation repr."""
        res = Resource("Bois", 50, "matériau", "rare")
        
        r = repr(res)
        
        assert "Resource" in r
        assert "Bois" in r
        assert "50" in r
