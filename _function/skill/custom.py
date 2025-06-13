from typing import Any, Callable, Union
from _class.skills.skill import Skill

def handle_damage_effect(caster, target, effect) -> dict[str, Union[bool,str,dict[str,int]]]:
    """Gère spécifiquement l'effet de dégâts"""
    damage = effect.value + int(caster.status["stats"]["Force"].current_value * 0.5)
    initial_hp = target.get_stat("HP").current_value
    message = target.lose_hp(caster, damage)
    true_damage = initial_hp - target.get_stat("HP").current_value
    result = {
        "success" : True,
        "message": message,
        "effects" :{
            "true_damage": true_damage
            }
    }
    return result

def handle_stun_effect(caster, target, effect) -> dict[str, Union[bool,str, dict[str,dict]]]:
    """Gère spécifiquement l'effet de stun"""
    success, message, alteration = target.add_alteration(caster, effect)
    message = f"{caster.name} use {effect.name} : {message}"
    effect_dict = {alteration.name : alteration} if success else {}
    return {"success" : success, "message" : message, "effect": effect_dict}


def multy_action_skill(caster, target, skill: Skill) -> dict:
    """Version modulaire avec gestion séparée des effets"""
    effect_handlers : dict[str , Callable[[Any,Any,Any], dict[str,Any]]]= {
        "damage": handle_damage_effect,
        "Stun": handle_stun_effect
    }
    
    result : dict[str,Union[bool, list, dict]] = {
        "success":True,
        "message":[],
        "effect":{}
    }
    
    for effect_name, effect in skill.effects.items():
        if effect_name in effect_handlers:
            result_of = effect_handlers[effect_name](caster, target, effect)
            result["message"].append(result_of["message"])
            if result_of["success"] == False:
                success = False
        else:
            NotImplementedError(f"no funct for {effect_name}")
    
    return result
