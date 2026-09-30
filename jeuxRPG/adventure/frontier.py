import os
from pathlib import Path
import tempfile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .catalog import Positive, Quantity, PathDefinition
from .coordination import world_lock


class Settlement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    stage: Literal["camp", "village"] = "camp"


class RoutingEpoch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clock: StrictInt
    paths: list[str]


class FrontierState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clock: Quantity = 8
    discovered: list[str] = Field(default_factory=list)
    settlements: dict[str, Settlement] = Field(default_factory=dict)
    roads: dict[str, PathDefinition] = Field(default_factory=dict)
    relays: list[str] = Field(default_factory=list)
    met_npcs: list[str] = Field(default_factory=list)
    hired_npcs: list[str] = Field(default_factory=list)
    next_road: Positive = 1
    routing_history: dict[str, list[RoutingEpoch]] = Field(default_factory=dict)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(value.model_dump_json(indent=2))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


class WorldSimulation:
    def __init__(self, catalog, state=None):
        self.catalog = catalog
        self.state = state or FrontierState(clock=catalog.geography.start_hour if catalog.geography else 8)
        self.validate()

    @classmethod
    def load(cls, path, catalog):
        state = FrontierState.model_validate_json(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else None
        return cls(catalog, state)

    @classmethod
    def tick_file(cls, path, catalog, hours):
        with world_lock(path):
            simulation = cls.load(path, catalog)
            report = simulation.advance(hours)
            simulation.save(path)
            return report

    def save(self, path):
        atomic_json(path, self.state)

    @property
    def paths(self):
        return {**self.catalog.paths, **self.state.roads}

    @property
    def routes(self):
        return {**self.paths, **self.catalog.landmarks}

    def validate(self):
        s = self.state
        for collection, allowed in [(s.discovered, self.catalog.zones), (s.met_npcs, self.catalog.npcs), (s.hired_npcs, self.catalog.npcs), (s.relays, self.paths)]:
            if len(set(collection)) != len(collection) or not set(collection) <= allowed.keys():
                raise ValueError("État du monde incompatible avec les ressources")
        if not set(s.hired_npcs) <= set(s.met_npcs) or any(self.catalog.npcs[key].role != "worker" for key in s.hired_npcs):
            raise ValueError("Main-d'œuvre sauvegardée invalide")
        if self.catalog.paths.keys() & s.roads.keys():
            raise ValueError("Route construite en conflit avec une route existante")
        pairs = set()
        for key, path in self.paths.items():
            if path.source not in self.catalog.zones or path.destination not in self.catalog.zones or path.source == path.destination:
                raise ValueError("Route sauvegardée invalide")
            pair = frozenset([path.source, path.destination])
            if pair in pairs:
                raise ValueError("Route sauvegardée dupliquée")
            pairs.add(pair)
            if key in s.roads and (self.catalog.zones[path.source].world != self.catalog.zones[path.destination].world or not any(zone in s.settlements and s.settlements[zone].stage == "village" for zone in pair)):
                raise ValueError("Raccordement de village sauvegardé invalide")
        for key, settlement in s.settlements.items():
            if key not in self.catalog.sites or key not in s.discovered or (settlement.stage == "village" and not self.catalog.sites[key].strategic) or not settlement.name.strip():
                raise ValueError("Camp ou village sauvegardé invalide")
        for key in s.roads:
            if not key.startswith("built-road-") or not key[11:].isdecimal() or not 0 < int(key[11:]) < s.next_road:
                raise ValueError("Identifiant de route construite invalide")
        for key, epochs in s.routing_history.items():
            if key not in self.catalog.npcs or not epochs or [epoch.clock for epoch in epochs] != sorted(set(epoch.clock for epoch in epochs)):
                raise ValueError("Historique d’itinéraire invalide")
            for epoch in epochs:
                current = self.catalog.npcs[key].start_zone
                if not epoch.paths:
                    raise ValueError("Itinéraire sauvegardé vide")
                for road_id in epoch.paths:
                    if road_id not in self.paths:
                        raise ValueError("Route d’itinéraire sauvegardée absente")
                    path = self.paths[road_id]
                    if path.source == current:
                        current = path.destination
                    elif path.bidirectional and path.destination == current:
                        current = path.source
                    else:
                        raise ValueError("Itinéraire sauvegardé discontinu")
                if current != self.catalog.npcs[key].start_zone:
                    raise ValueError("Itinéraire sauvegardé non fermé")
        if s.next_road <= len(s.roads):
            raise ValueError("Compteur de route invalide")

    def itinerary(self, npc):
        if hasattr(npc, "creature"):
            return npc.itinerary
        route = []
        visited = set()
        def spurs(zone):
            for road_id, road in self.state.roads.items():
                if road_id in visited:
                    continue
                other = road.destination if road.source == zone else road.source if road.destination == zone else None
                if other is None:
                    continue
                visited.add(road_id)
                route.append(road_id)
                spurs(other)
                route.append(road_id)
        current = npc.start_zone
        for key in npc.itinerary:
            spurs(current)
            route.append(key)
            path = self.routes[key]
            current = path.destination if path.source == current else path.source
        return route

    def schedule_roads(self):
        for key, npc in self.catalog.npcs.items():
            origin = (self.catalog.geography.start_hour if self.catalog.geography else 8) - npc.offset_hours
            epochs = self.state.routing_history.get(key, [RoutingEpoch(clock=origin, paths=npc.itinerary)])
            previous = [epoch for epoch in epochs if epoch.clock <= self.state.clock]
            active = previous[-1] if previous else epochs[0]
            period = sum(self.paths[road].hours + npc.stop_hours for road in active.paths)
            remaining = (active.clock - self.state.clock) % period
            boundary = self.state.clock + remaining
            desired = self.itinerary(npc)
            if desired != active.paths:
                previous = [epoch for epoch in previous if epoch.clock < boundary]
                previous.append(RoutingEpoch(clock=boundary, paths=desired))
            self.state.routing_history[key] = previous

    def position(self, npc, clock):
        if hasattr(npc, "active"):
            hour = clock % 24
            rules = self.catalog.geography
            night = hour < rules.day_start or hour >= rules.night_start
            if (npc.active == "day" and night) or (npc.active == "night" and not night):
                return None
        epochs = next((self.state.routing_history[key] for key, value in self.catalog.npcs.items() if value is npc and key in self.state.routing_history), [])
        active_epochs = [epoch for epoch in epochs if epoch.clock <= clock]
        active = active_epochs[-1] if active_epochs else None
        route = active.paths if active else npc.itinerary
        period = sum(self.routes[key].hours + npc.stop_hours for key in route)
        origin = active.clock if active else (self.catalog.geography.start_hour if self.catalog.geography else 8) - npc.offset_hours
        phase = (clock - origin) % period
        current = npc.start_zone
        for key in route:
            path = self.routes[key]
            destination = path.destination if path.source == current else path.source
            if phase < npc.stop_hours:
                return {"zone": current, "path": None, "progress": None}
            phase -= npc.stop_hours
            if phase < path.hours:
                fraction = phase / path.hours
                return {"zone": None, "path": key, "progress": fraction if current == path.source else 1 - fraction}
            phase -= path.hours
            current = destination
        raise ValueError("Itinéraire de simulation invalide")

    def positions(self, clock=None):
        clock = self.state.clock if clock is None else clock
        return {key: {"name": npc.name, "role": npc.role, "position": self.position(npc, clock)} for key, npc in self.catalog.npcs.items() if key not in self.state.hired_npcs}

    def advance(self, hours):
        if type(hours) is not int or hours < 1:
            raise ValueError("Durée de simulation invalide")
        before = self.positions()
        self.state.clock += hours
        return {"clock": self.state.clock, "before": before, "after": self.positions()}

    def crossing(self, key, start, end, before, after, entity):
        path = self.routes[key]
        positions = [self.position(entity, before), self.position(entity, after)]
        coordinates = []
        for position in positions:
            if position is None:
                coordinates.append(None)
            elif position["path"] == key:
                coordinates.append(position["progress"])
            elif position["zone"] == path.source:
                coordinates.append(0)
            elif position["zone"] == path.destination:
                coordinates.append(1)
            else:
                coordinates.append(None)
        first, last = coordinates
        if first is not None and last is not None:
            return (first - start) * (last - end) <= 0
        return (first is not None and abs(first - start) < 1e-9) or (last is not None and abs(last - end) < 1e-9)



class FrontierMixin:
    @property
    def simulation(self):
        return WorldSimulation(self.catalog, self.frontier)

    @property
    def all_paths(self):
        return self.simulation.paths

    def zone_definition(self, zone_id):
        zone = self.catalog.zones[zone_id]
        settlement = self.frontier.settlements.get(zone_id)
        if settlement and settlement.stage == "village":
            return zone.model_copy(update={"name": settlement.name, "kind": "village", "inn": True, "craft": False})
        return zone

    def _sync_world(self):
        if self.world_path is None or not self.world_path.exists():
            return
        latest = WorldSimulation.load(self.world_path, self.catalog).state
        for field in ["discovered", "relays", "met_npcs", "hired_npcs"]:
            setattr(self.frontier, field, list(dict.fromkeys([*getattr(latest, field), *getattr(self.frontier, field)])))
        for field in ["settlements", "roads", "routing_history"]:
            setattr(self.frontier, field, {**getattr(latest, field), **getattr(self.frontier, field)})
        self.frontier.next_road = max(latest.next_road, self.frontier.next_road)
        self.frontier.clock = max(latest.clock, self.frontier.clock)
        if self.location:
            self.location.elapsed_hours = max(self.location.elapsed_hours, self.frontier.clock)

    def _advance_hours(self, hours):
        self._sync_world()
        self.frontier.clock = max(self.frontier.clock, self.location.elapsed_hours)
        self.simulation.advance(hours)
        self.location.elapsed_hours = self.frontier.clock

    def advance_world(self, hours):
        self._sync_world()
        result = self.simulation.advance(hours)
        if self.location:
            self.location.elapsed_hours = self.frontier.clock
        self.save()
        return result

    def observe(self):
        self._sync_world()
        if self.location is None or self.location.route is not None:
            return {"landmarks": {}, "npcs": {}}
        zone = self.location.zone
        landmarks = {}
        for key, landmark in self.catalog.landmarks.items():
            destination = landmark.destination if landmark.source == zone else landmark.source if landmark.bidirectional and landmark.destination == zone else None
            if destination:
                landmarks[key] = {"name": landmark.name, "description": landmark.description,
                                  "direction": landmark.direction if landmark.source == zone else "retour par le même repère",
                                  "hours": landmark.hours,
                                  "destination": destination if destination in self.frontier.discovered else "inconnue"}
        npcs = {key: value for key, value in self.simulation.positions(self.location.elapsed_hours).items() if value["position"] and value["position"]["zone"] == zone}
        return {"landmarks": landmarks, "npcs": npcs, "site": self.catalog.sites[zone].model_dump() if zone in self.catalog.sites else None}

    def explore(self, landmark_id):
        if self.location is None or self.location.route is not None or landmark_id not in self.observe()["landmarks"]:
            raise ValueError("Repère non visible depuis cette position")
        landmark = self.catalog.landmarks[landmark_id]
        destination = landmark.destination if landmark.source == self.location.zone else landmark.source
        self._check_zone_level(destination)
        return self._journey(landmark_id, destination, landmark.hours, offroad=True)

    def hire(self, npc_id):
        visible = self.observe()["npcs"]
        if npc_id not in self.catalog.npcs or (npc_id not in self.frontier.met_npcs and npc_id not in visible) or npc_id in self.frontier.hired_npcs or self.catalog.npcs[npc_id].role != "worker":
            raise ValueError("Travailleurs indisponibles ou déjà recrutés")
        if npc_id not in self.frontier.met_npcs:
            self.frontier.met_npcs.append(npc_id)
        self.frontier.hired_npcs.append(npc_id)
        self.save()
        return self.catalog.npcs[npc_id].workforce

    @property
    def workforce(self):
        return sum(self.catalog.npcs[key].workforce for key in self.frontier.hired_npcs)

    def _construction(self, kind):
        if self.catalog.frontier is None:
            raise ValueError("Constructions absentes du catalogue")
        definition = self.catalog.constructions[getattr(self.catalog.frontier, kind)]
        costs = {self.catalog.ranked_material(key, 1): amount for key, amount in definition.materials.items()}
        if self.workforce < definition.workers:
            raise ValueError("Main-d'œuvre insuffisante")
        if any(self.inventory.materials.get(key, 0) < amount for key, amount in costs.items()):
            raise ValueError("Matériaux insuffisants")
        for key, amount in costs.items():
            self.inventory.materials[key] -= amount
        self._advance_hours(definition.hours)
        return {"materials": costs, "workers": definition.workers, "hours": definition.hours}

    def rest_at_camp(self, until="day"):
        if self.location is None or self.location.route is not None or self.location.zone not in self.frontier.settlements or until not in {"day", "night"}:
            raise ValueError("Camp absent ou heure de repos invalide")
        rules = self.catalog.geography
        target = rules.day_start if until == "day" else rules.night_start
        hours = (target - self.location.elapsed_hours % 24) % 24 or 24
        self._advance_hours(hours)
        self.player.hp.set_max()
        for energy in self.player.energie:
            energy.set_max()
        self.save()
        return {"rested_hours": hours, "hour": target, "night": self.is_night}

    def gather(self):
        if self.location is None or self.location.route is not None or self.location.zone not in self.catalog.sites:
            raise ValueError("Aucune ressource récoltable ici")
        drops = self.catalog.sites[self.location.zone].resources
        if not drops:
            raise ValueError("Aucune ressource récoltable ici")
        materials = {self.catalog.ranked_material(drop.material, 1): drop.minimum for drop in drops}
        self.inventory.add_materials(materials)
        self._advance_hours(self.catalog.frontier.gathering_hours)
        self.save()
        return materials

    def establish_camp(self, name):
        if self.location is None:
            raise ValueError("Aucune position de camp")
        zone = self.location.zone
        if self.location is None or self.location.route is not None or zone not in self.catalog.sites or zone in self.frontier.settlements or not isinstance(name, str) or not name.strip():
            raise ValueError("Emplacement de camp ou nom invalide")
        cost = self._construction("camp")
        self.frontier.settlements[zone] = Settlement(name=name.strip())
        self.save()
        return {"zone": zone, "stage": "camp", "cost": cost}

    def upgrade_village(self):
        if self.location is None:
            raise ValueError("Aucune position de village")
        zone = self.location.zone
        settlement = self.frontier.settlements.get(zone)
        if self.location is None or self.location.route is not None or settlement is None or settlement.stage != "camp" or not self.catalog.sites[zone].strategic:
            raise ValueError("Le camp doit occuper une position stratégique")
        cost = self._construction("village")
        settlement.stage = "village"
        self.save()
        return {"zone": zone, "stage": "village", "cost": cost}

    def connect_village(self, destination):
        if self.location is None:
            raise ValueError("Aucune position de raccordement")
        source = self.location.zone
        settlement = self.frontier.settlements.get(source)
        if self.location is None or self.location.route is not None or not settlement or settlement.stage != "village" or destination == source or destination not in self.catalog.zones:
            raise ValueError("Raccordement de village invalide")
        target = self.zone_definition(destination)
        if destination not in self.frontier.discovered or target.world != self.location.world or target.kind not in {"village", "city", "capital"}:
            raise ValueError("Destination habitée et découverte requise dans ce monde")
        if any({path.source, path.destination} == {source, destination} for path in self.all_paths.values()):
            raise ValueError("Ces zones sont déjà reliées")
        cost = self._construction("road")
        key = f"built-road-{self.frontier.next_road}"
        self.frontier.next_road += 1
        self.frontier.roads[key] = PathDefinition(source=source, destination=destination, hours=self.catalog.frontier.road_hours, day_risk=.1, night_risk=.3)
        self.simulation.schedule_roads()
        self.save()
        return {"path": key, "cost": cost}

    def build_relay(self, path_id):
        if self.location is None or self.location.route is not None or path_id not in self.available_paths() or path_id in self.frontier.relays or self.all_paths[path_id].hours < 2:
            raise ValueError("Chemin de relais inaccessible ou déjà équipé")
        cost = self._construction("relay")
        self.frontier.relays.append(path_id)
        self.save()
        return {"path": path_id, "cost": cost}
