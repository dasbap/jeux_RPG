from .skill import Skill
from .stats.basic_stat import HP, Energie, Endurance, Force, Sagesse, Intelligence

class Character:
    class_skills_dict : dict[str,Skill]= {}
    
    def __init__(self, user_id: str, name: str, hp: int = 1, force: int = 1, endurance: int = 1, inteligence : int = 1, energie: int = 0, sagesse : int = 1, skills: dict = None):
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("Invalid user_id")
        if not name or hp <= 0 or force <= 0 or endurance <= 0 or energie < 0:
            raise ValueError("Invalid character creation parameters")

        self.user_id = user_id
        self.name = name
        self.char_class = self.__class__.__name__
        self.hp = HP(hp)
        self.force = Force(force)
        self.endurance = Endurance(endurance)
        self.inteligence = Intelligence(inteligence)
        self.energie : Energie = Energie("energie",energie)
        self.sagesse = Sagesse(sagesse)
        self.skills = skills or {}
        self.status = {}
        self.level = 1
        self.exp = 0

    def drop_xp(self, target: 'Character') -> str:
        xp_given = self.level * 50 + self.exp
        target.gain_exp(xp_given)
        self.exp = 0
        self.level = max(1, self.level - 5)
        return f"{target.name} gained {xp_given} XP from {self.name}."

    def is_alive(self) -> bool:
        return self.hp > 0

    def lose_hp(self, who : 'Character', value: int) -> str:
        if value <= 0:
            raise ValueError("HP loss must be positive")
        self.hp = max(0, self.hp - value)
        if self.hp <= 0: self.drop_xp(who)
        return f"{who.name} dealt {value} damage to {self.name}."

    def gain_hp(self, value: int) -> None:
        if value <= 0:
            raise ValueError("HP gain must be positive")
        self.hp += value

    def get_skill(self, name_skill: str) -> Skill:
        if skill := self.skills.get(name_skill):
            return skill
        raise KeyError(f"Skill '{name_skill}' not found for {self.name}")
    
    
    def use_skill(self, name_skill: str, target : 'Character') -> tuple[bool, str]:
        if name_skill in self.get_skill_dict():
            try:
                skill = self.get_skill(name_skill)
                skill.action(self, target)
                
                return True,f"{self.name} uses {skill.name} on {target.name}"
            except KeyError:
                return False, f"Error in Skill '{name_skill}'. dev more for a valide skill."
        return False, f"Skill '{name_skill}' not found. Use a valide skill : {self.get_skill_dict()}."

    def get_skill_dict(self) -> dict:
        return self.skills.copy()

    def level_up_available(self) -> bool:
        return self.exp >= self.exp_for_level_up()

    def exp_for_level_up(self) -> int:
        return self.level * 100

    def gain_exp(self, exp: int) -> None:
        if exp <= 0:
            raise ValueError("XP must be positive")
        self.exp += exp
        while self.level_up_available():
            self.level_up()

    def level_up(self) -> None:
        if not self.level_up_available():
            return  
        
        self.exp -= self.exp_for_level_up()
        self.level += 1
        self.hp.update_value(15)
        self.force.update_value(3)
        self.endurance.update_value(2)
        self.energie.update_value(3)
        
        if skills_to_add := self.class_skills_dict.get(f"level {self.level}"):
            self.skills.update(skills_to_add)
    
    def gain_energie(self, amount : int) -> None:
        if amount < 0:
            raise ValueError("energie gain must be positive")
        self.energie = self.energie + amount
    
    def resurrected_by(self, who):
        self.hp
        return f"{self.name} has been resurrected by {who}."

    def __str__(self):
        return f"{self.name} ({self.char_class}) Lvl {self.level} | {self.hp}, {self.force}, {self.endurance}, {self.energie} | Skills: {', '.join(self.skills)}"

    def __repr__(self):
        return f"<Character {self.name} {self.char_class}>"