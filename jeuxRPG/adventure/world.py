from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class LocationState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    world: str
    zone: str
    elapsed_hours: Annotated[StrictInt, Field(ge=0)] = 8


class WorldMixin:
    @property
    def current_zone(self):
        return self.catalog.zones[self.location.zone] if self.location else None

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
        return self.current_zone is None or self.current_zone.craft

    def validate_location(self):
        if self.location is None:
            if self.catalog.geography:
                rules = self.catalog.geography
                self.location = LocationState(world=rules.start_world, zone=rules.start_zone, elapsed_hours=rules.start_hour)
            return
        if self.location.world not in self.catalog.worlds or self.location.zone not in self.catalog.zones or self.current_zone.world != self.location.world:
            raise ValueError("Position sauvegardée absente ou incompatible")

    def available_paths(self):
        if self.location is None:
            return {}
        result = {}
        for key, path in self.catalog.paths.items():
            if path.source == self.location.zone:
                destination = path.destination
            elif path.bidirectional and path.destination == self.location.zone:
                destination = path.source
            else:
                continue
            zone = self.catalog.zones[destination]
            result[key] = {"destination": destination, "name": zone.name, "world": zone.world,
                           "levels": [zone.min_level, zone.max_level], "hours": path.hours,
                           "day_risk": path.day_risk, "night_risk": path.night_risk}
        return result

    def world_map(self):
        return {"location": self.location.model_dump() if self.location else None,
                "hour": self.location.elapsed_hours % 24 if self.location else None,
                "night": self.is_night if self.location else None,
                "worlds": {key: value.model_dump() for key, value in self.catalog.worlds.items()},
                "zones": {key: {**value.model_dump(), "creatures": self.catalog.zone_creatures(key)} for key, value in self.catalog.zones.items()},
                "paths": {key: value.model_dump() for key, value in self.catalog.paths.items()},
                "available_paths": self.available_paths()}

    def _remove_overlevel_equipment(self):
        removed = []
        for slot, key in list(self.inventory.equipped.items()):
            if self.inventory.items[key].required_level > self.level_cap:
                del self.inventory.equipped[slot]
                removed.append(key)
        if removed:
            self.refresh_equipment()
        return removed

    def travel(self, path_id):
        paths = self.available_paths()
        if path_id not in paths:
            raise ValueError("Chemin inaccessible depuis cette zone")
        destination = paths[path_id]["destination"]
        zone = self.catalog.zones[destination]
        cap = self.catalog.worlds[zone.world].max_level
        if min(self.player.level, cap) < zone.min_level:
            raise ValueError("Niveau insuffisant pour cette zone")
        path = self.catalog.paths[path_id]
        encounters = []
        for _ in range(path.hours):
            risk = path.night_risk if self.is_night else path.day_risk
            self.location.elapsed_hours += 1
            if self.rng.random() < risk:
                report = self.encounter()
                encounters.append(report)
                if report["outcome"] != "victory":
                    self.save()
                    return {"arrived": False, "location": self.location.model_dump(), "encounters": encounters, "removed_equipment": []}
        self.location.world, self.location.zone = zone.world, destination
        removed = self._remove_overlevel_equipment()
        self.save()
        return {"arrived": True, "location": self.location.model_dump(), "encounters": encounters, "removed_equipment": removed}

    def rest_at_inn(self, until="day"):
        if until not in {"day", "night"}:
            raise ValueError("Choisissez day ou night")
        if self.current_zone is None or not self.current_zone.inn:
            raise ValueError("Aucune auberge dans cette zone")
        rules = self.catalog.geography
        target = rules.day_start if until == "day" else rules.night_start
        hours = (target - self.location.elapsed_hours % 24) % 24 or 24
        self.location.elapsed_hours += hours
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
