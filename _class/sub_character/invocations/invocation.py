from _class.character import Character
from _class.res.dictType import ClassSkills, ClassTable


class Invocation(Character):
    all_invocation : list['Invocation'] = []
    DEFAULT_NAME_FORMAT: str = "{invocation_class} of {master} n°{index}"
    def __init__(self,master : Character, class_table : ClassTable ,name  : str = None, skills : ClassSkills = None, char_class : str = None):
        self.master = master
        name = name or self._generate_default_name()
        Invocation.all_invocation.append(self)
        super().__init__("-1", name,class_table, skills, char_class)
    
    def drop_xp(self, killer):
        Invocation.all_invocation.remove(self)
        self.master.invocations.del_invocation(self)
        return super().drop_xp(killer)
    
    def _generate_default_name(self) -> str:
        nb = sum(1 for invoc in Invocation.all_invocation if isinstance(invoc, self.__class__))+1
        return self.DEFAULT_NAME_FORMAT.format(invocation_class=self.__class__.__name__,master=self.master.name,index=nb)