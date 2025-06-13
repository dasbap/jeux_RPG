"""
Character class module for RPG game system.

This module defines the base Character class and its metaclass, providing core functionality
for character management, skills, combat, and progression in a role-playing game system.
"""


from abc import ABC, ABCMeta
from collections import defaultdict
from copy import deepcopy
import json
import os
from typing import Dict, List, Literal, Optional, Tuple, Type, Union

from _class.res.character.alteration import alteration as alteration_file
from _class.res.character.invocation.invocation_pocket import InvocationPocket
from _class.res.character.stats.basic_stat import HP, AttributeStat, Endurance, Energie, Force, Intelligence, Sagesse, VitalStat
from _class.res.character.stats.stat import DefaultStat
from _class.res.classType import ClassType, SkillType
from _class.res.dictType import ClassSkills, ClassTable
from _class.skills.skill import Skill

from _class.skills.skillEffect import SkillEffect
from _class.stats.status_dict_type import Status_Dict_type

json_path = os.path.join(os.path.dirname(alteration_file.__file__), "alteration.json")

with open(json_path, "r", encoding="utf-8") as f:
    status_dict: Status_Dict_type = json.load(f)


class CharacterMeta(ABCMeta):
    """
    Metaclass for Character system to manage character class registration.
    
    Maintains a registry of all character classes for dynamic creation.
    """
    
    _classes: Dict[str, Type['Character']] = {}

    def __new__(cls, name, bases, namespace):
        """
        Create new character class and register it if not the base Character class.
        
        Args:
            name: Name of the class being created
            bases: Base classes
            namespace: Class namespace dictionary
            
        Returns:
            Newly created class
        """
        new_class = super().__new__(cls, name, bases, namespace)
        if name != 'Character':
            cls._classes[name.lower()] = new_class
        return new_class


class Character(ABC, metaclass=CharacterMeta):
    """
    Base abstract class representing a game character.
    
    Attributes:
        class_skills_dict: Dictionary mapping levels to available skills
        user_id: Unique identifier for the character owner
        name: Character's display name
        char_class: Character's class name
        hp: Health points
        force: Strength attribute
        endurance: Endurance attribute
        intelligence: Intelligence attribute
        sagesse: Wisdom attribute
        energie: List of energy resources
        _class_type: The character's class type (melee, ranged, etc.)
        skills: Dictionary of available skills
        status: Dictionary of status effects
        level: Current character level
        exp: Current experience points
        team: Team affiliation
        invocations: Container for summoned creatures
    """
    
    class_skills_dict: Dict[str, Dict[str, Skill]] = {}

    @classmethod
    def create(cls, class_name: str, *args, **kwargs) -> 'Character':
        """
        Factory method to create character instances by class name.
        
        Args:
            class_name: Name of the character class to instantiate
            *args: Positional arguments for constructor
            **kwargs: Keyword arguments for constructor
            
        Returns:
            New character instance
            
        Raises:
            ValueError: If class_name doesn't exist
        """
        char_class = CharacterMeta._classes.get(class_name.lower())
        if not char_class:
            raise ValueError(f"Unknown class: {class_name}")
        return char_class(*args, **kwargs)
    
    @classmethod
    def recreate(
        cls,
        class_name: str,
        user_id: str,
        name: str,
        class_table: ClassTable,
        skills: Optional[Dict[str, Skill]],
        char_class: Optional[str],
        level: int,
        exp: int
    ) -> 'Character':
        """
        Restore a character from saved data.

        Args:
            class_name: Nom de la classe (ex: "mage", "knight") pour instancier la bonne sous-classe
            user_id: Identifiant unique du joueur
            name: Nom du personnage
            class_table: Table des données de classe (stats, compétences, etc.)
            skills: Dictionnaire des compétences acquises
            char_class: Classe du personnage (optionnel, sinon déduit du nom de classe)
            level: Niveau actuel du personnage
            exp: Expérience actuelle

        Returns:
            Une instance complète de Character
        """
        char_class_obj = CharacterMeta._classes.get(class_name.lower())
        if not char_class_obj:
            raise ValueError(f"Unknown class: {class_name}")

        character = char_class_obj(user_id, name, class_table, skills, char_class)
        character.level = level
        character.exp = exp
        return character
    
    def __init__(
        self,
        user_id: str,
        name: str,
        class_table: ClassTable,
        skills: Optional[Dict[str, Skill]] = None,
        char_class: Optional[str] = None
    ):
        """
        Initialize a new character instance.
        
        Args:
            user_id: Unique identifier for the character owner
            name: Character's display name
            class_table_name: Name of the class stats table to load
            skills: Optional dictionary of initial skills
            char_class: Optional explicit class name override
            
        Raises:
            ValueError: If user_id is empty or invalid
        """
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string")

        self.user_id = user_id
        self.name = name
        self.char_class = char_class or self.__class__.__name__
        
        # Initialize base stats
        base_stats = class_table["base_stats"]
        self.hp = HP(base_stats["hp"])
        self.force = Force(base_stats["force"])
        self.endurance = Endurance(base_stats["endurance"])
        self.intelligence = Intelligence(base_stats["intelligence"])
        self.sagesse = Sagesse(base_stats["sagesse"])
        self.class_table = deepcopy(class_table)
        # Initialize energy systems
        self.energie: List[Energie] = []
        for num in base_stats["energie"].keys():
            energie_info = base_stats["energie"][num]
            self.add_energie(energie_info["type"](energie_info["value"], energie_info["regen_rate"]))
        
        self._class_type: ClassType = class_table["class_type"]
        try:
            if self.class_type == ClassType.INVOCATION:
                    class_skills : ClassSkills = class_table["class_skills_dict"][self.level].copy()
            else:
                class_skills: Dict[str, Skill] = class_table["class_skills_dict"]["level 1"].copy()
        except:
                class_skills = {}
        
        self.skills = deepcopy(skills) if skills else deepcopy(class_skills)
        self.status = status_dict.copy()
        
        # Initialize status effects and stats references
        self._init_status_stats()
        
        self.level = 1
        self.exp = 0
        self.team = None
        self.invocations = InvocationPocket(self)
    
    def _init_status_stats(self) -> None:
        """Initialize the status dictionary with references to character stats."""
        self.status["stats"] = {
            self.hp.name: self.hp,
            self.force.name: self.force,
            self.endurance.name: self.endurance,
            self.intelligence.name: self.intelligence,
            self.sagesse.name: self.sagesse,
            "energie": {
                energie.name: energie for energie in self.energie
            }
        }

    
    def __str__(self) -> str:
        """Return basic character info as string."""
        return f"{self.name} lvl {self.level}: {self.hp} / {self.energie}"

    @property
    def class_type(self) -> ClassType:
        """Get the character's class type."""
        return self._class_type

    @class_type.setter
    def class_type(self, value: ClassType) -> None:
        """
        Set the character's class type.
        
        Args:
            value: New class type to set
            
        Raises:
            ValueError: If value is not a valid ClassType
        """
        if not isinstance(value, ClassType):
            raise ValueError("Invalid class type")
        self._class_type = value

    def get_id(self) -> str:
        return self.user_id
    
    def is_alive(self) -> bool:
        """Check if character is alive (HP > 0)."""
        return self.hp.current_value > 0

    def have_invocation(self) -> bool:
        """Check if character has active summons."""
        return self.invocations.get_all() != []
    
    def _get_reduction(self) -> Dict[str, List[int]]:
        """Get damage reduction stats from status effects."""
        return self.status["alteration"]["Damage"]["Reduction"]
    
    def _compute_damage(self, amount: float) -> float:
        """
        Compute final damage after applying reductions.
        
        Args:
            amount: Base damage amount
            
        Returns:
            Final damage after reductions
        """
        reduction = self._get_reduction()

        malus = sum(reduction["-"])
        resistance = sum(reduction["+"])
        multiplier = 1.0

        for percent in reduction["%"]:
            multiplier *= percent

        final_amount = (amount - resistance + malus) * multiplier
        
        return max(0, final_amount)  

    def lose_hp(self, source: 'Character', amount: int) -> str:
        """
        Reduce character's HP by specified amount.
        
        Args:
            source: Character causing the damage
            amount: Amount of damage to apply
            
        Returns:
            Result message string
            
        Raises:
            ValueError: If amount is not positive
        """
        def clamp_reduction() -> int:
            import math
            endurance = self.get_stat("Endurance").current_value
            L = 0.9
            k = 0.02
            x0 = 150
            
            return int((L / (1 + math.exp(-k * (endurance - x0)))) * 100)
        
        if amount <= 0:
            raise ValueError("HP loss must be positive")
        
        if self.is_invulnerable():
            return f"{self.name} is invulnerable, {source.name} can't hit him"
            
        if self.have_reduction():
            amount = int(self._compute_damage(amount))
        
        # Apply endurance-based damage reduction
        reduction = clamp_reduction()
        
        amount = int(amount * (1 - (reduction/100)))
        
        self.hp.current_value = max(0, self.hp.current_value - amount)

        message = f"{source.name} dealt {amount} damage to {self.name}."
        if not self.is_alive():
            message += f" {self.drop_xp(source)}"
            self.invocations.kill_all()

        return message

    def gain_hp(self, amount: int) -> str:
        """
        Restore character's HP by specified amount.
        
        Args:
            amount: Amount of HP to restore
            
        Returns:
            Result message string
            
        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("HP gain must be positive")

        max_heal = self.hp.max_value - self.hp.current_value
        actual_heal = min(amount, max_heal)
        self.hp.current_value += actual_heal

        return f"{self.name} healed for {actual_heal} HP."

    def get_skill(self, skill_name: str) -> Skill:
        """
        Get skill by name.
        
        Args:
            skill_name: Name of skill to retrieve
            
        Returns:
            Requested Skill object
            
        Raises:
            KeyError: If skill doesn't exist
        """
        if skill := self.skills.get(skill_name):
            return skill
        raise KeyError(f"Skill '{skill_name}' not found for {self.name}")
    
    def get_stat(self, stat_name: str) -> Union[DefaultStat, AttributeStat, VitalStat]:
        """
        Get a stat by its name.
        
        Args:
            stat_name: Name of the stat to retrieve
            
        Returns:
            The requested stat object
            
        Raises:
            TypeError: If stat doesn't exist
        """
        stat_dict: Dict[str, Union[DefaultStat, AttributeStat, VitalStat]] = self.status["stats"]
        
        # Check main stats
        if stat_name in stat_dict:
            return stat_dict[stat_name]
        
        # Check energy stats
        if stat_name in stat_dict["energie"]:
            return stat_dict["energie"][stat_name]
            
        raise TypeError(f"{stat_name} not found in character stats")

    def use_skill(self, skill_name: str, target: Optional['Character'] = None) -> Tuple[bool, str]:
        """
        Attempt to use a skill, with comprehensive checks and execution.
        
        Args:
            skill_name: Name of skill to use
            target: Optional target character (default: None)
            
        Returns:
            Tuple of (success, message) where:
            - success: Boolean indicating if skill was used
            - message: String describing result
            
        The method performs the following checks in order:
        1. Skill existence
        2. Energy requirements
        3. Cooldown status
        4. Target validity (if required)
        5. Skill execution
        """
        try:
            # Get the skill instance
            skill = self.get_skill(skill_name)
            
            # Check energy requirements
            if not self.has_required_energie(skill):
                return False, f"Not enough energy to use {skill_name}"
                
            # Check cooldown status
            if not skill.is_ready():
                remaining = skill.cooldown - skill.current_cooldown
                return False, f"{skill.name} is on cooldown ({remaining} rounds remaining)"
            
            # Validate target if skill requires one
            if skill.requires_target and target is None:
                return False, f"{skill.name} requires a target"
                
            # Check if target is valid (alive and not self for harmful skills)
            if target is not None:
                if not target.is_alive():
                    return False, f"Cannot target defeated {target.name}"
                if skill.skill_type == SkillType.DAMAGE and target is self:
                    return False, "Cannot damage yourself"
                if skill.skill_type == SkillType.HEAL and target is not self and not skill.can_target_others:
                    return False, f"{skill.name} can only target self"

            # Execute the skill
            result = skill.execute(self, target)
            return result["success"], result["message"]
        except KeyError:
            return False, f"Unknown skill: {skill_name}"
        except Exception as e:
            return False, f"Skill failed: {str(e)}"

    def attack(self, target: 'Character', skill_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Perform an attack action against target.
        
        Args:
            target: Character to attack
            skill_name: Optional specific skill to use
            
        Returns:
            Tuple of (success, message)
        """
        success = False
        message = "No valid attack skill available"
        
        if skill_name:
            success, message = self.use_skill(skill_name, target)
        else:
            for skill in reversed(self.get_available_skills().values()):
                if skill.skill_type != SkillType.DAMAGE:
                    continue
                success, message = self.use_skill(skill.name, target)
                if success:
                    break
        
        mess, alt = self._update_status()
        message = f"{message}  {mess}"
        return success, message
    
    def add_alteration(self, origin : 'Character', skill_effect: SkillEffect) -> Tuple[bool, str, alteration_file.Alteration]:
        """
        Add an alteration (buff/debuff/...) to the character.
        
        Args:
            skill_used: Skill that caused the alteration
            skill_effect: Effect to apply
            
        Returns:
            Tuple of (success, message, Alteration)
        """
        if skill_effect.alterationtype == alteration_file.AlterationType.BUFFSTAT:
            return self.buff_stat(origin, skill_effect.name, skill_effect.stat_target, skill_effect.value, skill_effect.duration)
        elif skill_effect.alterationtype == alteration_file.AlterationType.DEBUFFSTAT:
            return self.debuff_stat(origin, skill_effect.name, skill_effect.stat_target, skill_effect.value, skill_effect.duration)
        elif skill_effect.alterationtype == alteration_file.AlterationType.STUN:
            return self.add_stun(origin, skill_effect.name, skill_effect.duration)
        raise NotImplementedError("Unsupported alteration type")
    
    def add_stun(self, origin : 'Character',stun_name : str, duration: int) -> Tuple[bool, str, alteration_file.DeBuff]:
        try:
            stun = alteration_file.Stun(stun_name, origin, duration, self)
            self.status["alteration"]["stun"].append(stun)
            return True,f"{self.name} was stun by {origin.name} for {duration} round", stun
        except Exception as e:
            return False,f"an error in Character.add_stun : {e}",None
    
    def debuff_stat(self, origin : 'Character', debuff_name : str, stat_target: Type[DefaultStat], value: int, duration: int) -> Tuple[bool, str, alteration_file.DeBuff]:
        """
        Apply a debuff to a character stat.
        
        Args:
            buff_name: Name of the buff
            stat_target: Type of stat to buff
            value: Amount to decrease the stat
            duration: Duration in rounds
            
        Returns:
            Tuple of (success, message)
        """
        try:
            stat = self.get_stat(stat_target.__name__)
            debuff = alteration_file.DeBuff(debuff_name, value, duration, self, stat_target)
            stat.add_debuff(debuff)
            self.status["alteration"]["debuff"].append(debuff)
            return True, f"{self.name} was debuffed with {debuff_name}, the stat {stat_target.__name__} gets -{value} for {duration} rounds",debuff
        except Exception as e:
            return False, f"Error in debuff_stat: {e}",None
        
    def buff_stat(self, buff_name: str, stat_target: Type[DefaultStat], value: int, duration: int) -> Tuple[bool, str, alteration_file.Buff]:
        """
        Apply a buff to a character stat.
        
        Args:
            buff_name: Name of the buff
            stat_target: Type of stat to buff
            value: Amount to increase the stat
            duration: Duration in rounds
            
        Returns:
            Tuple of (success, message)
        """
        try:
            stat = self.get_stat(stat_target.__name__)
            buff = alteration_file.Buff(buff_name, value, duration, self, stat_target)
            stat.add_buff(buff)
            self.status["alteration"]["buff"].append(buff)
            return True, f"{self.name} was buffed with {buff_name}, the stat {stat_target.__name__} gets +{value} for {duration} rounds",buff
        except Exception as e:
            return False, f"Error in buff_stat: {e}",None

    def heal(self, target: 'Character', skill_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Perform a heal action on target.
        
        Args:
            target: Character to heal
            skill_name: Optional specific skill to use
            
        Returns:
            Tuple of (success, message)
        """
        if target.hp.current_value == target.hp.max_value:
            return False, f"{target.name} is already at full HP"
            
        success = False
        message = "No valid heal skill available"
        
        if skill_name:
            success, message = self.use_skill(skill_name, target)
        else:
            # Try to use most powerful available heal skill
            for skill in reversed(self.get_available_skills().values()):
                if skill.skill_type != SkillType.HEAL:
                    continue
                success, message = self.use_skill(skill.name, target)
                if success:
                    break
                    
        return success, message

    def has_required_energie(self, skill: Skill) -> bool:
        """
        Check if character has enough energy to use skill.
        
        Args:
            skill: Skill to check
            
        Returns:
            True if enough energy, False otherwise
        """
        try:
            energie = self.get_energie(skill.energie_target)
            return energie.current_value >= skill.energie_cost
        except (TypeError, AttributeError):
            return False

    def consume_energie(self, amount: int, energie_type: Type[Energie]) -> None:
        """
        Consume specified amount of energy.
        
        Args:
            amount: Amount to consume
            energie_type: Type of energy to consume
            
        Raises:
            ValueError: If not enough energy available
        """
        energie = self.get_energie(energie_type)
        if energie.current_value < amount:
            raise ValueError("Not enough energy")
        energie.current_value -= amount

    def get_available_skills(self) -> Dict[str, Skill]:
        """Get dictionary of all available skills."""
        return self.skills.copy()

    def drop_xp(self, killer: 'Character') -> str:
        """
        Handle XP drop when character is defeated.
        
        Args:
            killer: Character who defeated this character
            
        Returns:
            Result message string
        """
        xp_given = self.level * 50 + self.exp
        killer.gain_exp(xp_given)
        self.exp = 0
        self.level = max(1, self.level - 5)
        return f"{killer.name} gained {xp_given} XP from defeating {self.name}."

    def gain_exp(self, amount: int) -> str:
        """
        Gain experience points, potentially leveling up.
        
        Args:
            amount: Amount of XP to gain
            
        Returns:
            Result message string
            
        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("XP must be positive")

        self.exp += amount
        messages = [f"{self.name} gained {amount} XP."]

        if self.can_level_up():
            messages.append(self.level_up())

        return " ".join(messages)

    def _check_death(self) -> bool:
        """Check if character should die from status effects."""
        return self.status.get("Death_in", 0) == 0
    
    def is_stun(self) -> bool:
        """Check if character is stunned."""
        return bool(self.status["alteration"].get("stun", []))
    
    def will_be_hit(self) -> bool:
        """Check if character has incoming damage effects."""
        return bool(self.status["alteration"]["Damage"].get("Incoming", []))
    
    def is_invulnerable(self) -> bool:
        """Check if character is invulnerable."""
        return bool(self.status["alteration"].get("invulnerability", []))
    
    def have_reduction(self) -> bool:
        """Check if character has any damage reduction effects."""
        r = self.status["alteration"]["Damage"].get("Reduction", {"-": [], "+": [], "%": []})
        return any(r["-"]) or any(r["+"]) or any(r["%"])
    
    def check_state(self) -> List[Tuple[str, bool]]:
        """
        Check all character status conditions.
        
        Returns:
            List of tuples (condition_name, is_active)
        """
        return [
            ("death", self._check_death()),
            ("stun", self.is_stun()),
            ("dot", self.will_be_hit()),
            ("invulnerability", self.is_invulnerable()),
            ("reduction", self.have_reduction())
        ]
    
    def can_level_up(self) -> bool:
        """Check if character has enough XP to level up."""
        return self.exp >= self._required_exp_for_next_level()

    def _required_exp_for_next_level(self) -> int:
        """Calculate XP needed for next level."""
        return self.level * 100


    def level_up(self) -> str:
        """
        Récursivement augmente le niveau du personnage si assez d'XP.
        Cumule les bonus dans self.tmp.
        Retourne un message final unique.
        """
        if not hasattr(self, "tmp"):
            self.tmp = {
                "start_level": self.level,
                "stats": defaultdict(int),
                "energies": defaultdict(int),
                "new_energies": []
            }

        if not self.can_level_up():
            if self.level == self.tmp["start_level"]:
                needed_xp = self._required_exp_for_next_level() - self.exp
                return f"❌ {self.name} needs {needed_xp} more XP to level up."

            # Construction du message final unique
            final_msg = [f"🎯 {self.name} advanced from Lv{self.tmp['start_level']} → Lv{self.level}"]

            for stat, value in self.tmp["stats"].items():
                final_msg.append(f"📈 {stat} +{value}")
            for energy, value in self.tmp["energies"].items():
                final_msg.append(f"⚡ {energy} capacity +{value}")
            for energy_type in self.tmp["new_energies"]:
                final_msg.append(f"🌟 NEW ENERGY TYPE: {energy_type}")

            del self.tmp
            return "\n".join(final_msg)

        self.exp -= self._required_exp_for_next_level()
        self.level += 1
        for level_skills_dict in self.class_skills_dict.keys():
            if level_skills_dict =="level " + str(self.level):
                self.skills.update(self.class_skills_dict[level_skills_dict])
        
        upgrades: Dict[int, Dict] = self.class_table["upgrade_stats"]
        for threshold in sorted(upgrades.keys()):
            if self.level < threshold:
                continue
            upgrade_data = upgrades[threshold]

            for stat_type, value in upgrade_data.items():
                if stat_type in (HP, Force, Endurance, Intelligence, Sagesse):
                    stat = self.get_stat(stat_type.__name__)
                    stat.upgrade_base_value(value)
                    self.tmp["stats"][stat_type.__name__] += value

            if "Energie" in upgrade_data:
                for energy_type, value in upgrade_data["Energie"].items():
                    energy = self.get_energie(energy_type)
                    energy.upgrade_base_value(value)
                    self.tmp["energies"][energy_type.__name__] += value

            if "new" in upgrade_data and "Energie" in upgrade_data["new"]:
                for energy_type, base_value in upgrade_data["new"]["Energie"].items():
                    self.add_energie(energy_type(base_value))
                    self.tmp["new_energies"].append(energy_type.__name__)
                upgrade_data.pop("new")

        return self.level_up()

    def rest(self) -> str:
        """Restore energy and reduce skill cooldowns."""
        # Regenerate energy
        for energie in self.energie:
            energie.regenerate()
        
        # Reduce skill cooldowns
        for skill in self.skills.values():
            skill.update_cooldown()
        return ""

    def _update_status(self) -> list[Tuple[str,alteration_file.Alteration]]: #to do
        
        stats_dict: Dict[str, DefaultStat] = self.status["stats"]
        for stat in stats_dict.values():
            if isinstance(stat, DefaultStat):
                stat.end_round()
        
        # Update and remove expired alterations
        alterations_dict = self.status["alteration"]
        alteration_remove : list[Tuple[str,alteration_file.Alteration]]= []
        for alterations_type in ["stun", "invulnerability"]:
            alterations_type : Literal["stun","invulnerability"]
            alterations = alterations_dict[alterations_type]
            for a in alterations:
                a.decrease()
                if a.is_over() :
                    alterations.remove(a)
                    alteration_remove.append((f"{self.name} is not longuer affected by {a.name}",a))

        dot_list = alterations_dict["Damage"]["Incoming"]
        dot_list : List[alteration_file.Dot]
        for dot in dot_list:
            if not isinstance(dot, alteration_file.Dot) : raise TypeError("a dot is not a Dot")
            self.lose_hp(dot.get_caster(), dot.value)
            dot.decrease()
        
        reduction = alterations_dict["Damage"]["Reduction"]
        for type in reduction:
            for res in reduction[type]:
                res.decrease()
                if res.is_over():
                    reduction[type].remove(res)
                    alteration_remove.append((f"{self.name} is not longuer affected by {res.name}",res))
        
        alteration_remove = [("",None)] if alteration_remove == [] else alteration_remove
        
        return alteration_remove
    
    def gain_energie(self, amount: int, energie_type: Type[Energie]) -> str:
        """
        Restore specified amount of energy.
        
        Args:
            amount: Amount to restore
            energie_type: Type of energy to restore
            
        Returns:
            Result message string
            
        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("Energy gain must be positive")

        energie = self.get_energie(energie_type)
        max_gain = energie.max_value - energie.current_value
        actual_gain = min(amount, max_gain)
        energie.current_value += actual_gain

        return f"{self.name} restored {actual_gain} {energie.name.lower()}."

    def add_energie(self, energie: Energie) -> None:
        """
        Add new energy type to character.
        
        Args:
            energie: Energy instance to add
            
        Raises:
            ValueError: If energy type already exists
        """
        if any(isinstance(e, type(energie)) for e in self.energie):
            raise ValueError(f"{energie.name} is already in the energy's list of {self.name}")
        self.energie.append(energie)

    def change_energie(self, old_energie: Type[Energie], new_energie: Energie) -> None:
        """
        Replace one energy type with another.
        
        Args:
            old_energie: Energy type to replace
            new_energie: New energy instance
            
        Raises:
            TypeError: If old energy type doesn't exist
        """
        for i, energie in enumerate(self.energie):
            if isinstance(energie, old_energie):
                self.energie[i] = new_energie
                return
        raise TypeError(f"{old_energie.__name__} is not in the energy's list of {self.name}")

    def get_energie(self, energie_type: Type[Energie]) -> Energie:
        """
        Get energy instance of specified type.
        
        Args:
            energie_type: Type of energy to retrieve
            
        Returns:
            Requested energy instance
            
        Raises:
            TypeError: If energy type doesn't exist
        """
        for energie in self.energie:
            if isinstance(energie, energie_type):
                return energie
        raise TypeError(f"{energie_type.__name__} is not in the energy's list of {self.name}")

    def get_invocation(self) -> List['Character']:
        """Get list of all active summons."""
        return self.invocations.get_all()
        
    def resurrect(self, reviver: 'Character') -> str:
        """
        Resurrect a defeated character.
        
        Args:
            reviver: Character performing the resurrection
            
        Returns:
            Result message string
        """
        if self.is_alive():
            return f"{self.name} is already alive."

        self.hp.current_value = self.hp.max_value // 2
        return f"{self.name} has been resurrected by {reviver.name}."