from typing import Literal
from jeuxRPG._class.res.classType import Build_state, Build_state_str, Build_type

class Building:
    def __init__(self, name, b_type : Build_type, level=1, status : Build_state=Build_state.UNDER_CONSTRUCTION):
        self.name = name
        self.type = b_type
        self.level = level
        self.status = status
        self.district = None

    def upgrade(self):
        self.level += 1

    def set_status(self, new_status: Build_state | Build_state_str):
        if isinstance(new_status, str):
            mapping = {
                "UNDER_CONSTRUCTION": Build_state.UNDER_CONSTRUCTION,
                "OPERATIONAL": Build_state.OPERATIONAL,
                "DESTROY": Build_state.DESTROY
            }
            new_status = mapping.get(new_status.upper(), self.status)  
        self.status = new_status

    def get_info(self):
        return {
            "name": self.name,
            "type": self.type,
            "level": self.level,
            "status": self.status
        }