import copy
import logging
from typing import Any, Callable, Dict, Optional, Tuple, Union

from jeuxRPG.i18n import t
from jeuxRPG._class.res.character.alteration.alteration import AlterationType
from jeuxRPG._class.res.character.stats.basic_stat import AttributeStat, Energie, Force, Intelligence, Mana, Sagesse
from jeuxRPG._class.res.classType import DamageType, SkillType
from jeuxRPG._class.skills.skillEffect import SkillEffect


class Skill:
    all_Skills: list['Skill'] = []
    def __init__(
        self,
        name: str,
        skill_type: SkillType,
        effects: Dict[str, SkillEffect],
        require_target : bool = True,
        can_target_others = True,
        energie_cost: int = 0,
        damage_type: Optional[DamageType] = None,
        energie_target: type[Energie] = Mana,
        custom_action: Optional[Callable[[Any, Any, 'Skill'], Dict]] = None,
        cooldown: int = 0,
        description: str = ""
    ):
        if energie_cost < 0:
            raise ValueError("Les coûts ne peuvent pas être négatifs")
        if not isinstance(energie_target, type) or not issubclass(energie_target, Energie):
            raise TypeError("`energie_target` doit être une sous-classe de `Energie`")
        if cooldown < 0:
            raise ValueError("Le cooldown ne peut pas être négatif")
        for effect in effects.values():
            if effect.duration < 0:
                raise ValueError("La durée des effets ne peut pas être négative")

        self.name = name
        self.skill_type = skill_type
        self.DamageType = damage_type
        self.effects = effects
        self.requires_target = require_target
        self.can_target_others = can_target_others
        self.energie_cost = energie_cost
        self.energie_target = energie_target
        self.custom_action = custom_action
        self.cooldown = cooldown
        self.current_cooldown = 0
        self.description = description or t("skill.default_desc", name=name, skill_type=skill_type.name)
        self._register_skill()
        
    def __str__(self) -> str:
        costs = []
        if self.energie_cost > 0:
            costs.append(f"{self.energie_target.__name__}: {self.energie_cost}")
        cost_str = ", ".join(costs) if costs else t("skill.no_cost")
        return t("skill.str", name=self.name, skill_type=self.skill_type.name, 
                 cost_str=cost_str, cooldown=self.cooldown, description=self.description)
    def __repr__(self):
        return f"{self.name} (cost: {self.energie_cost} {self.energie_target.__name__}, cooldown: {self.current_cooldown})"

    def _register_skill(self):
        """Enregistre le sort s'il est unique"""
        if not any(skill.name.lower() == self.name.lower() 
                for skill in Skill.all_Skills):
            Skill.all_Skills.append(self)
    
    def is_ready(self) -> bool:
        return self.current_cooldown <= 0

    def can_afford(self, caster: Any) -> bool:
        try:
            act = caster.get_energie(self.energie_target)
            return isinstance(act, self.energie_target) and act.current_value >= self.energie_cost
        except (AttributeError, TypeError):
            return False
    
    def get_true_damage(self, caster, target):
        copy_caster = copy.deepcopy(caster)
        copy_target = copy.deepcopy(target)
        copy_skill = copy.deepcopy(self)
        result = copy_skill.execute(copy_caster, copy_target)
        return result.get("effects", {}).get("true_damage", 0) or 0

    def setcooldown(self) -> None:
        if self.current_cooldown > 0: raise RuntimeError(f"cooldown is not ready for : {self.name}")
        self.current_cooldown = self.cooldown
    
    def execute(self, caster: Any, target: Any) -> Dict[str, Any]:
        if not self.is_ready():
            raise RuntimeError(f"Compétence {self.name} en cooldown")
        if not self.can_afford(caster):
            return {
                "success": False,
                "message": f"{caster.name} n'a pas assez de {self.energie_target.__name__} pour utiliser {self.name}",
                "effects": {}
            }

        result = {
            "success": True,
            "message": "",
            "effects": {}
        }

        caster.consume_energie(self.energie_cost, self.energie_target)
        self.setcooldown()

        if self.custom_action:
            try:
                custom_result = self.custom_action(caster, target, self)
                if not isinstance(custom_result, dict):raise ValueError("custom action must return a dict")
                else:
                    result.update(custom_result)
            except Exception as e:
                result["success"] = False
                result["message"] = f"Erreur dans l'action personnalisée: {str(e)}"
        else:
            result.update(self._execute_default_action(caster, target))

        return result

    def special_action(self, caster, target) -> Dict[str, Any]:
        return self._execute_default_action(caster, target)

    def _execute_default_action(self, caster: Any, target: Any) -> Dict[str, Any]:
        """Exécute l'action par défaut en fonction du type de compétence"""
        results = {
            "message": "",
            "effects": {},
            "success": True
        }

        action_handlers = {
            SkillType.DAMAGE: self._execute_damage_action,
            SkillType.HEAL: self._execute_heal_action,
            SkillType.RESURRECT: self._execute_resurrect_action,
            SkillType.INVOCATION: self._execute_invocation_action,
            SkillType.BUFF: self._execute_buff_debuff_action,
            SkillType.DEBUFF: self._execute_buff_debuff_action
        }

        handler = action_handlers.get(self.skill_type)
        if handler:
            return handler(caster, target, results)
        else:
            raise NotImplementedError(f"Skill type {self.skill_type} not implemented")

    # --- Actions séparées ---

    def _execute_damage_action(self, caster: Any, target: Any, results: Dict[str, Any]) -> Dict[str, Any]:
        """Gère les actions de dégâts"""
        def calculate_damage(caster_stat_instance: AttributeStat) -> int:
            import math
            base_damage = self.effects["damage"].value
            stat_value = caster_stat_instance.current_value
            stat_factor = (stat_value ** 0.2) / 2
            damage = base_damage * max(1, math.log((1 + stat_factor)))
            return int(max(1, damage))

        stat_mapping = {
            DamageType.PHYSICAL: Force,
            DamageType.MAGIC: Intelligence,
            DamageType.SACRED: Sagesse
        }

        stat_target = stat_mapping.get(self.DamageType)
        if not stat_target:
            raise NotImplementedError(f"Damage type {self.DamageType.name} not implemented")

        caster_stat = caster.status["stats"][stat_target.__name__]
        damage = calculate_damage(caster_stat)

        # Apply target advantage/resilience on damage type if available
        modifier = 1.0
        try:
            adv = getattr(target, "class_table", {}).get("advantage", None)
            if adv is not None and self.DamageType is not None:
                weak_list = None
                resi_list = None
                # Support Advantage instance or dict forms
                if hasattr(adv, "get_weakness"):
                    weak_list = set(adv.get_weakness())
                    resi_list = set(adv.get_resilience())
                elif isinstance(adv, dict):
                    weak_list = set(adv.get("weakness", adv.get("weak", [])))
                    resi_list = set(adv.get("resilience", adv.get("resilient", [])))
                if weak_list is not None and self.DamageType in weak_list:
                    # Weakness factor tuned empirically
                    modifier *= 1.8
                if resi_list is not None and self.DamageType in resi_list:
                    # Stronger resilience factor
                    modifier *= 0.6
        except Exception:
            # If anything goes wrong, ignore advantage modifiers
            pass

        damage = int(max(1, damage * modifier))
        initial_hp = target.get_stat("HP").current_value
        
        results["message"] = target.lose_hp(caster, damage)
        results["effects"]["true_damage"] = initial_hp - target.get_stat("HP").current_value
        
        return results

    def _execute_heal_action(self, caster: Any, target: Any, results: Dict[str, Any]) -> Dict[str, Any]:
        """Gère les actions de soin"""
        heal = self.effects["heal"].value
        target.gain_hp(heal)
        results["message"] = f"{caster.name} soigne {target.name} de {heal} HP!"
        results["effects"]["heal"] = heal
        return results

    def _execute_resurrect_action(self, caster: Any, target: Any, results: Dict[str, Any]) -> Dict[str, Any]:
        """Gère les actions de résurrection"""
        if not target.is_alive():
            target.resurrect(caster)
            results["message"] = f"{caster.name} ressuscite {target.name}!"
            results["effects"]["resurrect"] = True
        else:
            results["message"] = f"{target.name} ne peut pas être ressuscité!"
            results["success"] = False
        return results

    def _execute_invocation_action(self, caster: Any, target: Any, results: Dict[str, Any]) -> Dict[str, Any]:
        """Gère les actions d'invocation"""
        dict_invoc = self.effects["invocation"].invocation
        
        if len(caster.invocations.get_all()) >= caster.invocations.get_limit():
            results["message"] = f"{caster.name} ne peut pas invoquer !"
            results["success"] = False
        else:
            invocation = caster.__class__.create(
                dict_invoc["class"],
                master=caster,
                level=dict_invoc["level"]
            )
            caster.invocations.add_invocation(invocation)
            results["message"] = f"{caster.name} a invoqué un {invocation.__class__.__name__} !"
            results["success"] = True
            results["invocation"] = invocation
        
        return results

    def _execute_buff_debuff_action(self, caster: Any, target: Any, results: Dict[str, Any]) -> Dict[str, Any]:
        """Gère les actions de buff/debuff"""
        target = target or caster
        effects = self.effects
        total_pass = total_success = 0
        all_message = ""
        effects_list = []

        def process_effects(effect_item: Union[SkillEffect, list[SkillEffect]]):
            nonlocal total_pass, total_success, all_message, effects_list
            items = [effect_item] if isinstance(effect_item, SkillEffect) else (effect_item or [])
            for eff in items:
                success, message, _ = target.add_alteration(caster, eff)
                total_pass += 1
                if success:
                    total_success += 1
                    effects_list.append(
                        f"{eff.stat_target.__name__} {'+' if eff.alterationtype == AlterationType.BUFFSTAT else '-'}{eff.value}"
                    )
            all_message = ", ".join(effects_list)

        process_effects(effects.get("Buff", []))
        process_effects(effects.get("Debuff", []))

        results["effects"] = ", ".join(effects_list)
        results["message"] = f"Altérations appliquées sur {target.name} par {caster.name} : {total_success}/{total_pass} {all_message}"
        
        return results

    def update_cooldown(self) -> None:
        if self.current_cooldown > 0:
            self.current_cooldown -= 1

    def reset_cooldown(self) -> None:
        self.current_cooldown = 0

    @classmethod
    def apply_alteration(cls,caster, target = None, skill_effect : SkillEffect = None) ->tuple[bool, str]:
        if not skill_effect: raise ValueError("skill_effect must be given")
        target = target if target else caster
        ok, msg, _ = target.add_alteration(caster, skill_effect)
        return ok, msg
    
    @classmethod
    def get_skill_by_name(cls, name: str) -> 'Skill':
        """Retourne le skill ou lève une exception si non trouvé"""
        skill = next((s for s in cls.all_Skills if s.name.lower() == name.lower()), None)
        if skill is None:
            raise ValueError(f"Skill '{name}' not found")
        return skill
        
