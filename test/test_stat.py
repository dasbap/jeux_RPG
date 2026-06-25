"""
Tests pour la classe Stat et ses sous-classes.
"""

import pytest
from jeuxRPG._class.res.character.stats.stat import DefaultStat
from jeuxRPG._class.res.character.stats.basic_stat import HP, Mana, VitalStat, AttributeStat
from jeuxRPG._class.res.character.alteration.alteration import Buff, DeBuff


class TestDefaultStat:
    """Tests pour la classe DefaultStat."""
    
    def test_create_stat(self):
        """Test création d'une stat."""
        stat = DefaultStat(100)
        
        assert stat.value == 100
        assert stat.current_value == 100
        assert stat.name == "DefaultStat"
    
    def test_create_stat_negative_raises(self):
        """Test erreur pour valeur négative."""
        with pytest.raises(ValueError, match="positive integer"):
            DefaultStat(-10)
    
    def test_create_stat_not_int_raises(self):
        """Test erreur pour type non-entier."""
        with pytest.raises(ValueError):
            DefaultStat("100")
    
    def test_equality_with_int(self):
        """Test égalité avec un entier."""
        stat = DefaultStat(100)
        
        assert stat == 100
        assert not (stat == 50)
    
    def test_equality_with_stat(self):
        """Test égalité avec une autre stat."""
        stat1 = DefaultStat(100)
        stat2 = DefaultStat(100)
        
        assert stat1 == stat2
    
    def test_inequality(self):
        """Test inégalité."""
        stat = DefaultStat(100)
        
        assert stat != 50
        assert not (stat != 100)
    
    def test_greater_than(self):
        """Test supérieur à."""
        stat = DefaultStat(100)
        
        assert stat > 50
        assert not (stat > 100)
        assert not (stat > 150)
    
    def test_greater_or_equal(self):
        """Test supérieur ou égal."""
        stat = DefaultStat(100)
        
        assert stat >= 50
        assert stat >= 100
        assert not (stat >= 150)
    
    def test_less_than(self):
        """Test inférieur à."""
        stat = DefaultStat(100)
        
        assert stat < 150
        assert not (stat < 100)
        assert not (stat < 50)
    
    def test_less_or_equal(self):
        """Test inférieur ou égal."""
        stat = DefaultStat(100)
        
        assert stat <= 150
        assert stat <= 100
        assert not (stat <= 50)
    
    def test_iadd(self):
        """Test addition en place +=."""
        stat = DefaultStat(100)
        stat += 20
        
        assert stat.current_value == 120
    
    def test_iadd_not_int_raises(self):
        """Test erreur += avec non-entier."""
        stat = DefaultStat(100)
        
        with pytest.raises(TypeError, match="integers"):
            stat += "20"
    
    def test_isub(self):
        """Test soustraction en place -=."""
        stat = DefaultStat(100)
        stat -= 30
        
        assert stat.current_value == 70
    
    def test_isub_clamps_to_zero(self):
        """Test -= ne descend pas sous 0."""
        stat = DefaultStat(100)
        stat -= 150
        
        assert stat.current_value == 0
    
    def test_isub_not_int_raises(self):
        """Test erreur -= avec non-entier."""
        stat = DefaultStat(100)
        
        with pytest.raises(TypeError, match="integers"):
            stat -= "30"
    
    def test_add(self):
        """Test addition +."""
        stat = DefaultStat(100)
        stat + 20
        
        # Note: L'opérateur + modifie current_value
        assert stat.current_value >= 100
    
    def test_add_not_int_raises(self):
        """Test erreur + avec non-entier."""
        stat = DefaultStat(100)
        
        with pytest.raises(TypeError, match="integers"):
            stat + "20"
    
    def test_add_negative_raises(self):
        """Test erreur + avec valeur négative."""
        stat = DefaultStat(100)
        
        with pytest.raises(ValueError, match="positive"):
            stat + (-10)
    
    def test_sub(self):
        """Test soustraction -."""
        stat = DefaultStat(100)
        stat - 20
        
        assert stat.current_value <= 100
    
    def test_sub_not_int_raises(self):
        """Test erreur - avec non-entier."""
        stat = DefaultStat(100)
        
        with pytest.raises(TypeError, match="integers"):
            stat - "20"
    
    def test_sub_negative_raises(self):
        """Test erreur - avec valeur négative."""
        stat = DefaultStat(100)
        
        with pytest.raises(ValueError, match="positive"):
            stat - (-10)
    
    def test_str(self):
        """Test représentation string."""
        stat = DefaultStat(100)
        
        s = str(stat)
        
        assert "100" in s
        assert "DefaultStat" in s
    
    def test_repr(self):
        """Test représentation repr."""
        stat = DefaultStat(100)
        
        r = repr(stat)
        
        assert "DefaultStat" in r
        assert "100" in r
    
    def test_current_value_setter(self):
        """Test setter de current_value."""
        stat = DefaultStat(100)
        
        stat.current_value = 50
        
        assert stat.current_value == 50
    
    def test_current_value_setter_not_int_raises(self):
        """Test erreur setter avec non-entier."""
        stat = DefaultStat(100)
        
        with pytest.raises(ValueError, match="integer"):
            stat.current_value = "50"
    
    def test_current_value_clamps_negative(self):
        """Test que current_value ne descend pas sous 0."""
        stat = DefaultStat(100)
        
        stat.current_value = -50
        
        assert stat.current_value >= 0
    
    def test_name_property(self):
        """Test propriété name."""
        stat = DefaultStat(100)
        
        stat.name = "CustomStat"
        
        assert stat.name == "CustomStat"
    
    def test_change_type(self):
        """Test changement de type."""
        stat = DefaultStat(100)
        
        stat.change_type(VitalStat)
        
        assert isinstance(stat, VitalStat)
    
    def test_change_type_invalid_raises(self):
        """Test erreur changement vers type invalide."""
        stat = DefaultStat(100)
        
        with pytest.raises(TypeError):
            stat.change_type(str)
    
    def test_add_buff(self):
        """Test ajout d'un buff."""
        from jeuxRPG._class.sub_character.knight import Knight
        
        stat = DefaultStat(100)
        caster = Knight("test", "Caster")
        target = Knight("test2", "Target")
        buff = Buff("Force", caster, 5, 3, target, DefaultStat)
        
        stat.add_buff(buff)
        
        assert buff in stat.buffs
    
    def test_add_buff_invalid_raises(self):
        """Test erreur ajout buff invalide."""
        stat = DefaultStat(100)
        
        with pytest.raises(TypeError, match="Buff"):
            stat.add_buff("not a buff")
    
    def test_remove_buff(self):
        """Test suppression d'un buff."""
        from jeuxRPG._class.sub_character.knight import Knight
        
        stat = DefaultStat(100)
        caster = Knight("test", "Caster")
        target = Knight("test2", "Target")
        buff = Buff("Force", caster, 5, 3, target, DefaultStat)
        stat.add_buff(buff)
        
        result = stat.remove_buff(buff)
        
        assert result is True
        assert buff not in stat.buffs
    
    def test_remove_buff_not_found(self):
        """Test suppression buff non trouvé."""
        from jeuxRPG._class.sub_character.knight import Knight
        
        stat = DefaultStat(100)
        caster = Knight("test", "Caster")
        target = Knight("test2", "Target")
        buff = Buff("Force", caster, 5, 3, target, DefaultStat)
        
        result = stat.remove_buff(buff)
        
        assert result is False
    
    def test_add_debuff(self):
        """Test ajout d'un debuff."""
        from jeuxRPG._class.sub_character.knight import Knight
        
        stat = DefaultStat(100)
        caster = Knight("test", "Caster")
        target = Knight("test2", "Target")
        debuff = DeBuff("Faiblesse", caster, 5, 3, target, DefaultStat)
        
        stat.add_debuff(debuff)
        
        assert debuff in stat.debuffs
    
    def test_remove_debuff(self):
        """Test suppression d'un debuff."""
        from jeuxRPG._class.sub_character.knight import Knight
        
        stat = DefaultStat(100)
        caster = Knight("test", "Caster")
        target = Knight("test2", "Target")
        debuff = DeBuff("Faiblesse", caster, 5, 3, target, DefaultStat)
        stat.add_debuff(debuff)
        
        result = stat.remove_debuff(debuff)
        
        assert result is True
        assert debuff not in stat.debuffs
    
    def test_remove_debuff_not_found(self):
        """Test suppression debuff non trouvé."""
        from jeuxRPG._class.sub_character.knight import Knight
        
        stat = DefaultStat(100)
        caster = Knight("test", "Caster")
        target = Knight("test2", "Target")
        debuff = DeBuff("Faiblesse", caster, 5, 3, target, DefaultStat)
        
        result = stat.remove_debuff(debuff)
        
        assert result is False
    
    def test_clear_effects(self):
        """Test effacement de tous les effets."""
        from jeuxRPG._class.sub_character.knight import Knight
        
        stat = DefaultStat(100)
        caster = Knight("test", "Caster")
        target = Knight("test2", "Target")
        stat.add_buff(Buff("Force", caster, 5, 3, target, DefaultStat))
        stat.add_debuff(DeBuff("Faiblesse", caster, 5, 3, target, DefaultStat))
        
        stat.clear_effects()
        
        assert stat.buffs == []
        assert stat.debuffs == []
    
    def test_update_base_value(self):
        """Test mise à jour de la valeur de base."""
        stat = DefaultStat(100)
        
        stat.update_base_value(150)
        
        assert stat.value == 150
    
    def test_update_base_value_negative_raises(self):
        """Test erreur mise à jour valeur négative."""
        stat = DefaultStat(100)
        
        with pytest.raises(ValueError, match="positive"):
            stat.update_base_value(-10)
    
    def test_upgrade_base_value(self):
        """Test augmentation de la valeur de base."""
        stat = DefaultStat(100)
        
        stat.upgrade_base_value(20)
        
        assert stat.value == 120
    
    def test_upgrade_base_value_negative_raises(self):
        """Test erreur augmentation négative."""
        stat = DefaultStat(100)
        
        with pytest.raises(ValueError, match="positive"):
            stat.upgrade_base_value(-10)
    
    def test_get_effect_value(self):
        """Test récupération de la valeur des effets."""
        from jeuxRPG._class.sub_character.knight import Knight
        
        stat = DefaultStat(100)
        caster = Knight("test", "Caster")
        target = Knight("test2", "Target")
        stat.add_buff(Buff("Force", caster, 20, 3, target, DefaultStat))
        
        effect = stat.get_effect_value()
        
        assert effect == stat.current_value - 100
    
    def test_end_round(self):
        """Test fin de tour."""
        from jeuxRPG._class.sub_character.knight import Knight
        
        stat = DefaultStat(100)
        caster = Knight("test", "Caster")
        target = Knight("test2", "Target")
        buff = Buff("Force", caster, 5, 2, target, DefaultStat)  # Durée 2
        stat.add_buff(buff)
        
        stat.end_round()
        
        # Le buff devrait avoir sa durée diminuée
        assert buff.duration == 1
    
    def test_end_round_removes_expired(self):
        """Test fin de tour supprime effets expirés."""
        from jeuxRPG._class.sub_character.knight import Knight
        
        stat = DefaultStat(100)
        caster = Knight("test", "Caster")
        target = Knight("test2", "Target")
        buff = Buff("Force", caster, 5, 1, target, DefaultStat)  # Durée 1
        stat.add_buff(buff)
        
        stat.end_round()
        
        # Le buff devrait être retiré car expiré
        assert buff not in stat.buffs
    
    def test_set_max(self):
        """Test remise à la valeur max."""
        stat = DefaultStat(100)
        stat.current_value = 50
        
        stat.set_max()
        
        assert stat.current_value == 100


class TestHP:
    """Tests pour la classe HP."""
    
    def test_create_hp(self):
        """Test création d'HP."""
        hp = HP(100)
        
        assert hp.value == 100
        assert hp.current_value == 100
    
    def test_heal(self):
        """Test soin."""
        hp = HP(100)
        hp.current_value = 50
        
        healed = hp.heal(30)
        
        assert healed == 30
        assert hp.current_value == 80
    
    def test_heal_no_overheal(self):
        """Test pas de sursoin."""
        hp = HP(100)
        hp.current_value = 90
        
        healed = hp.heal(30)
        
        assert healed == 10  # Seulement 10 HP manquants
        assert hp.current_value == 100
    
    def test_heal_negative_returns_zero(self):
        """Test soin négatif retourne 0."""
        hp = HP(100)
        hp.current_value = 50
        
        healed = hp.heal(-10)
        
        assert healed == 0
        assert hp.current_value == 50


class TestMana:
    """Tests pour la classe Mana."""
    
    def test_create_mana(self):
        """Test création de mana."""
        mana = Mana(100)
        
        assert mana.value == 100
        assert mana.regen_rate == 0.15


class TestVitalStat:
    """Tests pour la classe VitalStat."""
    
    def test_is_full(self):
        """Test is_full."""
        vital = VitalStat(100)
        
        assert vital.is_full() is True
        
        vital.current_value = 50
        
        assert vital.is_full() is False
    
    def test_change_type_to_vital(self):
        """Test changement vers VitalStat."""
        vital = VitalStat(100)
        
        vital.change_type(HP)
        
        assert isinstance(vital, HP)
    
    def test_change_type_invalid_raises(self):
        """Test erreur changement vers type invalide."""
        vital = VitalStat(100)
        
        with pytest.raises(TypeError):
            vital.change_type(DefaultStat)


class TestAttributeStat:
    """Tests pour la classe AttributeStat."""
    
    def test_create_attribute(self):
        """Test création d'attribut."""
        attr = AttributeStat(50)
        
        assert attr.value == 50
    
    def test_str(self):
        """Test représentation string."""
        attr = AttributeStat(50)
        
        s = str(attr)
        
        assert "50" in s
    
    def test_change_type_invalid_raises(self):
        """Test erreur changement vers type invalide."""
        attr = AttributeStat(50)
        
        with pytest.raises(TypeError):
            attr.change_type(VitalStat)
