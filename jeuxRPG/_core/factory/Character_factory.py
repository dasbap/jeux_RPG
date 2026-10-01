from jeuxRPG._class import Character
from jeuxRPG._function.Character.level_up_f import level_up_f
from ..object_creation import ObjectCreation

class Character_factory(ObjectCreation):
    def __init__(self):
        super().__init__()
    
    def set_object_target(self, new_object_target):
        success = super().set_object_target(new_object_target)
        if success:self.set_attribute_required(class_name = new_object_target.__name__)
        return success
    
    def set_attribute_required(self, **arg: str):
        if not set(arg.keys()).issubset({"id", "name","class_name"}):
            raise ValueError("Keys must be exactly 'id' 'name' or 'class_name'")
        if not all(isinstance(v, str) for v in arg.values()):
            raise TypeError("All values must be strings")
        self.attribute_required = arg

    
    def reset_attribute_required(self):
        return super().reset_attribute_required()

    def create_object(self, to_level : dict[str,int] = {'to_level':0}):
        target = Character.create(self.attribute_required['class_name'],self.attribute_required['id'],self.attribute_required['name'])
        to_level = {'to_level':0} if to_level == {} else to_level
        level_up_f(target, to_level['to_level'])
        self.last_instance_create = target
        self._update_groupe(target)
        return target
