from jeuxRPG._core.object_creation import ObjectCreation

class Factory:
    def __init__(self):
        self.factorys = []
        self.last_create = None
    
    def add(self, factory: ObjectCreation):
        if factory.__class__ not in [f.__class__ for f in self.factorys]:
            self.factorys.append(factory)
            factory.group = self
    
    def get(self, type) -> ObjectCreation:
        # Handle both class and instance as input
        import inspect
        if inspect.isclass(type):
            # type is a class, find instance of that class
            return next((f for f in self.factorys if f.__class__.__name__ == type.__name__), None)
        else:
            # type is an instance, find by class
            return next((f for f in self.factorys if f.__class__.__name__ == type.__class__.__name__), None)
    
    def get_by_name(self, type : str) -> ObjectCreation:
        return next((f for f in self.factorys if f.__class__.__name__ == type), None)
    
    def create(self, type : ObjectCreation, **arg) -> object:
        self.last_create = self.get(type).create_object(**arg)
        return self.last_create
    
    def set(self, type, attribute : dict):
        self.get(type).set_attribute_required(attribute)
    
    def update(self, type, attribute : dict):
        self.get(type).update_attribute_required(attribute)
    
