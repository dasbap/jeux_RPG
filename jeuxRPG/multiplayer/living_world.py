"""Deterministic shared world. Scheduled events cost nothing between deadlines.

The same calendar is used online and during catch-up. Detailed positions are
derived from that calendar, never integrated in a separate, divergent simulation.
"""

import hashlib
import heapq
import json
import math
from copy import deepcopy

from .living_world_catalog import fingerprint


def roll(seed, identity, upper):
    return (
        int.from_bytes(
            hashlib.sha256(f"{seed}:{identity}".encode()).digest()[:8], "big"
        )
        % upper
    )


def schedule(state, at, kind, entity, cycle):
    identifier = f"{kind}:{entity}:{cycle}"
    heapq.heappush(state["queue"], [at, identifier, kind, entity, cycle])


def record(state, at, identity, kind, town, message, limit):
    state["events"].append(
        {"id": identity, "at": at, "kind": kind, "town": town, "message": message}
    )
    state["events"] = state["events"][-limit:]


class WorldSimulation:
    def __init__(self, catalog):
        self.catalog = deepcopy(catalog)
        self.identity = fingerprint(catalog)
        self.rules = catalog["rules"]
        if any(type(value) is not int or value <= 0 for value in self.rules.values()):
            raise ValueError("Les échéances du monde doivent être des entiers positifs")
        if not math.isfinite(catalog["speed"]) or not 0 < catalog["speed"] <= 600:
            raise ValueError("Vitesse de simulation invalide")

    def create(self, origin, realm=1):
        if not math.isfinite(origin) or origin < 0:
            raise ValueError("Origine du monde invalide")
        state = {
            "version": 1,
            "catalog": self.identity,
            "realm": realm,
            "seed": f"{self.catalog['seed']}:{realm}",
            "origin": origin,
            "time": origin,
            "processed": 0,
            "queue": [],
            "towns": {},
            "patrols": {},
            "merchant": None,
            "events": [],
        }
        for key in sorted(self.catalog["towns"]):
            state["towns"][key] = {
                "integrity": 100,
                "food": 60,
                "wood": 40,
                "stone": 30,
                "gold": 80,
                "guards": 12,
                "raid": None,
                "losses": 0,
                "goods": dict.fromkeys(self.catalog["goods"], 12),
            }
            schedule(state, origin + self.rules["economy_period"], "economy", key, 0)
            schedule(state, origin + self.rules["raid_period"], "raid_warning", key, 0)
        zones = {}
        for key, definition in self.catalog["maps"].items():
            zones.setdefault(definition["zone"], []).append(key)
        for zone, maps in sorted(zones.items(), key=lambda item: str(item[0])):
            for kind in ("guards", "monsters"):
                choices = [
                    key
                    for key in maps
                    if self.catalog["maps"][key]["town"] == (kind == "guards")
                ]
                if not choices:
                    continue
                key = f"{kind}:{zone}"
                state["patrols"][key] = {
                    "kind": kind,
                    "map": choices[0],
                    "since": origin,
                    "strength": 5 + roll(state["seed"], key, 6),
                }
                schedule(state, origin + self.rules["patrol_period"], "patrol", key, 0)
        if state["towns"]:
            town = sorted(state["towns"])[0]
            state["merchant"] = {
                "id": "caravan",
                "name": "Léon, marchand itinérant",
                "town": town,
                "destination": town,
                "phase": "stationed",
                "since": origin,
                "arrives_at": origin,
                "stock": dict.fromkeys(self.catalog["goods"], 5),
                "gold": 200,
                "visits": 0,
            }
            schedule(
                state,
                origin + self.rules["merchant_stay"],
                "merchant_depart",
                "caravan",
                0,
            )
        return state

    def validate(self, state):
        if state.get("version") != 1 or state.get("catalog") != self.identity:
            raise ValueError("Le monde sauvegardé requiert une migration de catalogue")
        identifiers = [event[1] for event in state["queue"]]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Événement planifié en double")
        if any(
            not math.isfinite(event[0]) or event[0] < state["time"]
            for event in state["queue"]
        ):
            raise ValueError("Calendrier du monde invalide")

    def advance(self, state, target, budget=None):
        self.validate(state)
        if not math.isfinite(target) or target < 0:
            raise ValueError("Échéance du monde invalide")
        budget = self.rules["event_budget"] if budget is None else budget
        if type(budget) is not int or budget <= 0:
            raise ValueError("Budget de rattrapage invalide")
        original = state
        state = self._repair_patrols(state)
        from .guard_patrols import settle_offscreen

        for key, group in state["patrols"].items():
            if group.get("squad"):
                updated_group = deepcopy(group)
                if settle_offscreen(updated_group, target / self.catalog["speed"]):
                    if state is original:
                        state = deepcopy(state)
                    state["patrols"][key] = updated_group
        if not state["queue"] or state["queue"][0][0] > target:
            return state, 0
        updated = deepcopy(state)
        heapq.heapify(updated["queue"])
        processed = 0
        while (
            updated["queue"] and updated["queue"][0][0] <= target and processed < budget
        ):
            at, identity, kind, entity, cycle = heapq.heappop(updated["queue"])
            self._event(updated, at, identity, kind, entity, cycle)
            updated["time"] = at
            updated["processed"] += 1
            processed += 1
        return updated, processed

    def _patrol_allowed(self, kind, map_id):
        definition = self.catalog["maps"].get(map_id)
        return definition is not None and definition["town"] == (kind == "guards")

    def _repair_patrols(self, state):
        invalid = [
            key
            for key, group in state["patrols"].items()
            if not self._patrol_allowed(group["kind"], group["map"])
        ]
        if not invalid:
            return state
        updated = deepcopy(state)
        for key in invalid:
            group = updated["patrols"][key]
            allowed = [
                map_id
                for map_id in sorted(self.catalog["maps"])
                if self._patrol_allowed(group["kind"], map_id)
            ]
            home = [
                map_id
                for map_id in allowed
                if key == f"{group['kind']}:{self.catalog['maps'][map_id]['zone']}"
            ]
            if not allowed:
                raise ValueError(
                    "La patrouille ne dispose plus d'un territoire compatible."
                )
            group.update(map=(home or allowed)[0], since=state["time"])
        return updated

    def _event(self, state, at, identity, kind, entity, cycle):
        if kind == "economy":
            self._economy(state["towns"][entity])
            schedule(state, at + self.rules["economy_period"], kind, entity, cycle + 1)
        elif kind == "patrol":
            patrol = state["patrols"][entity]
            choices = [
                map_id
                for map_id in self.catalog["neighbours"].get(patrol["map"], [])
                if self._patrol_allowed(patrol["kind"], map_id)
            ]
            if choices and not patrol.get("squad"):
                patrol["map"] = choices[roll(state["seed"], identity, len(choices))]
            patrol["since"] = at
            schedule(state, at + self.rules["patrol_period"], kind, entity, cycle + 1)
        elif kind.startswith("raid_"):
            self._raid(state, at, identity, kind, entity, cycle)
        elif kind.startswith("merchant_"):
            self._merchant(state, at, identity, kind, cycle)
        else:
            raise ValueError("Type d'événement inconnu")

    def _economy(self, town):
        for key, quantity in (("food", 6), ("wood", 4), ("stone", 2), ("gold", 3)):
            town[key] = min(500, town[key] + quantity)
        if not town["raid"]:
            if town["integrity"] < 100 and town["wood"] >= 3 and town["stone"] >= 2:
                town["wood"] -= 3
                town["stone"] -= 2
                town["integrity"] = min(100, town["integrity"] + 5)
            if town["guards"] < 12 and town["food"] >= 2 and town["gold"] >= 2:
                town["food"] -= 2
                town["gold"] -= 2
                town["guards"] += 1
            for key in town["goods"]:
                if town["food"] and town["goods"][key] < 50:
                    town["food"] -= 1
                    town["goods"][key] += 1

    def _raid(self, state, at, identity, kind, entity, cycle):
        town = state["towns"][entity]
        name = self.catalog["towns"][entity]["name"]
        if kind == "raid_warning":
            schedule(state, at + self.rules["raid_period"], kind, entity, cycle + 1)
            if town["raid"] or (cycle and roll(state["seed"], identity, 100) >= 60):
                return
            town["raid"] = {
                "id": identity,
                "phase": "warning",
                "strength": 18 + roll(state["seed"], identity, 18),
                "support": 0,
                "starts_at": at + self.rules["raid_warning"],
                "ends_at": at
                + self.rules["raid_warning"]
                + self.rules["raid_duration"],
            }
            schedule(state, town["raid"]["starts_at"], "raid_start", entity, cycle)
            message = f"Des éclaireurs signalent une attaque vers {name}."
        elif kind == "raid_start":
            if not town["raid"]:
                raise ValueError("Attaque sans avertissement")
            town["raid"]["phase"] = "siege"
            schedule(state, town["raid"]["ends_at"], "raid_end", entity, cycle)
            message = f"Les gardes défendent {name}."
        else:
            raid = town["raid"]
            if not raid:
                raise ValueError("Résolution d'attaque déjà appliquée")
            defense = town["guards"] + raid["support"] + town["integrity"] // 20
            difference = raid["strength"] - defense
            if difference > 0:
                damage = min(35, 4 + difference * 2)
                town["integrity"] = max(0, town["integrity"] - damage)
                town["food"] = max(0, town["food"] - difference * 2)
                town["wood"] = max(0, town["wood"] - difference)
                town["guards"] = max(0, town["guards"] - max(1, difference // 3))
                town["losses"] += 1
                message = f"L'attaque de {name} laisse des dégâts ; les habitants préparent la reconstruction."
            else:
                message = f"Les défenseurs de {name} repoussent l'attaque."
            town["raid"] = None
        record(state, at, identity, kind, entity, message, self.rules["history_limit"])

    def _merchant(self, state, at, identity, kind, cycle):
        merchant = state["merchant"]
        if kind == "merchant_depart":
            choices = sorted(self.catalog["journeys"].get(merchant["town"], {}))
            if not choices:
                schedule(
                    state, at + self.rules["merchant_stay"], kind, "caravan", cycle + 1
                )
                return
            target = choices[cycle % len(choices)]
            route = self.catalog["journeys"][merchant["town"]][target]
            merchant.update(
                phase="travelling",
                destination=target,
                since=at,
                arrives_at=at + route["duration"],
            )
            schedule(state, merchant["arrives_at"], "merchant_arrive", "caravan", cycle)
            return
        town_id = merchant["destination"]
        town = state["towns"][town_id]
        if town["raid"]:
            merchant["phase"] = "waiting"
            schedule(
                state, max(at + 1, town["raid"]["ends_at"] + 1), kind, "caravan", cycle
            )
            return
        merchant.update(
            town=town_id, phase="stationed", since=at, visits=merchant["visits"] + 1
        )
        for key, definition in self.catalog["goods"].items():
            quantity = min(4, town["goods"][key], max(0, 30 - merchant["stock"][key]))
            price = max(1, definition["sell"])
            quantity = min(quantity, merchant["gold"] // price)
            merchant["stock"][key] += quantity
            merchant["gold"] -= quantity * price
            town["goods"][key] -= quantity
            town["gold"] = min(500, town["gold"] + quantity * price)
        schedule(
            state,
            at + self.rules["merchant_stay"],
            "merchant_depart",
            "caravan",
            cycle + 1,
        )
        record(
            state,
            at,
            identity,
            kind,
            town_id,
            f"La caravane arrive à {self.catalog['towns'][town_id]['name']}.",
            self.rules["history_limit"],
        )

    def catching_up(self, state, now):
        return bool(state["queue"] and state["queue"][0][0] <= now)

    def view(self, state, now, map_id=None):
        pending = self.catching_up(state, now)
        instant = state["time"] if pending else max(state["time"], now)
        # Detailed scene updates once a real second, without changing simulation state.
        quantum = 3 * self.catalog["speed"]
        instant = max(
            state["origin"], state["time"], math.floor(instant / quantum) * quantum
        )
        towns = []
        for key, data in sorted(state["towns"].items()):
            town = {**self.catalog["towns"][key], **deepcopy(data)}
            town.pop("goods")
            town["status"] = (
                data["raid"]["phase"]
                if data["raid"]
                else "rebuilding"
                if data["integrity"] < 100
                else "peaceful"
            )
            town["price_percent"] = (
                100 + (100 - data["integrity"]) // 2 + max(0, 60 - data["food"])
            )
            if town["raid"]:
                raid = town["raid"]
                raid["progress"] = max(
                    0,
                    min(1, (instant - raid["starts_at"]) / self.rules["raid_duration"]),
                )
            towns.append(town)
        merchant = self._merchant_view(state, towns)
        patrols = [
            {
                "id": key,
                **{
                    name: deepcopy(value)
                    for name, value in group.items()
                    if name != "squad"
                },
                "mode": group.get("squad", {}).get("mode", "patrol"),
                "zone": self.catalog["maps"][group["map"]]["zone"],
            }
            for key, group in sorted(state["patrols"].items())
        ]
        nearby = self._nearby(state, instant, map_id, patrols, merchant)
        return {
            "time": instant,
            "catching_up": pending,
            "towns": towns,
            "merchant": merchant,
            "patrols": patrols,
            "nearby": nearby,
            "events": deepcopy(state["events"][-12:]),
        }

    def _merchant_view(self, state, towns):
        source = state["merchant"]
        if source is None:
            return {
                "name": "Aucune caravane",
                "location": None,
                "travelling": False,
                "stock": [],
            }
        town = next(item for item in towns if item["id"] == source["town"])
        offers = [
            {
                "id": key,
                "name": self.catalog["goods"][key]["name"],
                "quantity": quantity,
                "unit_price": math.ceil(
                    self.catalog["goods"][key]["buy"] * town["price_percent"] / 100
                ),
            }
            for key, quantity in source["stock"].items()
        ]
        return {
            "id": "caravan",
            "name": source["name"],
            "town": source["town"] if source["phase"] == "stationed" else None,
            "location": town["name"] if source["phase"] == "stationed" else None,
            "destination": self.catalog["towns"][source["destination"]]["name"],
            "travelling": source["phase"] != "stationed",
            "phase": source["phase"],
            "stock": offers,
        }

    def _nearby(self, state, now, map_id, patrols, merchant):
        definition = self.catalog["maps"].get(map_id)
        if not definition:
            return []
        path = definition["route"]
        actors = []
        town = state["towns"].get(map_id)
        siege = bool(town and town["raid"] and town["raid"]["phase"] == "siege")
        for group in patrols:
            if group["map"] == map_id:
                from .guard_patrols import public_members

                members = public_members(
                    state["patrols"][group["id"]], definition["display_id"]
                )
                if members:
                    actors.extend(members)
                    continue
                elapsed = (now - group["since"]) / 3
                actors.append(
                    {
                        "id": group["id"],
                        "kind": group["kind"],
                        "name": "Patrouille de gardes"
                        if group["kind"] == "guards"
                        else "Groupe de monstres",
                        "activity": "défend la ville"
                        if siege and group["kind"] == "guards"
                        else "patrouille",
                        "position": route_position(path, elapsed),
                        "map": definition["display_id"],
                    }
                )
        if map_id in state["towns"]:
            raid = state["towns"][map_id]["raid"]
            if raid and raid["phase"] == "siege":
                progress = max(
                    0, min(1, (now - raid["starts_at"]) / self.rules["raid_duration"])
                )
                actors.append(
                    {
                        "id": raid["id"],
                        "kind": "raiders",
                        "name": "Assaillants",
                        "activity": "attaque la ville",
                        "position": route_position(
                            list(reversed(path)), progress * (len(path) - 1), loop=False
                        ),
                        "map": definition["display_id"],
                    }
                )
            for index in range(2):
                identity = f"resident:{map_id}:{index}"
                phase = (
                    (
                        now
                        - state["origin"]
                        + roll(state["seed"], identity, self.rules["npc_cycle"])
                    )
                    % self.rules["npc_cycle"]
                ) / self.rules["npc_cycle"]
                distance = max(1, len(path) - 1)
                if phase < 0.25:
                    position, activity = (
                        route_position(path, phase * 4 * distance, loop=False),
                        "rejoint son travail",
                    )
                elif phase < 0.5:
                    position, activity = path[-1], "travaille"
                elif phase < 0.75:
                    position, activity = (
                        route_position(
                            list(reversed(path)),
                            (phase - 0.5) * 4 * distance,
                            loop=False,
                        ),
                        "rentre chez lui",
                    )
                else:
                    position, activity = path[0], "se repose"
                if siege:
                    position, activity = path[-1], "se met à l'abri"
                actors.append(
                    {
                        "id": identity,
                        "kind": "resident",
                        "name": f"Habitant {index + 1}",
                        "activity": activity,
                        "position": position,
                        "map": definition["display_id"],
                    }
                )
        if merchant.get("town") == map_id:
            actors.append(
                {
                    "id": "caravan",
                    "kind": "merchant",
                    "name": merchant["name"],
                    "activity": "commerce",
                    "position": path[0],
                    "map": definition["display_id"],
                }
            )
        return actors


def route_position(path, distance, loop=True):
    if len(path) < 2:
        return list(path[0])
    length = len(path) - 1
    if loop:
        distance %= length * 2
        if distance > length:
            distance = length * 2 - distance
    distance = max(0, min(length, distance))
    index = min(length - 1, int(distance))
    fraction = distance - index
    return [
        round(
            path[index][axis] + (path[index + 1][axis] - path[index][axis]) * fraction,
            3,
        )
        for axis in (0, 1)
    ]


class LivingWorld:
    """SQLite transaction participant; meta rows also use existing fenced D1 batches."""

    def __init__(self, connection, catalog):
        self.db = connection
        self.simulation = WorldSimulation(catalog)
        self.speed = catalog["speed"]
        self.cache = {}

    def load(self, realm, now):
        key = f"world_life:{realm}"
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if row is None:
            state = self.simulation.create(now * self.speed, realm)
            self.save(realm, state)
            return state
        raw = row[0]
        cached = self.cache.get(realm)
        if cached is None or cached[0] != raw:
            state = json.loads(raw)
            self.simulation.validate(state)
            self.cache[realm] = (raw, state)
        return self.cache[realm][1]

    def save(self, realm, state):
        if not self.db.in_transaction:
            raise RuntimeError("Le monde doit être sauvegardé dans une transaction")
        raw = json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.db.execute(
            "INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (f"world_life:{realm}", raw),
        )

    def advance(self, realm, now):
        state = self.load(realm, now)
        updated, count = self.simulation.advance(state, now * self.speed)
        if updated is not state:
            self.save(realm, updated)
        return updated

    def view(self, realm, now, map_id=None):
        state = self.advance(realm, now)
        return self.simulation.view(state, now * self.speed, map_id)
