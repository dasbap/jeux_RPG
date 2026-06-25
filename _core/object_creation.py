from typing import Any

class ObjectCreation:
    def __init__(self):
        self.attribute_required: dict[str, Any] = {}
        self.object_target: type | None = None
        self.last_instance_create: Any | None = None
        self.group = None
    
    def __str__(self):
        return self.__class__.__name__ + self.object_target.__str__()
    
    def __repr__(self):
        return self.__str__()

    def set_object_target(self, new_object_target: type) -> bool:
        self.object_target = new_object_target
        return True

    def del_object_target(self) -> None:
        self.object_target = None

    def set_attribute_required(self, attribute_required: dict[str, Any]) -> bool:
        try:
            if not all(isinstance(k, str) for k in attribute_required):
                raise ValueError("Keys must be strings")
            self.attribute_required = attribute_required
            return True
        except Exception:
            return False

    def update_attribute_required(self, **attribute_required : str) -> bool:
        try:
            if not all(isinstance(k, str) for k in attribute_required):
                raise ValueError("Keys must be strings")
            self.attribute_required.update(attribute_required)
            return True
        except Exception:
            return False

    def reset_attribute_required(self) -> None:
        self.attribute_required = {}
        
    
    def _update_groupe(self,creation):
        if hasattr(self.group,"last_create"):
                self.group.last_create = creation
    def create_object(self, attribute_spe: dict[str, Any] | None = None) -> object:
        if self.object_target is None:
            return None
        attribute_spe = attribute_spe or {}
        final_attrs = {**self.attribute_required, **attribute_spe}
        try:
            instance = self.object_target(**final_attrs)
            self.last_instance_create = instance
            self._update_groupe(instance)
            return instance
        except Exception:
            return None
