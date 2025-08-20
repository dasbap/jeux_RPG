from typing import Literal
from district import District


class Town:
    def __init__(self, name, population=0, wealth=0, reputation=0):
        self.name = name
        self.population = population
        self.wealth = wealth
        self.reputation = reputation
        self.districts : dict[str,dict[str,dict|list]]= {}

    def add_district(self, new_district : District):
        if new_district.name not in self.districts:
            self.districts[new_district.name] = new_district 
    
    def create_new_district(self,district_name,guards=[],notable : dict[Literal["notable","role"],object|str]={"notable":None,"Role":None}):
        district = District(district_name)
        for guard in guards:
            district.add_guard(guard)
        if notable["notable"] is not None:
            district.add_notable(notable["notable"].name,notable["role"])
        district.add_building()
        self.add_district(district)

    def add_building(self, district_name, building_name, building_type, level=1):
        if district_name in self.districts:
            self.districts[district_name]["buildings"][building_name] = {
                "type": building_type,
                "level": level,
                "status": "operational"
            }

    def upgrade_building(self, district_name, building_name):
        if district_name in self.districts:
            if building_name in self.districts[district_name]["buildings"]:
                self.districts[district_name]["buildings"][building_name]["level"] += 1

    def add_guard(self, district_name, number=1):
        if district_name in self.districts:
            self.districts[district_name]["guards"].append()

    def add_notable(self, district_name, notable_name, role):
        if district_name in self.districts:
            self.districts[district_name]["notables"].append({
                "name": notable_name,
                "role": role
            })

    def add_resource(self, district_name, resource_name, quantity):
        if district_name in self.districts:
            if resource_name not in self.districts[district_name]["resources"]:
                self.districts[district_name]["resources"][resource_name] = 0
            self.districts[district_name]["resources"][resource_name] += quantity

    def spend_resource(self, district_name, resource_name, quantity):
        if district_name in self.districts:
            if resource_name in self.districts[district_name]["resources"]:
                if self.districts[district_name]["resources"][resource_name] >= quantity:
                    self.districts[district_name]["resources"][resource_name] -= quantity
                    return True
        return False

    def get_info(self):
        return {
            "name": self.name,
            "population": self.population,
            "wealth": self.wealth,
            "reputation": self.reputation,
            "districts": self.districts
        }
