from _class.character import Character
from _class.sub_character.invocations.squelette import Squelette

from _class.res.dictType import ClassSkills
from _class.res.classType import ClassType, SkillType
from _class.res.character.table_stat_subclass import necromancien_table



class Necromancien(Character):
    class_skills_dict: ClassSkills = necromancien_table["class_skills_dict"]
    def __init__(self, user_id: str, name: str):
        super().__init__(
            user_id=user_id,
            name=name,
            class_table=necromancien_table,
            skills=self.class_skills_dict["level 1"].copy()
        )
        self.class_type = ClassType.SUMMONER
    
    def attack(self, target: 'Character', skill_name: str = None) -> tuple[bool, str]:
        
        if skill_name:
            if self.get_skill(skill_name).skill_type is SkillType.INVOCATION:
                return self._invocation(skill_name)
        
        if not self.have_invocation():
            success, message = self._invocation()
            if not success : return False, f"{self.name} can't attack"
            return True, message + " (it's not an attack)"

        invocations = self.invocations.get_all()

        if not isinstance(invocations, list):
            raise TypeError(f"The invocations of {self.name} must be a list")

        message = f"No alive invocation for {self.name} to attack"
        success = False
        for invocation in invocations:
            if not isinstance(invocation, Squelette):
                raise TypeError(f"One of the invocations of {self.name} is not an Invocation")
            if not invocation.is_alive() : continue
            message = ""
            if invocation.is_alive():
                success, mess = invocation.attack(target)
                if success :
                    if isinstance(message, str):
                        message = []
                    message.append(mess)
        if isinstance(message, list):
            message = ", ".join(message)

        return success, message

    def lose_hp(self, source, amount):
        div = int(amount / 2)
        success, message = self.invocations.lose_hp(source,div)
        if not success : div = amount
        return super().lose_hp(source, div)
    
    def _invocation(self, skill_name : str = class_skills_dict["level 1"]["Low Skull"].name) -> tuple[bool,str]:
        skill = self.get_skill(skill_name)
        if skill.can_afford(self) and self.has_required_energie(skill) and self.invocations.can_summon():
            message = skill.execute(self,self)
            if message["success"] == True:
                return True, f"the invocation of {message["invocation"].name} is a success"
            else:
                return False, "the invocation faild"
        return False, "the condition for a invocation was not reach"