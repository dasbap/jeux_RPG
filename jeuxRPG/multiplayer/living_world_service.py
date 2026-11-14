"""Authenticated player interactions with a realm's shared simulation."""

import json
from copy import deepcopy


class LivingWorldMixin:
    def _advance_world(self, now):
        if self.world_life is not None:
            for realm in range(1, self.realm_count + 1):
                self.world_life.advance(realm, now)

    def _living_view(self, player, party, now):
        from . import world

        if self.world_life is None:
            return None
        realm = self.runtime_presence.get(player["id"], {}).get("realm", 1)
        map_id = (
            None
            if party.get("transit")
            else party.get("field_map") or world.map_for_point(party["position"])
        )
        view = self.world_life.view(realm, now, map_id)
        view["local_town"] = (
            map_id if map_id in self.world_life.simulation.catalog["towns"] else None
        )
        view["can_trade"] = (
            view["merchant"].get("town") == map_id and map_id is not None
        )
        if view["can_trade"] and party.get("field_map"):
            position = party["battle"]["players"][player["id"]]["position"]
            anchor = self.world_life.simulation.catalog["maps"][map_id]["route"][0]
            view["can_trade"] = (
                sum((a - b) ** 2 for a, b in zip(position, anchor, strict=True)) <= 4
            )
        return view

    def _execute_living_world(self, player, action, params, now, compact):
        from . import economy, mob_rules, world
        from .service import GameError

        if self.world_life is None:
            raise GameError("world_disabled", "Le monde vivant n'est pas activé.", 409)
        session = self._session(player, params["session_id"])
        if params["revision"] > session["revision"]:
            raise GameError("stale_revision", "État du personnage à actualiser.", 409)
        row = self.db.execute(
            "SELECT data FROM tutorials WHERE session_id=?", (session["id"],)
        ).fetchone()
        if row is None:
            raise GameError("not_tutorial", "Commencez votre aventure.", 409)
        party = json.loads(row[0])
        if party.get("transit") or any(
            mob_rules.is_hostile(mob) for mob in party.get("mobs", [])
        ):
            raise GameError(
                "world_busy", "Terminez le trajet ou le combat avant cette action.", 409
            )
        realm = self.runtime_presence.get(player["id"], {}).get("realm", 1)
        life = self.world_life
        state = deepcopy(life.advance(realm, now))
        if life.simulation.catching_up(state, now * life.speed):
            raise GameError(
                "world_catching_up",
                "Les nouvelles du monde sont en cours de mise à jour.",
                503,
            )
        map_id = party.get("field_map") or world.map_for_point(party["position"])
        economy.migrate(party)
        if action == "world_help":
            message = self._help_town(state, map_id, party, player["id"], params)
        else:
            message = self._buy_caravan(state, map_id, party, player["id"], params, now)
        # Gold-only contributions must checkpoint the adventure in the same
        # fenced batch as the shared city's new state.
        party["autosave_checkpoint"] = party.get("autosave_checkpoint", 0) + 1
        life.save(realm, state)
        self.db.execute(
            "UPDATE tutorials SET data=? WHERE session_id=?",
            (json.dumps(party), session["id"]),
        )
        self.db.execute(
            "UPDATE sessions SET revision=revision+1 WHERE id=?", (session["id"],)
        )
        self._event(session["id"], now, message)
        return {
            "session": self._snapshot(
                player, self._session(player, session["id"]), now, compact=compact
            )
        }

    def _help_town(self, state, map_id, party, player_id, params):
        from .service import GameError

        town_id, kind = params["town"], params["kind"]
        if (
            not isinstance(town_id, str)
            or town_id not in state["towns"]
            or kind not in ("defend", "rebuild", "supply")
        ):
            raise GameError("invalid_world_action", "Aide à la ville invalide.")
        if map_id != town_id:
            raise GameError(
                "world_too_far", "Rejoignez la ville pour lui apporter votre aide.", 409
            )
        town = state["towns"][town_id]
        if party["gold"][player_id] < 10:
            raise GameError("missing_gold", "Cette aide coûte 10 or.", 409)
        if kind == "defend":
            if not town["raid"] or town["raid"]["support"] >= 100:
                raise GameError(
                    "no_raid", "Aucune défense supplémentaire n'est nécessaire.", 409
                )
            town["raid"]["support"] += 5
        elif kind == "rebuild":
            if town["raid"] or town["integrity"] >= 100:
                raise GameError(
                    "no_repair",
                    "La ville ne peut pas être reconstruite maintenant.",
                    409,
                )
            if town["wood"] < 2 or town["stone"] < 1:
                raise GameError(
                    "missing_resources", "La ville manque de bois ou de pierre.", 409
                )
            town["wood"] -= 2
            town["stone"] -= 1
            town["integrity"] = min(100, town["integrity"] + 5)
        else:
            if town["food"] >= 500 and town["wood"] >= 500:
                raise GameError(
                    "town_supplied", "Les réserves de la ville sont pleines.", 409
                )
            town["food"] = min(500, town["food"] + 5)
            town["wood"] = min(500, town["wood"] + 3)
        party["gold"][player_id] -= 10
        name = self.world_life.simulation.catalog["towns"][town_id]["name"]
        return f"Votre aide à {name} a été prise en compte (10 or)."

    def _buy_caravan(self, state, map_id, party, player_id, params, now):
        from .service import GameError

        item, quantity, quoted = (
            params["item"],
            params["quantity"],
            params["unit_price"],
        )
        if (
            not isinstance(item, str)
            or type(quantity) is not int
            or not 1 <= quantity <= 10
            or type(quoted) is not int
            or quoted < 1
        ):
            raise GameError("invalid_world_trade", "Achat à la caravane invalide.")
        merchant = state["merchant"]
        if (
            not merchant
            or merchant["phase"] != "stationed"
            or merchant["town"] != map_id
        ):
            raise GameError(
                "merchant_absent",
                "La caravane n'est pas présente dans cette ville.",
                409,
            )
        if party.get("field_map"):
            position = party["battle"]["players"][player_id]["position"]
            anchor = self.world_life.simulation.catalog["maps"][map_id]["route"][0]
            if sum((a - b) ** 2 for a, b in zip(position, anchor, strict=True)) > 4:
                raise GameError(
                    "world_too_far",
                    "Approchez-vous de la caravane pour commercer.",
                    409,
                )
        offers = self.world_life.simulation.view(state, now * self.world_life.speed)[
            "merchant"
        ]["stock"]
        offer = next((value for value in offers if value["id"] == item), None)
        if not offer or offer["quantity"] < quantity:
            raise GameError(
                "merchant_stock", "Le stock de la caravane est insuffisant.", 409
            )
        if quoted != offer["unit_price"]:
            raise GameError(
                "world_price_changed",
                "Le prix a changé ; consultez la caravane à nouveau.",
                409,
            )
        total = quoted * quantity
        if party["gold"][player_id] < total:
            raise GameError("missing_gold", "Or insuffisant.", 409)
        party["gold"][player_id] -= total
        inventory = party["inventory"][player_id]
        inventory[item] = inventory.get(item, 0) + quantity
        merchant["stock"][item] -= quantity
        merchant["gold"] += total
        return f"Caravane : achat de {quantity} {offer['name']} pour {total} or."
