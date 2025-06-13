from typing import Literal
from _class.res.character.alteration.alteration import AlterationType


class SkillEffect:
    def __init__(self,value : int = None, name : str = '', duration : int = 0, stat_target : int = 0, invocation : dict[Literal["class","level","id"],str] = None,alterationtype : AlterationType = None):
        self.value = value
        self.duration = duration
        self.stat_target = stat_target
        self.invocation = invocation
        self.alterationtype = alterationtype
        self.name = name 
        if not alterationtype and not invocation : 
            if not value:
                raise ValueError("une erreur dans la creation d'un skill effect")
        if not value and not duration and not stat_target and not invocation:
            raise ValueError("Le skill effect ne peux pas fonctionner")
        
        if alterationtype:
            if not name : raise ValueError("un SkillEffect de type alteration dois avoir un nom")
            if self.invocation : raise ValueError("un SkillEffect de type alteration ne peux pas avoir d'invocation")
            if not self.stat_target and self.alterationtype not in [AlterationType.STUN, AlterationType.INVINCIBILYTY,AlterationType.DOT]: raise ValueError("un SkillEffect de type alteration doit avoir une stat target")
            if not value :
                if self.alterationtype in [AlterationType.BUFFSTAT, AlterationType.DEBUFFSTAT,AlterationType.DOT, AlterationType.RESISTENCE]:
                    raise ValueError("un SkillEffect de type alteration dois avoir une valeur")
        
        if invocation:
            if not value:
                self.value = 1
                if not duration:
                    self.duration = 4
                if stat_target:raise ValueError("un SkillEffect de type invocation ne peux pas avoir de stat target")
