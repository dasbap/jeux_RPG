from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

Positive = Annotated[StrictInt, Field(ge=1)]
Quantity = Annotated[StrictInt, Field(ge=0)]


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


PROFILES = {
    Family.GOBLIN: ("gobelin", "cuir", "dent", "Force"),
    Family.ORC: ("orc", "peau", "défense", "Endurance"),
    Family.DRAGON: ("dragon", "écaille", "griffe", "Force"),
    Family.PHYSICAL: ("gardien de pierre", "carapace", "noyau", "Endurance"),
    Family.MAGIC: ("créature arcanique", "étoffe", "cristal", "Intelligence"),
    Family.SACRED: ("créature sacrée", "plume", "relique", "Sagesse"),
}
SLOT_NAMES = {Slot.HELMET: "Casque", Slot.CHEST: "Plastron", Slot.BOOTS: "Bottes"}


def parse_recipe(recipe_id: str):
    try:
        family, tier, slot = recipe_id.split(":")
        if not tier.isdecimal() or str(int(tier)) != tier or int(tier) < 1:
            raise ValueError("Rang de recette invalide")
        return Gear(family=Family(family), tier=int(tier), slot=Slot(slot))
    except (ValueError, AttributeError) as error:
        raise ValueError("Recette inconnue. Utilisez la commande recettes.") from error


def material_id(family: Family, tier: int, kind: str) -> str:
    return f"{family.value}:{tier}:{kind}"


def material_name(identifier: str) -> str:
    family, tier, kind = identifier.split(":")
    profile = PROFILES[Family(family)]
    if kind not in {"hide", "trophy"} or not tier.isdecimal() or int(tier) < 1 or str(int(tier)) != tier:
        raise ValueError("Matériau invalide")
    return f"{profile[1 if kind == 'hide' else 2]} de {profile[0]} (rang {tier})"


class Gear(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    family: Family
    tier: Positive
    slot: Slot

    @property
    def recipe_id(self):
        return f"{self.family.value}:{self.tier}:{self.slot.value}"

    @property
    def name(self):
        return f"{SLOT_NAMES[self.slot]} de {PROFILES[self.family][0]} (rang {self.tier})"

    @property
    def bonuses(self):
        weight = 2 if self.slot is Slot.CHEST else 1
        result = {"HP": 5 * self.tier * weight, "Endurance": self.tier}
        stat = PROFILES[self.family][3]
        result[stat] = result.get(stat, 0) + self.tier * weight
        return result

    @property
    def ingredients(self):
        return {material_id(self.family, self.tier, "hide"): 3 if self.slot is Slot.CHEST else 2,
                material_id(self.family, self.tier, "trophy"): 1}


class Inventory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    materials: dict[str, Quantity] = Field(default_factory=dict)
    items: dict[str, Gear] = Field(default_factory=dict)
    equipped: dict[Slot, str] = Field(default_factory=dict)
    next_id: Positive = 1

    @model_validator(mode="after")
    def validate_inventory(self):
        for identifier in self.materials:
            material_name(identifier)
        for identifier in self.items:
            if not identifier.startswith("item-") or not identifier[5:].isdecimal() or int(identifier[5:]) >= self.next_id:
                raise ValueError("Identifiant d'objet invalide")
        for slot, identifier in self.equipped.items():
            if identifier not in self.items or self.items[identifier].slot != slot:
                raise ValueError("Équipement incompatible ou absent")
        return self

    def add_loot(self, family: Family, tier: int, hide: int, trophy: int):
        for kind, amount in (("hide", hide), ("trophy", trophy)):
            if type(amount) is not int or amount < 0:
                raise ValueError("Quantité de butin invalide")
        for kind, amount in (("hide", hide), ("trophy", trophy)):
            key = material_id(family, tier, kind)
            material_name(key)
            self.materials[key] = self.materials.get(key, 0) + amount

    def recipes(self):
        discovered = {":".join(identifier.split(":")[:2]) for identifier in self.materials}
        return sorted(f"{prefix}:{slot.value}" for prefix in discovered for slot in Slot)

    def craft(self, recipe_id: str):
        gear = parse_recipe(recipe_id)
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

    def unequip(self, slot: Slot):
        self.equipped.pop(slot, None)

    def bonuses(self):
        result = {}
        gears = [self.items[identifier] for identifier in self.equipped.values()]
        for gear in gears:
            for stat, value in gear.bonuses.items():
                result[stat] = result.get(stat, 0) + value
        if len(gears) == len(Slot) and len({(gear.family, gear.tier) for gear in gears}) == 1:
            tier = gears[0].tier
            result["HP"] = result.get("HP", 0) + 20 * tier
            result["Endurance"] = result.get("Endurance", 0) + 3 * tier
        return result
