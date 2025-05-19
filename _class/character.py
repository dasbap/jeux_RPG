from typing import Dict, Optional, Tuple, List, Type as TypingType
from abc import ABC, ABCMeta
from .skill import Skill, SkillType
from .stats.basic_stat import HP, Energie, Endurance, Force, Sagesse, Intelligence, Mana

class CharacterMeta(ABCMeta):
    _classes: Dict[str, TypingType['Character']] = {}

    def __new__(cls, name, bases, namespace):
        new_class = super().__new__(cls, name, bases, namespace)
        if name != 'Character':
            cls._classes[name.lower()] = new_class
        return new_class

class Character(ABC, metaclass=CharacterMeta):
    class_skills_dict: Dict[str, Dict[str, Skill]] = {}

    @classmethod
    def create(cls, class_name: str, *args, **kwargs):
        char_class = CharacterMeta._classes.get(class_name.lower())
        if not char_class:
            raise ValueError(f"Classe inconnue: {class_name}")
        return char_class(*args, **kwargs)

    def __init__(
        self,
        user_id: str,
        name: str,
        hp: int = 1,
        force: int = 1,
        endurance: int = 1,
        intelligence: int = 1,
        energie: int = 0,
        sagesse: int = 1,
        skills: Optional[Dict[str, Skill]] = None,
        char_class: Optional[str] = None
    ):
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string")

        self.user_id = user_id
        self.name = name
        self.char_class = char_class or self.__class__.__name__

        self.hp = HP(hp)
        self.force = Force(force)
        self.endurance = Endurance(endurance)
        self.intelligence = Intelligence(intelligence)
        self.sagesse = Sagesse(sagesse)

        self.energie: List[Energie] = []
        self.add_energie(Mana(energie))

        self.skills = skills.copy() if skills else {}
        self.status = {}
        self.level = 1
        self.exp = 0
        self.team : object = None
    
    def __str__(self):
        return f"{self.name} : {self.hp} / {self.energie}"

    def is_alive(self) -> bool:
        return self.hp.value > 0

    def lose_hp(self, source: 'Character', amount: int) -> str:
        if amount <= 0:
            raise ValueError("HP loss must be positive")

        actual_damage = min(amount, self.hp.current_value)
        self.hp._current_value = max(0, self.hp.current_value - amount)

        message = f"{source.name} dealt {actual_damage} damage to {self.name}."
        if not self.is_alive():
            message += f" {self.drop_xp(source)}"

        return message

    def gain_hp(self, amount: int) -> str:
        if amount <= 0:
            raise ValueError("HP gain must be positive")

        max_heal = self.hp.value - self.hp.current_value
        actual_heal = min(amount, max_heal)
        self.hp.heal(actual_heal)

        return f"{self.name} healed for {actual_heal} HP."

    def get_skill(self, skill_name: str) -> Skill:
        if skill := self.skills.get(skill_name):
            return skill
        raise KeyError(f"Skill '{skill_name}' not found for {self.name}")

    def use_skill(self, skill_name: str, target: 'Character') -> Tuple[bool, str]:
        try:
            skill = self.get_skill(skill_name)
            if not self.has_required_energie(skill):
                return False, f"Not enough energie to use {skill_name}"

            skill.execute(self, target)

            return True, f"{self.name} uses {skill.name} on {target.name}"
        except KeyError:
            return False, f"Unknown skill: {skill_name}"
        except Exception as e:
            return False, f"Skill failed: {str(e)}"

    def attack(self, target : 'Character', skill_name : str = None) -> tuple[bool,str]:
        success = False
        message = "error"
        if skill_name:
            success,message = self.use_skill(skill_name, target)
        else:
            for k, skill in  self.get_available_skills().items() :
                if skill.skill_type != SkillType.DAMAGE : continue
                success,message = self.use_skill(skill.name, target)
                if success : break
        return (success, message)
    
    def heal(self, target : 'Character', skill_name : str = None) -> tuple[bool,str]:
        success = False
        message = "error"
        if target.hp.is_full(): return False,f"{target.name} is full hp"
        if skill_name:
            success,message = self.use_skill(skill_name)
        else:
            for k, skill in  self.get_available_skills().items() :
                if skill.skill_type != SkillType.HEAL : continue
                success,message = self.use_skill(skill.name, target)
                if success : break
        return (success, message)
    def has_required_energie(self, skill: Skill) -> bool:
        try:
            return self.get_energie(skill.energie_target).current_value >= skill.energie_cost
        except TypeError:
            return False

    def consume_energie(self, amount: int, energie_type: TypingType[Energie]) -> None:
        energie = self.get_energie(energie_type)
        if energie.current_value - amount < 0 : raise ValueError("not enough energie")
        energie.current_value = max(0, energie.current_value - amount)

    def get_available_skills(self) -> Dict[str, Skill]:
        return self.skills.copy()

    def drop_xp(self, killer: 'Character') -> str:
        xp_given = self.level * 50 + self.exp
        killer.gain_exp(xp_given)
        self.exp = 0
        self.level = max(1, self.level - 5)
        return f"{killer.name} gained {xp_given} XP from defeating {self.name}."

    def gain_exp(self, amount: int) -> str:
        if amount <= 0:
            raise ValueError("XP must be positive")

        self.exp += amount
        messages = [f"{self.name} gained {amount} XP."]

        while self.can_level_up():
            messages.append(self.level_up())

        return " ".join(messages)

    def can_level_up(self) -> bool:
        return self.exp >= self.required_exp_for_next_level()

    def required_exp_for_next_level(self) -> int:
        return self.level * 100

    def level_up(self) -> str:
        if not self.can_level_up():
            return f"{self.name} needs more XP to level up."

        self.exp -= self.required_exp_for_next_level()
        self.level += 1

        self.hp.update_base_value(15)
        self.force.update_base_value(3)
        self.endurance.update_base_value(2)

        for energie in self.energie:
            energie.update_base_value(3)

        new_skills = self.class_skills_dict.get(f"level {self.level}", {})
        self.skills.update(new_skills)

        self.hp._current_value = self.hp.value
        for energie in self.energie:
            energie._current_value = energie.value

        message = f"{self.name} reached level {self.level}!"
        if new_skills:
            message += f" Learned new skills: {', '.join(new_skills.keys())}"

        return message

    def gain_energie(self, amount: int, energie_type: TypingType[Energie]) -> str:
        if amount <= 0:
            raise ValueError("Energie gain must be positive")

        energie = self.get_energie(energie_type)
        max_gain = energie.value - energie.current_value
        actual_gain = min(amount, max_gain)
        energie._current_value += actual_gain

        return f"{self.name} restored {actual_gain} {energie.name.lower()}."

    def add_energie(self, energie : Energie):
        if any(isinstance(e, type(energie)) for e in self.energie):
            raise ValueError(f"{energie.name} is already in the energy's list of {self.name}")
        self.energie.append(energie)

    def change_energie(self, old_energie: TypingType[Energie], new_energie: Energie):
        for i, energie in enumerate(self.energie):
            if isinstance(energie, old_energie):
                self.energie[i].change_type(new_energie)
                return
        raise TypeError(f"{old_energie.__name__} is not in the energy's list of {self.name}")

    def get_energie(self, energie_type: Energie) -> Energie:
        for energie in self.energie:
            if isinstance(energie, energie_type):
                return energie
        raise TypeError(f"{energie_type.__name__} is not in the energy's list of {self.name}")

    def resurrect(self, reviver: 'Character') -> str:
        if self.is_alive():
            return f"{self.name} is already alive."

        self.hp._current_value = self.hp.value // 2
        return f"{self.name} has been resurrected by {reviver.name}."