from jeuxRPG._class.place.building import Building


class District:
    def __init__(self, name):
        self.name = name
        self.buildings : dict[str,Building]= {}
        self.guards = []
        self.notables = []
        self.resources : dict[object,list]= {}
        self.town = None

    def add_building(self, building_name, building_type, level=1):
        self.buildings[building_name] = {
            "type": building_type,
            "level": level,
            "status": "operational"
        }

    def upgrade_building(self, building_name):
        if building_name in self.buildings:
            self.buildings[building_name].upgrade()

    def add_guard(self, guard):
        if not hasattr(guard,"name"):
            raise TypeError("un garde doit avoir un nom")
        self.guards.append(guard)

    def add_notable(self, notable_name, role):
        self.notables.append({
            "name": notable_name,
            "role": role
        })

    def add_resource(self, resource):
        if resource in self.resources:
            res = self.resources[resource.type].pop(resource)
            resource += res
        self.resources[resource.type].append(resource)
        

    def spend_resource(self, resource_name, quantity):
        if resource_name in self.resources and self.resources[resource_name] >= quantity:
            self.resources[resource_name] -= quantity
            return True
        return False

    def get_info(self):
        return {
            "name": self.name,
            "buildings": self.buildings,
            "guards": self.guards,
            "notables": self.notables,
            "resources": self.resources,
            "town": self.town
        }
