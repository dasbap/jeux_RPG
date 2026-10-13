from typing import Literal, TypedDict

from jeuxRPG._class.res.advantage import Advantage
from jeuxRPG._class.res.character.alteration.alteration import (
    Alteration,
    Buff,
    DeBuff,
    Resistance,
)
from jeuxRPG._class.res.character.stats.basic_stat import Energie
from jeuxRPG._class.res.character.stats.stat import DefaultStat


class DamageType(TypedDict):
    Incoming: list
    Reduction: dict[Literal["%"] | Literal["-"] | Literal["+"], list[Resistance]]


class AlterationDictType(TypedDict):
    buff: list[Buff]
    debuff: list[DeBuff]
    invulnerability: list[Alteration]
    Damage: DamageType
    stun: list[Alteration]


class Status_Dict_type(TypedDict):
    stats: dict[
        str,
        dict[str, DefaultStat | dict[str, Energie]],
    ]
    alteration: AlterationDictType
    advantage: Advantage
    Death_in: int
