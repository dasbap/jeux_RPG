from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum, auto

from _class.stats.basic_stat import DefaultStat, Energie, Mana

class SkillType(Enum):
    DAMAGE = auto()
    HEAL = auto()
    BUFF = auto()
    DEBUFF = auto()
    RESURRECT = auto()
    CUSTOM = auto()

@dataclass
class SkillEffect:
    value: int
    duration: int = 0
    stat_target: Optional[str] = None

class Skill:
    def __init__(
        self,
        name: str,
        skill_type: SkillType,
        effects: Dict[str, SkillEffect],
        energie_cost: int = 0,
        energie_target: type[Energie] = Mana,
        custom_action: Optional[Callable] = None,
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
        self.effects = effects
        self.energie_cost = energie_cost
        self.energie_target = energie_target
        self.custom_action = custom_action
        self.cooldown = cooldown
        self.current_cooldown = 0
        self.description = description or f"Compétence {name} de type {skill_type.name}"

    def __str__(self) -> str:
        costs = []
        if self.energie_cost > 0:
            costs.append(f"{self.energie_target.__name__}: {self.energie_cost}")
        cost_str = ", ".join(costs) if costs else "Aucun coût"
        return (f"{self.name} [{self.skill_type.name}] - {cost_str} - "
                f"Cooldown: {self.cooldown} - {self.description}")
    def __repr__(self):
        return f"{self.name, self.energie_target, self.energie_cost, self.current_cooldown}"

    def is_ready(self) -> bool:
        return self.current_cooldown <= 0

    def can_afford(self, caster: Any) -> bool:
        try :
            act = caster.get_energie(self.energie_target)
            if act.__class__ == self.energie_target:
                return True
        except :
            return False
        return False
    

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
                custom_result = self.custom_action(caster, target)
                if isinstance(custom_result, str):
                    result["message"] = custom_result
                elif isinstance(custom_result, dict):
                    result.update(custom_result)
            except Exception as e:
                result["success"] = False
                result["message"] = f"Erreur dans l'action personnalisée: {str(e)}"
        else:
            result.update(self._execute_default_action(caster, target))

        return result

    def _execute_default_action(self, caster: Any, target: Any) -> Dict[str, Any]:
        results = {
            "message": "",
            "effects": {}
        }

        if self.skill_type == SkillType.DAMAGE:
            damage = self.effects["damage"].value
            target.lose_hp(caster, damage)
            results["message"] = f"{caster.name} inflige {damage} dégâts à {target.name}!"
            results["effects"]["damage"] = damage

        elif self.skill_type == SkillType.HEAL:
            heal = self.effects["heal"].value
            target.gain_hp(heal)
            results["message"] = f"{caster.name} soigne {target.name} de {heal} HP!"
            results["effects"]["heal"] = heal

        elif self.skill_type == SkillType.RESURRECT:
            if not target.is_alive():
                target.resurrect(caster)
                results["message"] = f"{caster.name} ressuscite {target.name}!"
                results["effects"]["resurrect"] = True
            else:
                results["message"] = f"{target.name} ne peut pas être ressuscité!"
                results["success"] = False

        elif self.skill_type in (SkillType.BUFF, SkillType.DEBUFF):
            for effect_name, effect in self.effects.items():
                if effect.stat_target:
                    if self.skill_type == SkillType.BUFF:
                        target.buff_stat(effect.stat_target, effect.value, effect.duration)
                    else:
                        target.debuff_stat(effect.stat_target, effect.value, effect.duration)
                    results["effects"][effect_name] = {
                        "stat": effect.stat_target,
                        "value": effect.value,
                        "duration": effect.duration
                    }
            action = "augmente" if self.skill_type == SkillType.BUFF else "réduit"
            stats = ", ".join(e.stat_target for e in self.effects.values() if e.stat_target)
            results["message"] = f"{caster.name} {action} {stats} de {target.name}!"

        return results

    def update_cooldown(self) -> None:
        if self.current_cooldown > 0:
            self.current_cooldown -= 1

    def reset_cooldown(self) -> None:
        self.current_cooldown = 0

    @classmethod
    def create_simple_damage_skill(
        cls,
        name: str,
        damage: int,
        energie_cost: int,
        cooldown: int = 0
    ) -> 'Skill':
        return cls(
            name=name,
            skill_type=SkillType.DAMAGE,
            effects={"damage": SkillEffect(value=damage)},
            energie_cost=energie_cost,
            cooldown=cooldown,
            description=f"Inflige {damage} points de dégâts"
        )

    @classmethod
    def create_stat_modifier_skill(
        cls,
        name: str,
        stat_target: DefaultStat,
        value: int,
        duration: int,
        is_buff: bool = True,
        energie_cost: int = 0,
        cooldown: int = 0
    ) -> 'Skill':
        skill_type = SkillType.BUFF if is_buff else SkillType.DEBUFF
        return cls(
            name=name,
            skill_type=skill_type,
            effects={"modifier": SkillEffect(value=value, duration=duration, stat_target=stat_target)},
            energie_cost=energie_cost,
            cooldown=cooldown,
            description=f"{'Augmente' if is_buff else 'Réduit'} {stat_target} de {value} pendant {duration} tours"
        )
