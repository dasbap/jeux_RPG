import json
import os
from .factory.Character_factory import Character_factory
from .factory.factory import Factory
from .object_creation import ObjectCreation


class GameController:
    allinstance = []

    def __init__(self):
        self.id = len(GameController.allinstance) + 1
        self.factory = Factory()
        self.save_path = ""
        self.memory : dict[str, object | list] = {"creation": [], "last creation": None}

        self.__init_factory()
        GameController.allinstance.append(self)

    def __init_factory(self):
        self.add_factory(Character_factory())

    def set_save_path(self, path: str) -> bool:
        self.save_path = path
        return True

    def create_save(self, id, **data) -> bool:
        if not self.save_path:
            return False
        filename = os.path.join(self.save_path, f"id_{id}.json")
        save = {"id": id, "data": data}
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(save, f, indent=4)
            self.memory["creation"].append(save)
            self.memory["last creation"] = save
            return True
        except Exception as e:
            print(f"Erreur sauvegarde : {e}")
            return False

    def load_save(self, id) -> dict | None:
        if not self.save_path:
            return None
        filename = os.path.join(self.save_path, f"id_{id}.json")
        if not os.path.isfile(filename):
            return None
        try:
            with open(filename, "r", encoding="utf-8") as f:
                save = json.load(f)
            return save
        except Exception as e:
            print(f"Erreur lecture sauvegarde : {e}")
            return None
    
    def del_save(self, id) -> bool:
        if not self.save_path:
            return False
        filename = os.path.join(self.save_path, f"id_{id}.json")
        if os.path.isfile(filename):
            try:
                os.remove(filename)
                self.memory["creation"] = [s for s in self.memory["creation"] if s["id"] != id]
                if self.memory["last creation"] and self.memory["last creation"]["id"] == id:
                    self.memory["last creation"] = None
                return True
            except Exception as e:
                print(f"Erreur suppression sauvegarde : {e}")
                return False
        else:
            return False
    
    def add_factory(self, factory : ObjectCreation):
        self.factory.add(factory)
    
    def get_factory(self, type : ObjectCreation):
        self.factory.get(type)
    
    def clear_memory(self):
        self.memory = {"creation":[],"last creation":None}
    
    def set_factory_target(self,type : ObjectCreation, new_target : object):
        self.factory.get(type).set_object_target(new_target)
    
    def update_factory_target(self,type : ObjectCreation, new_target : object):
        self.factory.get(type).update_object_target(new_target)
    
    def update_factory_attribute(self, type : ObjectCreation, attribute : dict):
        self.factory.get(type).update_attribute_required(**attribute)
    
    def set_factory_attribute(self, type : ObjectCreation, attribute : dict):
        self.factory.get(type).set_attribute_required(**attribute)
    
    def factory_create(self, type : ObjectCreation | str, **arg) -> object:
        if isinstance(type,str):
            type = self.factory.get_by_name(type)
        if type is None:raise ValueError("a unknow str for a reach factory")
        last_create = self.factory.get(type).create_object(arg)
        self.memory["last creation"] = last_create
        self.memory["creation"].append(last_create)
        return self.factory.get(type).create_object(arg)

gameController = GameController()