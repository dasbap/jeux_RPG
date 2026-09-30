from functools import lru_cache
import importlib
import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

Positive = Annotated[StrictInt, Field(ge=1)]
Quantity = Annotated[StrictInt, Field(ge=0)]
STAT_NAMES = {"HP", "Force", "Endurance", "Intelligence", "Sagesse"}


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Drop(Definition):
    material: str
    minimum: Quantity
    maximum: Quantity

    @model_validator(mode="after")
    def valid_range(self):
        if self.minimum > self.maximum:
            raise ValueError("Plage de butin invalide")
        return self


class CreatureDefinition(Definition):
    name: str
    character_class: str
    module: str | None = None
    drops: list[Drop]


class MaterialDefinition(Definition):
    name: str


class EquipmentDefinition(Definition):
    name: str
    family: str
    slot: str
    bonuses: dict[str, Quantity]


class RecipeDefinition(Definition):
    equipment: str
    ingredients: dict[str, Positive]


class SetDefinition(Definition):
    name: str
    equipment: list[str]
    bonuses: dict[str, Quantity]


class SkillDefinition(Definition):
    name: str
    damage_type: str
    damage: Positive
    energie_cost: Quantity
    cooldown: Quantity


class Rules(Definition):
    levels_per_tier: Positive
    fallback_skill: str


class Catalog(Definition):
    version: StrictInt
    slots: dict[str, str]
    creatures: dict[str, CreatureDefinition]
    materials: dict[str, MaterialDefinition]
    equipment: dict[str, EquipmentDefinition]
    recipes: dict[str, RecipeDefinition]
    sets: dict[str, SetDefinition]
    skills: dict[str, SkillDefinition]
    rules: Rules
    character_modules: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self):
        from jeuxRPG._class.character import CharacterMeta
        from jeuxRPG._class.res.classType import DamageType

        if self.version != 1 or not self.creatures or not self.slots:
            raise ValueError("Catalogue vide ou version inconnue")
        for module in self.character_modules:
            if not module.startswith("jeuxRPG."):
                raise ValueError("Module de personnage extérieur au projet")
            try:
                importlib.import_module(module)
            except ImportError as error:
                raise ValueError(f"Module de personnage absent : {module}") from error
        for identifier in self.slots:
            if not identifier or ":" in identifier:
                raise ValueError("Identifiant d'emplacement invalide")
        for identifier in self.materials:
            parts = identifier.split(":")
            if len(parts) != 2 or not all(parts):
                raise ValueError("Identifiant de matériau invalide")
        for identifier, definition in self.creatures.items():
            if ":" in identifier or not identifier:
                raise ValueError("Identifiant de créature invalide")
            if definition.module:
                if not definition.module.startswith("jeuxRPG."):
                    raise ValueError("Module de créature extérieur au projet")
                try:
                    importlib.import_module(definition.module)
                except ImportError as error:
                    raise ValueError(f"Module de créature absent : {definition.module}") from error
            if definition.character_class.lower() not in CharacterMeta._classes:
                raise ValueError(f"Classe absente : {definition.character_class}")
            if CharacterMeta._classes[definition.character_class.lower()].is_playable:
                raise ValueError(f"Une créature doit être une classe non jouable : {identifier}")
            if any(drop.material not in self.materials for drop in definition.drops):
                raise ValueError(f"Matériau de butin absent : {identifier}")
        for identifier, definition in self.equipment.items():
            if identifier != f"{definition.family}:{definition.slot}" or definition.family not in self.creatures or definition.slot not in self.slots:
                raise ValueError(f"Équipement incompatible : {identifier}")
            if not set(definition.bonuses) <= STAT_NAMES:
                raise ValueError("Statistique d'équipement inconnue")
        for identifier, definition in self.recipes.items():
            if identifier != definition.equipment or definition.equipment not in self.equipment:
                raise ValueError(f"Équipement de recette absent : {identifier}")
            if not definition.ingredients or not set(definition.ingredients) <= self.materials.keys():
                raise ValueError(f"Ingrédients de recette absents : {identifier}")
        for identifier, definition in self.sets.items():
            if not definition.equipment or len(set(definition.equipment)) != len(definition.equipment) or not set(definition.equipment) <= self.equipment.keys():
                raise ValueError(f"Panoplie invalide : {identifier}")
            slots = [self.equipment[key].slot for key in definition.equipment]
            if len(set(slots)) != len(slots) or not set(definition.bonuses) <= STAT_NAMES:
                raise ValueError(f"Panoplie incompatible : {identifier}")
        if self.rules.fallback_skill not in self.skills:
            raise ValueError("Compétence de base absente")
        for definition in self.skills.values():
            if definition.damage_type not in DamageType.__members__:
                raise ValueError("Type de dégâts inconnu")
        return self

    def recipe(self, identifier):
        family, tier, slot = identifier.split(":")
        if not tier.isdecimal() or int(tier) < 1 or str(int(tier)) != tier:
            raise ValueError("Rang de recette invalide")
        key = f"{family}:{slot}"
        if key not in self.recipes:
            raise ValueError("Recette inconnue")
        return key, int(tier)

    def material(self, identifier):
        family, tier, kind = identifier.split(":")
        key = f"{family}:{kind}"
        if key not in self.materials or not tier.isdecimal() or int(tier) < 1 or str(int(tier)) != tier:
            raise ValueError("Matériau inconnu")
        return key, int(tier)

    def ranked_material(self, identifier, tier):
        family, kind = identifier.split(":")
        return f"{family}:{tier}:{kind}"


def load_catalog(path: str | Path | None = None):
    source = Path(path) if path is not None else Path(__file__).parent.parent / "resources"
    files = sorted(source.glob("*.json")) if source.is_dir() else [source]
    if not files:
        raise ValueError("Aucun fichier de ressources")
    merged = {}
    sections = {"slots", "creatures", "materials", "equipment", "recipes", "sets", "skills"}
    for file in files:
        data = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Catalogue JSON invalide : {file}")
        for key, value in data.items():
            if key in sections:
                if not isinstance(value, dict):
                    raise ValueError(f"Section invalide : {key}")
                target = merged.setdefault(key, {})
                duplicates = target.keys() & value.keys()
                if duplicates:
                    raise ValueError(f"Ressources dupliquées : {sorted(duplicates)}")
                target.update(value)
            elif key == "character_modules":
                if not isinstance(value, list) or not all(isinstance(module, str) for module in value):
                    raise ValueError("Liste de modules de personnages invalide")
                merged.setdefault(key, []).extend(module for module in value if module not in merged.get(key, []))
            elif key in merged and merged[key] != value:
                raise ValueError(f"Configuration contradictoire : {key}")
            else:
                merged[key] = value
    return Catalog.model_validate(merged)


@lru_cache(maxsize=1)
def default_catalog():
    return load_catalog()
