from functools import lru_cache
import importlib
import json
from pathlib import Path
from typing import Annotated, Literal

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
    parent: str | None = None
    variant: Literal["normal", "subspecies", "boss"] = "normal"
    stat_multiplier: Annotated[float, Field(gt=0, le=100)] = 1
    loot_multiplier: Positive = 1
    zones: list[str] = Field(default_factory=list)


class MaterialDefinition(Definition):
    name: str


class EquipmentDefinition(Definition):
    name: str
    family: str
    slot: str
    bonuses: dict[str, Quantity]
    minimum_level: Positive = 1


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


class WorldDefinition(Definition):
    name: str
    max_level: Positive
    entry_zone: str


class ZoneDefinition(Definition):
    name: str
    world: str
    min_level: Positive
    max_level: Positive
    creatures: list[str]
    kind: Literal["wilderness", "village", "city", "capital", "fortress"] = "wilderness"
    inn: bool = False
    craft: bool = False
    hidden: bool = False
    settlement_level: Positive | None = None


class PathDefinition(Definition):
    source: str
    destination: str
    hours: Positive
    day_risk: Annotated[float, Field(ge=0, le=1)] = .1
    night_risk: Annotated[float, Field(ge=0, le=1)] = .3
    bidirectional: bool = True


class GeographyRules(Definition):
    start_world: str
    start_zone: str
    start_hour: Annotated[StrictInt, Field(ge=0, le=23)] = 8
    day_start: Annotated[StrictInt, Field(ge=0, le=23)] = 6
    night_start: Annotated[StrictInt, Field(ge=0, le=23)] = 18
    combat_hours: Positive = 1


class LandmarkDefinition(Definition):
    name: str
    description: str
    direction: str
    source: str
    destination: str
    hours: Positive
    day_risk: Annotated[float, Field(ge=0, le=1)] = .1
    night_risk: Annotated[float, Field(ge=0, le=1)] = .3
    bidirectional: bool = True


class SiteDefinition(Definition):
    strategic: bool = False
    reason: str
    resources: list[Drop] = Field(default_factory=list)


class ConstructionDefinition(Definition):
    materials: dict[str, Positive]
    workers: Positive
    hours: Positive


class NpcDefinition(Definition):
    name: str
    role: Literal["merchant", "worker", "guard"]
    start_zone: str
    itinerary: list[str]
    stop_hours: Positive = 1
    offset_hours: Quantity = 0
    workforce: Quantity = 0


class PatrolDefinition(NpcDefinition):
    role: Literal["guard"] = "guard"
    creature: str
    level: Positive
    active: Literal["always", "day", "night"] = "always"


class FrontierRules(Definition):
    camp: str
    village: str
    road: str
    relay: str
    gathering_hours: Positive = 1
    road_hours: Positive = 3



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
    worlds: dict[str, WorldDefinition] = Field(default_factory=dict)
    zones: dict[str, ZoneDefinition] = Field(default_factory=dict)
    paths: dict[str, PathDefinition] = Field(default_factory=dict)
    geography: GeographyRules | None = None
    landmarks: dict[str, LandmarkDefinition] = Field(default_factory=dict)
    sites: dict[str, SiteDefinition] = Field(default_factory=dict)
    constructions: dict[str, ConstructionDefinition] = Field(default_factory=dict)
    npcs: dict[str, NpcDefinition] = Field(default_factory=dict)
    frontier: FrontierRules | None = None
    patrols: dict[str, PatrolDefinition] = Field(default_factory=dict)

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
        if any(definition.parent is not None and definition.parent not in self.creatures for definition in self.creatures.values()):
            raise ValueError("Espèce parente absente")
        for identifier, definition in self.creatures.items():
            if definition.variant != "normal" and definition.parent is None:
                raise ValueError("Une variante doit déclarer son espèce parente")
            if not set(definition.zones) <= self.zones.keys():
                raise ValueError("Zone de créature absente")
            seen = {identifier}
            parent = definition.parent
            while parent is not None:
                if parent in seen:
                    raise ValueError("Cycle d'espèces")
                seen.add(parent)
                parent = self.creatures[parent].parent
        self.validate_frontier()
        self.validate_geography()
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

    def validate_geography(self):
        if not self.worlds and not self.zones and not self.paths and self.geography is None:
            return
        if not self.worlds or not self.zones or self.geography is None:
            raise ValueError("Carte incomplète")
        rules = self.geography
        if rules.day_start >= rules.night_start:
            raise ValueError("Cycle jour/nuit invalide")
        if rules.start_world not in self.worlds or rules.start_zone not in self.zones or self.zones[rules.start_zone].world != rules.start_world:
            raise ValueError("Point de départ invalide")
        for key, world in self.worlds.items():
            if world.entry_zone not in self.zones or self.zones[world.entry_zone].world != key:
                raise ValueError("Entrée de monde invalide")
        for zone in self.zones.values():
            if zone.world not in self.worlds or zone.min_level > zone.max_level or zone.max_level > self.worlds[zone.world].max_level:
                raise ValueError("Niveaux de zone invalides")
            if zone.settlement_level is not None and zone.settlement_level > self.worlds[zone.world].max_level:
                raise ValueError("Niveau d’agglomération supérieur au plafond du monde")
            if not zone.creatures or len(set(zone.creatures)) != len(zone.creatures) or not set(zone.creatures) <= self.creatures.keys():
                raise ValueError("Créatures de zone invalides")
            if (zone.craft and zone.kind not in {"village", "city", "capital"}) or (zone.inn and zone.kind not in {"village", "city", "capital"}):
                raise ValueError("Service réservé aux agglomérations")
        connections = set()
        for path in self.paths.values():
            if path.source not in self.zones or path.destination not in self.zones or path.source == path.destination or path.night_risk <= path.day_risk:
                raise ValueError("Chemin invalide ou risque nocturne insuffisant")
            pairs = [(path.source, path.destination)]
            if path.bidirectional:
                pairs.append((path.destination, path.source))
            for pair in pairs:
                if pair in connections:
                    raise ValueError("Chemin dupliqué")
                connections.add(pair)
        reachable = {rules.start_zone}
        while True:
            expanded = reachable | {b for a, b in connections if a in reachable}
            if expanded == reachable:
                break
            reachable = expanded
        road_reachable = set(reachable)
        for landmark in self.landmarks.values():
            connections.add((landmark.source, landmark.destination))
            if landmark.bidirectional:
                connections.add((landmark.destination, landmark.source))
        while True:
            expanded = reachable | {b for a, b in connections if a in reachable}
            if expanded == reachable:
                break
            reachable = expanded
        if any(key not in road_reachable for key, zone in self.zones.items() if not zone.hidden):
            raise ValueError("Zone routière inaccessible depuis le départ")
        if reachable != self.zones.keys():
            raise ValueError("Zone inaccessible depuis le départ")

    def validate_frontier(self):
        if (self.sites or self.constructions) and self.frontier is None:
            raise ValueError("Règles de construction absentes")
        if self.paths.keys() & self.landmarks.keys():
            raise ValueError("Identifiant partagé par une route et un repère")
        for key, landmark in self.landmarks.items():
            if landmark.source not in self.zones or landmark.destination not in self.zones or landmark.source == landmark.destination:
                raise ValueError(f"Repère invalide : {key}")
            if self.zones[landmark.source].world != self.zones[landmark.destination].world or landmark.night_risk <= landmark.day_risk:
                raise ValueError("Exploration hors route incompatible")
        for key, site in self.sites.items():
            if key not in self.zones or self.zones[key].kind != "wilderness" or any(drop.material not in self.materials for drop in site.resources):
                raise ValueError("Site de camp ou de récolte invalide")
        for construction in self.constructions.values():
            if not construction.materials or not set(construction.materials) <= self.materials.keys():
                raise ValueError("Matériaux de construction invalides")
        if self.frontier and not {self.frontier.camp, self.frontier.village, self.frontier.road, self.frontier.relay} <= self.constructions.keys():
            raise ValueError("Construction de frontière absente")
        for npc in [*self.npcs.values(), *self.patrols.values()]:
            if npc.start_zone not in self.zones or not npc.itinerary or (npc.role == "worker") != (npc.workforce > 0):
                raise ValueError("PNJ invalide")
            current = npc.start_zone
            routes = {**self.paths, **self.landmarks} if isinstance(npc, PatrolDefinition) else self.paths
            for key in npc.itinerary:
                if key not in routes:
                    raise ValueError("Itinéraire de PNJ absent")
                path = routes[key]
                if path.source == current:
                    current = path.destination
                elif path.bidirectional and path.destination == current:
                    current = path.source
                else:
                    raise ValueError("Itinéraire de PNJ discontinu")
            if current != npc.start_zone:
                raise ValueError("L'itinéraire du PNJ doit former une boucle")

        for patrol in self.patrols.values():
            if patrol.creature not in self.creatures or patrol.level > self.worlds[self.zones[patrol.start_zone].world].max_level:
                raise ValueError("Patrouille invalide")

    def zone_creatures(self, zone_id):
        result = list(self.zones[zone_id].creatures)
        result.extend(key for key, creature in self.creatures.items() if zone_id in creature.zones and key not in result)
        return result

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
    sections = {"slots", "creatures", "materials", "equipment", "recipes", "sets", "skills", "worlds", "zones", "paths", "landmarks", "sites", "constructions", "npcs", "patrols"}
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
