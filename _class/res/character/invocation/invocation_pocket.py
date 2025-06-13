from typing import List


class InvocationPocket:
    def __init__(self, master, limit : int = 2):
        self.master = master
        self.limit = limit
        self.invocations : list[object] = []
    
    def get_invocation(self) -> list[object]:
        return self.invocations
    
    def add_invocation(self, invocation : object) -> bool:
        if len(self.invocations) >= self.limit : return False
        self.invocations.append(invocation)
        return True
    
    def del_invocation(self, invocation : object) -> None:
        if not invocation in self.invocations:raise ValueError(f"{invocation} not in the pocket of {self.master.name}")
        self.invocations.remove(invocation)
    
    def change_limit(self, new_limit : int) -> None:
        if len(self.invocations) < new_limit or self.limit == new_limit: raise ValueError(f"the new limit of the {self.master.name}'s pocket is not conform")
        self.limit = new_limit
    
    def lose_hp(self, source : object, amount : int) -> tuple[bool, str]:
        valide_invoc = [invoc for invoc in self.get_all() if invoc.is_alive()]
        if valide_invoc == [] : return False, ""
        div = int(amount / len(valide_invoc))
        for invoc in valide_invoc:
            invoc.lose_hp(source, div)
        invoc_killed = [invoc for invoc in valide_invoc if not invoc.is_alive()]
        message = ""
        if invoc_killed is not []:
            message = str(len(invoc_killed)) + ", some was killed in the attack "
            message += ", ".join(invoc.name for invoc in invoc_killed)
            message += " was defeated"
        return True, f"{amount} dgt was take by {len(valide_invoc)} invoc" + message
    
    def kill_all(self):
        self.invocations.clear()
    
    def get_all(self) -> List[object]:
        return self.invocations
    
    def get_limit(self) -> int:
        return self.limit
    
    def can_summon(self) -> bool:
        return len(self.invocations) < self.limit 
    
    def __str__(self):
        noms_invocations = ", ".join(invoc.name for invoc in self.invocations)
        return f"Invocation pocket of {self.master.name} : has {noms_invocations}"
