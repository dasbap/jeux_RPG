"""
Character class module for RPG game system.

This module defines the base Character class and its metaclass, providing core functionality
for character management, skills, combat, and progression in a role-playing game system.

The Character class uses mixins to separate responsibilities:
- HealthMixin: HP, damage, healing, resurrection
- EnergyMixin: Energy management
- AlterationMixin: Buffs, debuffs, stuns, status effects
- SkillMixin: Skill usage and management
- ProgressionMixin: Experience and leveling
- CombatMixin: Attack and heal actions
"""


from abc import ABC, ABCMeta
from copy import deepcopy
import json
import os
from typing import Dict, List, Optional, Type, Union

from jeuxRPG._class.mixins import (
    HealthMixin,
    EnergyMixin,
    AlterationMixin,
    SkillMixin,
    ProgressionMixin,
    CombatMixin,
    NavigationMixin,
)
from jeuxRPG._class.res.character.alteration import alteration as alteration_file
from jeuxRPG._class.res.character.invocation.invocation_pocket import InvocationPocket
from jeuxRPG._class.res.character.stats.basic_stat import (
    HP, AttributeStat, Endurance, Energie, Force, Intelligence, Sagesse, VitalStat
)
from jeuxRPG._class.res.character.stats.stat import DefaultStat
from jeuxRPG._class.res.classType import ClassType
from jeuxRPG._class.res.dictType import ClassSkills, ClassTable
from jeuxRPG._class.skills.skill import Skill
from jeuxRPG._class.stats.status_dict_type import Status_Dict_type

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


class Character(
    HealthMixin,
    EnergyMixin, 
    AlterationMixin,
    SkillMixin,
    ProgressionMixin,
    CombatMixin,
    NavigationMixin,
    ABC,
    metaclass=CharacterMeta
):
    """
    Base abstract class representing a game character.
    
    This class uses mixins to separate concerns:
    - HealthMixin: HP management, damage, healing
    - EnergyMixin: Energy systems management
    - AlterationMixin: Status effects (buffs, debuffs, stuns)
    - SkillMixin: Skill usage and management
    - ProgressionMixin: Experience and leveling
    - CombatMixin: Combat actions
    
    Attributes:
        is_playable: Whether this class can be selected by players (False for mobs)
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
    
    is_playable: bool = False 
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
            class_table: Class stats table to load
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
                class_skills: ClassSkills = class_table["class_skills_dict"][self.level].copy()
            else:
                class_skills: Dict[str, Skill] = class_table["class_skills_dict"]["level 1"].copy()
        except:
            class_skills = {}
        
        self.skills = deepcopy(skills) if skills else deepcopy(class_skills)
        self.status = deepcopy(status_dict)  # Deep copy to avoid shared state between instances
        
        # Initialize status effects and stats references
        self._init_status_stats()
        
        self.level = 1
        self.exp = 0
        self.team = None
        self.invocations = InvocationPocket(self)
        # Initialize navigation/location fields
        try:
            self._init_navigation()
        except Exception:
            # Be resilient if navigation subsystem is not available
            pass
    
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
        """Return basic character info as string (uses default language)."""
        return self.format()
    
    def format(self, lang: str = "en") -> str:
        """
        Return character info formatted in the specified language.
        
        Args:
            lang: Language code (en, fr, ja). Defaults to English.
            
        Returns:
            Formatted character string in the specified language.
        """
        from jeuxRPG.i18n import t, translate_class_name
        
        # Translate class name
        translated_class = translate_class_name(self.char_class, lang)
        
        # Format HP with language
        hp_str = self.hp.format(lang)
        
        # Format energies list with language
        energie_strs = [e.format(lang) for e in self.energie]
        energie_str = "[" + ", ".join(energie_strs) + "]" if energie_strs else "[]"
        
        return t(
            "character.str",
            lang,
            char_class=translated_class,
            name=self.name,
            level=self.level,
            hp=hp_str,
            energie=energie_str
        )

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
        """Get the character's unique identifier."""
        return self.user_id

    def have_invocation(self) -> bool:
        """Check if character has active summons."""
        return self.invocations.get_all() != []
    
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

    def get_invocation(self) -> List['Character']:
        """Get list of all active summons."""
        return self.invocations.get_all()
