from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationInfo, model_validator

from .catalog import Catalog, Positive, Quantity, default_catalog


class Family(str, Enum):
    GOBLIN = "Goblin"
    ORC = "Orc"
    DRAGON = "DragonWhelp"
    PHYSICAL = "PhysicalResistantMob"
    MAGIC = "MagicResistantMob"
    SACRED = "SacredResistantMob"


class Slot(str, Enum):
    HELMET = "helmet"
    CHEST = "chest"
    BOOTS = "boots"


def value(identifier):
    return identifier.value if isinstance(identifier, Enum) else identifier


def parse_recipe(recipe_id: str, catalog: Catalog | None = None):
    catalog = catalog or default_catalog()
    try:
        key, tier = catalog.recipe(recipe_id)
        return Gear.from_definition(key, tier, catalog)
    except (ValueError, AttributeError) as error:
        raise ValueError("Recette inconnue. Utilisez la commande recettes.") from error


def material_id(family, tier: int, kind: str) -> str:
    return f"{value(family)}:{tier}:{kind}"


def material_name(identifier: str, catalog: Catalog | None = None) -> str:
    catalog = catalog or default_catalog()
    key, tier = catalog.material(identifier)
    return f"{catalog.materials[key].name} (rang {tier})"


class Gear(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    family: str
    tier: Positive
    slot: str
    _catalog: Catalog = PrivateAttr(default_factory=default_catalog)

    @model_validator(mode="after")
    def validate_definition(self, info: ValidationInfo):
        self._catalog = (info.context or {}).get("catalog", self._catalog)
        if self.definition_id not in self._catalog.equipment:
            raise ValueError("Équipement absent du catalogue")
        return self

    @classmethod
    def from_definition(cls, identifier, tier, catalog):
        definition = catalog.equipment[identifier]
        return cls.model_validate({"family": definition.family, "slot": definition.slot, "tier": tier}, context={"catalog": catalog})

    @property
    def definition_id(self):
        return f"{self.family}:{self.slot}"

    @property
    def recipe_id(self):
        return f"{self.family}:{self.tier}:{self.slot}"

    @property
    def name(self):
        return f"{self._catalog.equipment[self.definition_id].name} (rang {self.tier})"

    @property
    def bonuses(self):
        return {stat: amount * self.tier for stat, amount in self._catalog.equipment[self.definition_id].bonuses.items()}

    @property
    def ingredients(self):
        recipe = self._catalog.recipes[self.definition_id]
        return {self._catalog.ranked_material(key, self.tier): amount for key, amount in recipe.ingredients.items()}


class Inventory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    materials: dict[str, Quantity] = Field(default_factory=dict)
    items: dict[str, Gear] = Field(default_factory=dict)
    equipped: dict[str, str] = Field(default_factory=dict)
    next_id: Positive = 1
    _catalog: Catalog = PrivateAttr(default_factory=default_catalog)

    @classmethod
    def for_catalog(cls, catalog):
        return cls.model_validate({}, context={"catalog": catalog})

    @model_validator(mode="after")
    def validate_inventory(self, info: ValidationInfo):
        self._catalog = (info.context or {}).get("catalog", self._catalog)
        for identifier in self.materials:
            self._catalog.material(identifier)
        for identifier, gear in self.items.items():
            if not identifier.startswith("item-") or not identifier[5:].isdecimal() or int(identifier[5:]) >= self.next_id:
                raise ValueError("Identifiant d'objet invalide")
            if gear.definition_id not in self._catalog.equipment:
                raise ValueError("Équipement absent du catalogue")
            gear._catalog = self._catalog
        for slot, identifier in self.equipped.items():
            if identifier not in self.items or self.items[identifier].slot != slot:
                raise ValueError("Équipement incompatible ou absent")
        return self

    def add_materials(self, materials):
        for identifier, amount in materials.items():
            self._catalog.material(identifier)
            if type(amount) is not int or amount < 0:
                raise ValueError("Quantité de butin invalide")
        for identifier, amount in materials.items():
            self.materials[identifier] = self.materials.get(identifier, 0) + amount

    def add_loot(self, family, tier: int, hide: int, trophy: int):
        self.add_materials({material_id(family, tier, "hide"): hide, material_id(family, tier, "trophy"): trophy})

    def recipes(self):
        discovered = {self._catalog.material(identifier) for identifier in self.materials}
        recipes = set()
        for key, recipe in self._catalog.recipes.items():
            gear = self._catalog.equipment[recipe.equipment]
            for material, tier in discovered:
                if material in recipe.ingredients:
                    recipes.add(f"{gear.family}:{tier}:{gear.slot}")
        return sorted(recipes)

    def craft(self, recipe_id: str):
        gear = parse_recipe(recipe_id, self._catalog)
        if any(self.materials.get(key, 0) < amount for key, amount in gear.ingredients.items()):
            raise ValueError("Matériaux insuffisants")
        identifier = f"item-{self.next_id:06d}"
        for key, amount in gear.ingredients.items():
            self.materials[key] -= amount
        self.items[identifier] = gear
        self.next_id += 1
        return identifier

    def equip(self, identifier: str):
        if identifier not in self.items:
            raise ValueError("Objet absent de l'inventaire")
        self.equipped[self.items[identifier].slot] = identifier

    def unequip(self, slot):
        slot = value(slot)
        if slot not in self._catalog.slots:
            raise ValueError("Emplacement inconnu")
        self.equipped.pop(slot, None)

    def bonuses(self):
        result = {}
        gears = [self.items[identifier] for identifier in self.equipped.values()]
        for gear in gears:
            for stat, amount in gear.bonuses.items():
                result[stat] = result.get(stat, 0) + amount
        by_definition = {gear.definition_id: gear for gear in gears}
        for definition in self._catalog.sets.values():
            if all(identifier in by_definition for identifier in definition.equipment):
                tiers = {by_definition[identifier].tier for identifier in definition.equipment}
                if len(tiers) == 1:
                    for stat, amount in definition.bonuses.items():
                        result[stat] = result.get(stat, 0) + amount * next(iter(tiers))
        return result
