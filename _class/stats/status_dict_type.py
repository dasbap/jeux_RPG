from typing import Dict, List, Literal, TypedDict, Union

from _class.res.advantage import Advantage
from _class.res.character.alteration.alteration import Alteration, Buff, DeBuff, Resistance

from _class.res.character.stats.basic_stat import Energie
from _class.res.character.stats.stat import DefaultStat

from _class.res.classType import DamageType as DT

class DamageType(TypedDict):
    Incoming: List
    Reduction: Dict[Union[Literal["%"],Literal["-"],Literal["+"]], List[Resistance]]

class AlterationDictType(TypedDict):
    buff: List[Buff]
    debuff: List[DeBuff]
    invulnerability: List[Alteration]
    Damage: DamageType
    stun: List[Alteration]


class Status_Dict_type(TypedDict):
    stats: Dict[str, Dict[str,Union[DefaultStat, Dict[str, Energie]]], ]
    alteration: AlterationDictType
    advantage: Advantage
    Death_in: int
