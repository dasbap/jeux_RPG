from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class LocationState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    world: str
    zone: str
    elapsed_hours: Annotated[StrictInt, Field(ge=0)] = 8
    route: str | None = None
    route_destination: str | None = None
    route_progress: Annotated[StrictInt, Field(ge=0)] = 0


class WorldMixin:
    @property
    def current_zone(self):
        return self.zone_definition(self.location.zone) if self.location else None

    @property
    def level_cap(self):
        return self.catalog.worlds[self.location.world].max_level if self.location else self.player.level

    @property
    def effective_level(self):
        return min(self.player.level, self.level_cap)

    @property
    def is_night(self):
        hour = self.location.elapsed_hours % 24
        rules = self.catalog.geography
        return hour < rules.day_start or hour >= rules.night_start

    @property
    def can_craft(self):
        return self.location is None or (self.location.route is None and self.current_zone.craft)

    def validate_location(self):
        if self.location is None:
            if self.catalog.geography:
                rules = self.catalog.geography
                self.location = LocationState(world=rules.start_world, zone=rules.start_zone, elapsed_hours=rules.start_hour)
            return
        if self.location.route is not None:
            path = self.all_paths.get(self.location.route)
            if path is None or self.location.route not in self.frontier.relays or self.location.zone not in {path.source, path.destination} or self.location.route_destination not in {path.source, path.destination} or self.location.zone == self.location.route_destination or not 0 < self.location.route_progress < path.hours:
                raise ValueError("Position de relais sauvegardée invalide")
        elif self.location.route_destination is not None or self.location.route_progress != 0:
            raise ValueError("Position de route incohérente")
        if self.location.world not in self.catalog.worlds or self.location.zone not in self.catalog.zones or self.current_zone.world != self.location.world:
            raise ValueError("Position sauvegardée absente ou incompatible")

    def available_paths(self):
        self._sync_world()
        if self.location is None:
            return {}
        result = {}
        for key, path in self.all_paths.items():
            if self.location.route is not None and key != self.location.route:
                continue
            if path.source == self.location.zone:
                destination = path.destination
            elif path.bidirectional and path.destination == self.location.zone:
                destination = path.source
            else:
                continue
            zone = self.zone_definition(destination)
            result[key] = {"destination": destination, "name": zone.name, "world": zone.world,
                           "levels": [zone.min_level, zone.max_level], "hours": path.hours - self.location.route_progress,
                           "relay": key in self.frontier.relays}
        return result

    def world_map(self):
        self._sync_world()
        visible = {key for key, zone in self.catalog.zones.items() if not zone.hidden or key in self.frontier.discovered}
        return {"location": self.location.model_dump() if self.location else None,
                "hour": self.location.elapsed_hours % 24 if self.location else None,
                "night": self.is_night if self.location else None,
                "worlds": {key: value.model_dump() for key, value in self.catalog.worlds.items()},
                "zones": {key: {**self.zone_definition(key).model_dump(), "creatures": self.catalog.zone_creatures(key)} for key in visible},
                "paths": {key: value.model_dump() for key, value in self.all_paths.items() if value.source in visible and value.destination in visible},
                "available_paths": self.available_paths(),
                "settlements": {key: value.model_dump() for key, value in self.frontier.settlements.items()},
                "relays": list(self.frontier.relays), "workforce": self.workforce}

    def _remove_overlevel_equipment(self):
        removed = []
        for slot, key in list(self.inventory.equipped.items()):
            if self.inventory.items[key].required_level > self.level_cap:
                del self.inventory.equipped[slot]
                removed.append(key)
        if removed:
            self.refresh_equipment()
        return removed

    def _check_zone_level(self, destination):
        zone = self.zone_definition(destination)
        if min(self.player.level, self.catalog.worlds[zone.world].max_level) < zone.min_level:
            raise ValueError("Niveau insuffisant pour cette zone")

    def travel(self, path_id, stop_at_relay=False):
        paths = self.available_paths()
        if path_id not in paths:
            raise ValueError("Chemin inaccessible depuis cette zone")
        destination = paths[path_id]["destination"]
        self._check_zone_level(destination)
        return self._journey(path_id, destination, self.all_paths[path_id].hours, stop_at_relay=stop_at_relay)

    def _journey(self, route_id, destination, hours, offroad=False, stop_at_relay=False):
        encounters, npc_encounters = [], []
        seen_npcs, seen_patrols = set(), set()
        route = self.simulation.routes[route_id]
        progress = self.location.route_progress if not offroad else 0
        reverse = route.destination != destination
        for index in range(progress, hours):
            before = self.location.elapsed_hours
            self._advance_hours(1)
            after_move = self.location.elapsed_hours
            start, end = index / hours, (index + 1) / hours
            if reverse:
                start, end = 1 - start, 1 - end
            for key, npc in self.catalog.npcs.items():
                if key in seen_npcs or key in self.frontier.hired_npcs or offroad:
                    continue
                if self.simulation.crossing(route_id, start, end, before, after_move, npc):
                    npc_encounters.append({"id": key, "name": npc.name, "role": npc.role})
                    seen_npcs.add(key)
                    if key not in self.frontier.met_npcs:
                        self.frontier.met_npcs.append(key)
            for key, patrol in self.catalog.patrols.items():
                if key in seen_patrols or not self.simulation.crossing(route_id, start, end, before, after_move, patrol):
                    continue
                seen_patrols.add(key)
                report = self.encounter(family=patrol.creature, enemy_level=patrol.level)
                report["patrol"] = key
                encounters.append(report)
                if report["outcome"] != "victory":
                    self.location.route = self.location.route_destination = None
                    self.location.route_progress = 0
                    self.save()
                    return {"arrived": False, "location": self.location.model_dump(), "encounters": encounters, "npc_encounters": npc_encounters, "removed_equipment": []}
            if stop_at_relay and route_id in self.frontier.relays and progress == 0 and index + 1 == (hours + 1) // 2 and index + 1 < hours:
                self.location.route, self.location.route_destination, self.location.route_progress = route_id, destination, index + 1
                self.save()
                return {"arrived": False, "stopped_at_relay": True, "location": self.location.model_dump(), "encounters": encounters, "npc_encounters": npc_encounters, "removed_equipment": []}
        zone = self.zone_definition(destination)
        self.location.world, self.location.zone = zone.world, destination
        self.location.route = self.location.route_destination = None
        self.location.route_progress = 0
        if destination not in self.frontier.discovered:
            self.frontier.discovered.append(destination)
        removed = self._remove_overlevel_equipment()
        self.save()
        return {"arrived": True, "location": self.location.model_dump(), "zone": destination, "encounters": encounters, "npc_encounters": npc_encounters, "removed_equipment": removed}

    def rest_at_inn(self, until="day"):
        if until not in {"day", "night"}:
            raise ValueError("Choisissez day ou night")
        at_relay = self.location is not None and self.location.route in self.frontier.relays
        if not at_relay and (self.current_zone is None or not self.current_zone.inn or self.location.route is not None):
            raise ValueError("Aucune auberge dans cette zone")
        rules = self.catalog.geography
        target = rules.day_start if until == "day" else rules.night_start
        hours = (target - self.location.elapsed_hours % 24) % 24 or 24
        self._advance_hours(hours)
        self.player.hp.set_max()
        for energy in self.player.energie:
            energy.set_max()
        self.save()
        return {"rested_hours": hours, "hour": target, "night": self.is_night}

    def combat_player(self):
        if self.location is None or self.player.level < self.level_cap:
            return self.player
        from jeuxRPG._class.character import Character

        player = Character.create(self.player.char_class, self.player.user_id, self.player.name)
        for level in range(1, self.effective_level):
            player.gain_exp(level * 100)
        for name, amount in self.inventory.bonuses().items():
            player.get_stat(name).upgrade_base_value(amount)
        return player
