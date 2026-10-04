import math

from . import progression


def advance(party, mob, target, characters, units, preset, now, messages):
    from .tutorial import unpack, pack
    from . import tactics
    abilities = mob.get('abilities', [])
    cast = mob.get('ability_cast')
    if cast:
        ability = cast['ability']
        key = cast['target']
        if ability['type'] != 'heal' and (key not in units or not characters[key].is_alive() or not tactics.sees(preset,mob,units[key]) or tactics.distance(mob['position'],units[key]['position']) > ability['range']):
            mob.pop('ability_cast',None)
            messages.append(f"{mob['name']} : cible perdue, {ability['name']} annulée.")
            return False
        if cast['ends_at'] > now:
            mob['intent'] = f"{ability['name']} · {(cast['ends_at']-now)/progression.RATIO:.1f} s"
            return True
        source = unpack(mob)
        power = max(1, round(ability['power']+ability['growth']*(mob['level']-1)))
        if ability['type'] == 'heal':
            source.gain_hp(power)
            mob.update(pack(source))
        else:
            actor = characters[key]
            before = actor.hp.current_value
            invocations_before = sum(invoc.hp.current_value for invoc in actor.invocations.get_all()) if hasattr(actor,'invocations') else 0
            actor.drop_xp = lambda killer: ''
            if ability['type'] == 'damage':
                actor.lose_hp(source,power)
            else:
                actor.add_stun(source,ability['name'],max(1,math.ceil(ability.get('duration',2)/progression.ACTION_SECONDS)))
                party.setdefault('effect_at',{})[key] = now+progression.ACTION_SECONDS*progression.RATIO
                units[key]['route'] = []
                units[key].pop('casting',None)
            invocations_after = sum(invoc.hp.current_value for invoc in actor.invocations.get_all()) if hasattr(actor,'invocations') else 0
            if actor.hp.current_value < before or invocations_after < invocations_before:
                party['battle']['damage_received'] = True
                if units[key].get('casting',{}).get('concentration'):
                    units[key].pop('casting',None)
        mob.pop('ability_cast',None)
        mob.setdefault('ability_ready',{})[ability['name']] = now+ability['cooldown']*progression.RATIO
        mob['next_attack'] = now+progression.ACTION_SECONDS*progression.RATIO
        messages.append(f"{mob['name']} utilise {ability['name']} : {'soin' if ability['type'] == 'heal' else 'étourdissement' if ability['type'] == 'stun' else str(power)+' dégâts avant réduction'}.")
        return True
    for ability in abilities:
        if mob.get('ability_ready',{}).get(ability['name'],0) > now or mob.get('next_attack',0) > now:
            continue
        if ability['type'] == 'heal':
            if mob['stats']['hp']['current'] >= mob['stats']['hp']['max']:
                continue
            key = None
        else:
            if not target or not tactics.sees(preset,mob,units[target]) or tactics.distance(mob['position'],units[target]['position']) > ability['range']:
                continue
            key = target
        mob['windup_until'] = None
        mob['ability_cast'] = {'ability':ability, 'target':key, 'ends_at':now+ability['cast']*progression.RATIO, 'concentration':ability.get('concentration',True)}
        mob['intent'] = 'Va utiliser '+ability['name']
        messages.append(f"{mob['name']} prépare {ability['name']}.")
        return True
    return False
