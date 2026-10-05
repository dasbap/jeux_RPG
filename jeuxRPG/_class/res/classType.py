from enum import Enum
from typing import Literal


Build_state_str = Literal["UNDER_CONSTRUCTION","OPERATIONAL","DESTROY"]
class Build_state(Enum):
    UNDER_CONSTRUCTION=0
    OPERATIONAL=1
    DESTROY=2

class Build_type(Enum):
    SHOP = 0               # Boutique générique
    TRADE = 1              # Comptoir / Marché
    TRAINING = 2           # Dojo / Terrain d’entraînement
    GUILD = 3              # Guilde (aventuriers, voleurs, mages…)
    MILICE = 4             # Caserne / garnison
    FORGE = 5              # Forge / Armurerie
    MAGIC_TOWER = 6        # Tour magique
    TEMPLE = 7             # Temple / Cathédrale
    LIBRARY = 8            # Bibliothèque / Archives
    INN = 9                # Taverne / Auberge
    FARM = 10              # Ferme / Moulin
    MARKET = 11            # Grand marché
    ALCHEMY_LAB = 12       # Laboratoire d’alchimie
    HARBOR = 13            # Port / Docks
    WALL = 14              # Fortifications
    HOUSE = 15             # Habitations / Quartier résidentiel
    CASTLE = 16            # Château / Palais
    PRISON = 17            # Prison / Geôle
    TOWN_HALL = 18         # Hôtel de ville / Conseil
    STABLE = 19            # Écuries

class ClassType(Enum):
    DEFAULT = 0
    DAMAGE = 1
    DOT = 2
    HEAL = 3
    BUFF = 4
    SHIELD = 5
    INVOCATION = 6
    SUMMONER = 7

class DamageType(Enum):
    PHYSICAL = 0
    MAGIC = 1
    SACRED = 2

class SkillType(Enum):
    DAMAGE = 0
    HEAL = 1
    BUFF = 2
    DEBUFF = 3
    RESURRECT = 4
    INVOCATION = 5
    CUSTOM = 6

class ReductionType(Enum):
    MULTIPLY = 0
    ADD = 1
    SUBSTRACT = 2