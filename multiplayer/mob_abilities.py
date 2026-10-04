import math
from copy import deepcopy

from . import progression


def self_target(ability):
    if ability['type'] == 'heal':
        return True
    if ability.get('native'):
        from .skill_catalog import builtins
        return builtins()[ability['native']].skill_type.name not in ('DAMAGE','DEBUFF')
    return False


def advance(party, mob, target, characters, units, preset, now, messages):
    from .tutorial import unpack, pack
    from . import tactics
    abilities = mob.get('abilities', [])
    cast = mob.get('ability_cast')
    if cast:
        ability = cast['ability']
        key = cast['target']
        own = self_target(ability)
        if not own and (ability['range'] == 0 or key not in units or not characters[key].is_alive() or not tactics.sees(preset,mob,units[key]) or tactics.distance(mob['position'],units[key]['position']) > ability['range']):
            mob.pop('ability_cast',None)
            messages.append(f"{mob['name']} : cible perdue, {ability['name']} annulée.")
            return False
        if cast['ends_at'] > now:
            mob['intent'] = f"{ability['name']} · {(cast['ends_at']-now)/progression.RATIO:.1f} s"
            return True
        source = unpack(mob)
        actor = source if own else characters[key]
        before = actor.hp.current_value
        invocations_before = sum(invoc.hp.current_value for invoc in actor.invocations.get_all())
        success = True
        if ability.get('native'):
            from .skill_catalog import builtins
            skill = deepcopy(builtins()[ability['native']])
            skill.energie_cost = ability['cost']
            skill.current_cooldown = 0
            source.skills[skill.name] = skill
            progression.scale_skill(source,skill)
            actor.drop_xp = lambda killer: ''
            success, _ = source.use_skill(skill.name,actor)
            mob.update(pack(source))
        else:
            power = max(1, round(ability['power']+ability['growth']*(mob['level']-1)))
            if own:
                source.gain_hp(power)
                mob.update(pack(source))
            elif ability['type'] == 'damage':
                actor.drop_xp = lambda killer: ''
                actor.lose_hp(source,power)
            else:
                actor.add_stun(source,ability['name'],max(1,math.ceil(ability.get('duration',2)/progression.ACTION_SECONDS)))
        if not own:
            party.setdefault('effect_at',{})[key] = now+progression.ACTION_SECONDS*progression.RATIO
            if actor.is_stunned():
                units[key]['route'] = []
                units[key].pop('casting',None)
            invocations_after = sum(invoc.hp.current_value for invoc in actor.invocations.get_all())
            if actor.hp.current_value < before or invocations_after < invocations_before:
                party['battle']['damage_received'] = True
                if units[key].get('casting',{}).get('concentration'):
                    units[key].pop('casting',None)
        mob.pop('ability_cast',None)
        mob.setdefault('ability_ready',{})[ability['name']] = now+ability['cooldown']*progression.RATIO
        mob['next_attack'] = now+progression.ACTION_SECONDS*progression.RATIO
        messages.append(f"{mob['name']} {'utilise' if success else 'ne peut pas utiliser'} {ability['name']}." )
        return True
    for ability in abilities:
        if mob.get('ability_ready',{}).get(ability['name'],0) > now or mob.get('next_attack',0) > now:
            continue
        own = self_target(ability)
        if own:
            if ability['type'] == 'heal' or ability.get('native') and ability['native'].endswith(':Heal'):
                if mob['stats']['hp']['current'] >= mob['stats']['hp']['max']:
                    continue
            key = None
        else:
            if ability['range'] == 0 or not target or not tactics.sees(preset,mob,units[target]) or tactics.distance(mob['position'],units[target]['position']) > ability['range']:
                continue
            key = target
        if ability.get('native'):
            from .skill_catalog import builtins
            energy_name = builtins()[ability['native']].energie_target.__name__
            elapsed = max(0,now-mob.get('energy_at',now))/progression.RATIO
            for energy in mob['energies']:
                energy['current'] = min(energy['max'],energy['current']+elapsed)
            mob['energy_at'] = now
            if not any(energy['type'] == energy_name and energy['current'] >= ability['cost'] for energy in mob['energies']):
                continue
        mob['windup_until'] = None
        mob['ability_cast'] = {'ability':ability, 'target':key, 'ends_at':now+ability['cast']*progression.RATIO, 'concentration':ability.get('concentration',True)}
        mob['intent'] = 'Va utiliser '+ability['name']
        messages.append(f"{mob['name']} prépare {ability['name']}.")
        return True
    return False
