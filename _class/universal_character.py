from copy import deepcopy

from .character import Character, CharacterMeta
from .res.character.class_models import MODELS, table_from_model
from .res.classType import SkillType


class UniversalCharacter(Character):
    def level_up(self):
        result = super().level_up()
        for key,formula in self.class_table.get('formulas',{}).items():
            stat = getattr(self,key)
            missing = stat.value-stat.current_value
            stat.value = round(formula['base']+formula['growth']*(self.level-1))
            stat.current_value = max(0,stat.value-missing)
        return result

    def attack(self,target,skill_name=None):
        if not self.combat_profile.get('summoner'):
            return super().attack(target,skill_name)
        if skill_name and self.get_skill(skill_name).skill_type is SkillType.INVOCATION:
            return self._invocation(skill_name)
        if not self.have_invocation():
            success,message = self._invocation()
            return (True,message+" (it's not an attack)") if success else (False,f"{self.name} can't attack")
        from .sub_character.invocations.invocation import Invocation
        message = f"No alive invocation for {self.name} to attack"
        success = False
        invocations = self.invocations.get_all()
        if not isinstance(invocations,list):
            raise TypeError(f'The invocations of {self.name} must be a list')
        for invocation in invocations:
            if not isinstance(invocation,Invocation):
                raise TypeError(f'One of the invocations of {self.name} is not an Invocation')
            if not invocation.is_alive():
                continue
            message = ''
            success,mess = invocation.attack(target)
            if success:
                if isinstance(message,str):
                    message = []
                message.append(mess)
        return success, ', '.join(message) if isinstance(message,list) else message

    def lose_hp(self,source,amount):
        if self.combat_profile.get('summoner'):
            div = int(amount/2)
            success,_ = self.invocations.lose_hp(source,div)
            amount = div if success else amount
        return super().lose_hp(source,amount)

    def _invocation(self,skill_name=None):
        skill_name = skill_name or next((name for name,skill in self.skills.items() if skill.skill_type is SkillType.INVOCATION),None)
        if skill_name is None:
            return False,'the condition for a invocation was not reach'
        skill = self.get_skill(skill_name)
        if skill.can_afford(self) and self.has_required_energie(skill) and self.invocations.can_summon():
            result = skill.execute(self,self)
            if result['success']:
                return True,f"the invocation of {result['invocation'].name} is a success"
            return False,'the invocation faild'
        return False,'the condition for a invocation was not reach'


def register_model(model,data=None):
    table = table_from_model(model,data)
    if table['class_type'].name == 'INVOCATION':
        from .sub_character.invocations.invocation import Invocation
        from jeuxRPG.i18n import t
        def initialize(self,master,name=None,level='BL'):
            self.level = level
            Invocation.__init__(self,master,deepcopy(table),name,skills=deepcopy(table['class_skills_dict'][level]))
        actor_type = CharacterMeta(model['id'],(Invocation,),{'__init__':initialize,'class_skills_dict':table['class_skills_dict'],'is_playable':False,'universal_class':True,'can_level_up':lambda self:False,'_required_exp_for_next_level':lambda self:0,'level_up':lambda self:t('invocation.cannot_level_up',name=self.name)})
        return actor_type
    def initialize(self,user_id,name):
        Character.__init__(self,user_id,name,deepcopy(table),char_class=model['id'])
    actor_type = CharacterMeta(model['id'],(UniversalCharacter,),{'__init__':initialize,'class_skills_dict':table['class_skills_dict'],'is_playable':model['playable'],'universal_class':True})
    if 'rank' in model:
        actor_type.rank = model['rank']
    for alias in model.get('previous_ids',[]):
        CharacterMeta._classes[alias.lower()] = actor_type
    return actor_type


def get_class(identifier):
    model = next((model for model in MODELS['classes'] if model['id'] == identifier or identifier in model.get('previous_ids',[])),None)
    return register_model(model) if model else None
