import json
import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path

from jeuxRPG.catalog_paths import CATALOG_NAMES

from .content import load_content, validate_content
from .map_assets import load, validate
from .mob_rules import validate_mobs


class Project:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        from .project_storage import project_lock, recover_project

        with project_lock(self.directory):
            recover_project(self.directory)
        packaged = Path(__file__).resolve().parents[1] / "maps"
        for source in packaged.glob("*.json"):
            target = self.directory / source.name
            if not target.exists():
                shutil.copyfile(source, target)
        original_disk = self.disk_state()
        self.content = load_content(self.directory / "content.json")
        self.mobs = validate_mobs(
            json.loads((self.directory / "mobs.json").read_text(encoding="utf-8"))[
                "maps"
            ],
            classes=[
                item["id"]
                for item in self.content["templates"]["classes"]
                if item["class_type"] != "INVOCATION"
            ],
            xp_classes=self.content["gameplay"]["xp_classes"],
        )
        from .gameplay_catalog import material_ids

        for item in material_ids(self.mobs):
            self.content["gameplay"]["materials"].setdefault(
                item, {"name": item.replace("_", " "), "rare_chance": 0.0}
            )
        from . import map_building

        previous = map_building.MOBS
        try:
            map_building.MOBS = self.mobs
            self.maps = load(self.directory / "world.json")
        finally:
            map_building.MOBS = previous
        from .map_assets import read_catalog

        self.encounters = read_catalog("encounters", self.directory)
        self.migrate_classes()
        self.validate()
        self.snapshot = self.state()
        self.disk_snapshot = self.disk_state()
        if original_disk != self.disk_snapshot:
            raise ValueError("Le projet a changé pendant son ouverture. Rechargez-le.")

    def migrate_classes(self):
        definitions = self.content.get("classes", [])
        if not definitions:
            return
        from jeuxRPG._class.character import Character, CharacterMeta
        from jeuxRPG._class.res.character.class_models import model_from_actor

        from .skill_catalog import install
        from .tutorial import blueprint

        old = CharacterMeta._classes.copy()
        try:
            install(self.content, self.mobs)
            for definition in definitions:
                actor = Character.create(
                    definition["id"], "migration", definition["name"]
                )
                model = model_from_actor(
                    actor,
                    definition["id"],
                    definition["name"],
                    self.content["templates"],
                )
                model["formulas"] = deepcopy(definition.get("stats", {}))
                if definition.get("previous_ids"):
                    model["previous_ids"] = deepcopy(definition["previous_ids"])
                self.content["templates"]["classes"].append(model)
            self.content["classes"] = []
        finally:
            CharacterMeta._classes.clear()
            CharacterMeta._classes.update(old)
            blueprint.cache_clear()

    def state(self):
        return deepcopy((self.maps, self.mobs, self.content, self.encounters))

    def restore(self, state):
        self.maps, self.mobs, self.content, self.encounters = deepcopy(state)

    def document(self):
        return {
            "maps": deepcopy(self.maps),
            "encounters": deepcopy(self.encounters),
            "mobs": deepcopy(self.mobs),
            "content": deepcopy(self.content),
        }

    def replace_document(self, document):
        roots = {"maps", "encounters", "mobs", "content"}
        if not isinstance(document, dict) or set(document) != roots:
            raise ValueError(
                "Le projet complet doit contenir exactement maps, encounters, mobs et content."
            )
        if not all(isinstance(document[key], dict) for key in roots):
            raise ValueError("Les racines du projet doivent être des objets JSON.")
        before = self.state()
        try:
            self.maps = deepcopy(document["maps"])
            self.encounters = deepcopy(document["encounters"])
            self.mobs = deepcopy(document["mobs"])
            self.content = deepcopy(document["content"])
            self.validate()
        except Exception:
            self.maps, self.mobs, self.content, self.encounters = before
            raise
        return self.document()

    def validate_encounters(self):
        import re

        from . import tactics

        if (
            not isinstance(self.encounters, dict)
            or not self.encounters
            or len(self.encounters) > 100
        ):
            raise ValueError(
                "Le catalogue de rencontres doit contenir de 1 à 100 terrains."
            )
        required = {
            "clearing_1",
            "clearing_2",
            "clearing_3",
            "lisiere_1",
            "lisiere_2",
            "lisiere_3",
            "road_1",
            "road_2",
            "road_3",
            "rosee_1",
            "rosee_2",
            "rosee_3",
            "brume_1",
            "brume_2",
            "brume_3",
        }
        if not required <= self.encounters.keys():
            raise ValueError(
                "Les quinze terrains de rencontre de base doivent être conservés."
            )
        for identifier, definition in self.encounters.items():
            if (
                not isinstance(identifier, str)
                or not re.fullmatch(r"[a-z0-9_]{1,64}", identifier)
                or not isinstance(definition, dict)
            ):
                raise ValueError("Terrain de rencontre invalide.")
            width, height = definition.get("width"), definition.get("height")
            if (
                type(width) is not int
                or type(height) is not int
                or not 4 <= width <= 128
                or not 4 <= height <= 128
            ):
                raise ValueError(f"{identifier} : dimensions invalides.")
            if (
                definition.get("id") != identifier
                or not isinstance(definition.get("name"), str)
                or not definition["name"]
            ):
                raise ValueError(f"{identifier} : identifiant interne ou nom invalide.")

            def point(value, width=width, height=height):
                return (
                    isinstance(value, list)
                    and len(value) == 2
                    and all(type(n) is int for n in value)
                    and 0 <= value[0] < width
                    and 0 <= value[1] < height
                )

            for field in ("cover", "blocked", "water", "bridges", "paths"):
                values = definition.get(field, [])
                if not isinstance(values, list) or any(
                    not point(value) for value in values
                ):
                    raise ValueError(f"{identifier} : {field} invalide.")
            for item in definition.get("decorations", []):
                if not isinstance(item, dict) or not point(item.get("position")):
                    raise ValueError(f"{identifier} : décoration invalide.")
            route = tactics.patrol_route(definition, 0)
            if (
                len(route) < 2
                or any(not tactics.walkable(definition, value) for value in route)
                or any(
                    tactics.path(definition, a, b) is None
                    for a, b in zip(route, route[1:] + route[:1], strict=True)
                )
            ):
                raise ValueError(f"{identifier} : terrain non parcourable.")
        return True

    def validate(self):
        before = self.state()
        try:
            return self._validate()
        except Exception:
            self.restore(before)
            raise

    def _validate(self):
        validate_mobs(
            self.mobs,
            classes=[
                item["id"]
                for item in self.content["templates"]["classes"]
                if item["class_type"] != "INVOCATION"
            ],
            xp_classes=self.content["gameplay"]["xp_classes"],
        )
        from jeuxRPG._class.res.character.class_models import skill_to_data

        from .skill_catalog import library, make_skill

        available = library(self.content, self.mobs)
        definitions = self.content["templates"]["skills"]
        for identifier in list(definitions):
            if identifier.startswith(("skill:", "mob:")):
                if identifier not in available:
                    if any(
                        entry["skill_id"] == identifier
                        for model in self.content["templates"]["classes"]
                        for entry in model["skills"]
                    ):
                        raise ValueError(
                            "Compétence référencée introuvable : " + identifier
                        )
                    del definitions[identifier]
                else:
                    definitions[identifier] = skill_to_data(
                        make_skill(available[identifier], {})
                    )
        self.content["gameplay"] = validate_content(self.content)["gameplay"]
        from .gameplay_catalog import (
            validate_references as validate_gameplay_references,
        )

        validate_gameplay_references(
            self.content["gameplay"], self.mobs, self.content["templates"]
        )
        self.validate_encounters()
        from .skill_catalog import validate as validate_catalog

        validate_catalog(self.content, self.mobs)
        from . import map_building

        previous = map_building.MOBS
        try:
            map_building.MOBS = self.mobs
            validate(self.maps)
        finally:
            map_building.MOBS = previous
        npcs = {
            site["id"] for data in self.maps.values() for site in data.get("sites", [])
        }
        from .gameplay_catalog import validate_start

        validate_start(self.content["gameplay"], self.maps)
        for quest in self.content["quests"]:
            if (
                quest["npc"] not in npcs
                or quest.get("zone")
                and quest["zone"] not in self.maps
                or quest["kind"] == "kill"
                and quest["target"] not in self.mobs
                or quest["kind"] == "craft"
                and quest["target"] not in self.content["gameplay"]["recipes"]
            ):
                raise ValueError(f"{quest['name']} : PNJ, zone ou cible introuvable.")
        from .content import validate_references

        validate_references(self.content, self.mobs, self.maps)
        from .map_playability import validate as validate_playability

        validate_playability(self.maps)
        return True

    def rename(self, section, identifier, replacement):
        import re

        if not isinstance(replacement, str) or not re.fullmatch(
            r"[a-zA-Z0-9_]{1,64}" if section == "classes" else r"[a-z0-9_]{1,64}",
            replacement,
        ):
            raise ValueError(
                "Identifiant : 1–64 lettres minuscules, chiffres ou underscores (ex. mira_hunt_2)."
            )
        if identifier == replacement:
            return
        before = self.state()
        try:
            if section == "classes" and any(
                item["id"] == identifier
                for item in self.content["templates"]["classes"]
            ):
                self._rename_class_model(identifier, replacement, section)
            elif section == "skill_models":
                self._rename_skill_model(identifier, replacement, section)
            elif section in ("classes", "skills"):
                self._rename_class_or_skill(identifier, replacement, section)
            elif section == "endgame":
                self._rename_contract(identifier, replacement, section)
            elif section in ("quests", "achievements"):
                self._rename_quest_or_achievement(identifier, replacement, section)
            elif section == "mobs":
                self._rename_mob(identifier, replacement, section)
            elif section == "npcs":
                self._rename_npc(identifier, replacement, section)
            elif section == "maps":
                self._rename_map(identifier, replacement, section)
            else:
                self._rename_unsupported(identifier, replacement, section)
            self.validate()
        except Exception:
            self.maps, self.mobs, self.content, self.encounters = before
            raise

    def _rename_class_model(self, identifier, replacement, section):
        item = next(
            item
            for item in self.content["templates"]["classes"]
            if item["id"] == identifier
        )
        item["id"] = replacement
        item["previous_ids"] = list(
            dict.fromkeys([*item.get("previous_ids", []), identifier])
        )
        controls = self.content["gameplay"]["summon_control"]
        if identifier in controls:
            controls[replacement] = controls.pop(identifier)
        for definition in self.content["templates"]["skills"].values():
            for effect in definition["effects"].values():
                if (
                    effect.get("invocation", {})
                    and effect["invocation"].get("class") == identifier
                ):
                    effect["invocation"]["class"] = replacement
        for species in self.mobs.values():
            if species["class_name"] == identifier:
                species["class_name"] = replacement
        for definition in self.content.get("classes", []):
            if definition["base_class"] == identifier:
                definition["base_class"] = replacement

    def _rename_skill_model(self, identifier, replacement, section):
        if replacement in self.content["templates"]["skills"]:
            raise ValueError("Identifiant déjà utilisé.")
        self.content["templates"]["skills"][replacement] = self.content["templates"][
            "skills"
        ].pop(identifier)
        for model in self.content["templates"]["classes"]:
            for entry in model["skills"]:
                if entry["skill_id"] == identifier:
                    entry["skill_id"] = replacement
        for mob in self.mobs.values():
            for entry in mob.get("abilities", []):
                if entry.get("skill_id") == identifier:
                    entry["skill_id"] = replacement

    def _rename_class_or_skill(self, identifier, replacement, section):
        item = next(
            item for item in self.content.get(section, []) if item["id"] == identifier
        )
        if any(other["id"] == replacement for other in self.content[section]):
            raise ValueError("Identifiant déjà utilisé.")
        item["id"] = replacement
        if section == "classes":
            item["previous_ids"] = list(
                dict.fromkeys([*item.get("previous_ids", []), identifier])
            )
        if section == "skills":
            cached = self.content["templates"]["skills"].pop(
                "skill:" + identifier, None
            )
            if cached is not None:
                self.content["templates"]["skills"]["skill:" + replacement] = cached
            for definition in [
                *self.content.get("classes", []),
                *self.content["templates"]["classes"],
                *self.mobs.values(),
            ]:
                for assignment in definition.get(
                    "skills", definition.get("abilities", [])
                ):
                    if assignment.get("skill_id") == "skill:" + identifier:
                        assignment["skill_id"] = "skill:" + replacement

    def _rename_contract(self, identifier, replacement, section):
        item = next(
            item for item in self.content["endgame"] if item["id"] == identifier
        )
        if any(
            other["id"] == replacement
            for other in self.content["endgame"]
            if other is not item
        ):
            raise ValueError("Identifiant déjà utilisé.")
        item["previous_ids"] = list(
            dict.fromkeys([*item.get("previous_ids", []), identifier])
        )
        item["id"] = replacement

    def _rename_quest_or_achievement(self, identifier, replacement, section):
        item = next(item for item in self.content[section] if item["id"] == identifier)
        if any(
            other["id"] == replacement or replacement in other.get("previous_ids", [])
            for other in self.content[section]
            if other is not item
        ):
            raise ValueError("Identifiant déjà utilisé.")
        item["previous_ids"] = list(
            dict.fromkeys([*item.get("previous_ids", []), identifier])
        )
        item["id"] = replacement
        if section == "quests":
            for success in self.content["achievements"]:
                if (
                    success["condition"] == "quests"
                    and success.get("target") == identifier
                ):
                    success["target"] = replacement
        requirement_key = "quests" if section == "quests" else "achievements"
        for quest in self.content["quests"]:
            requirements = quest.get("requirements", {})
            if requirement_key in requirements:
                requirements[requirement_key] = [
                    replacement if value == identifier else value
                    for value in requirements[requirement_key]
                ]

    def _rename_mob(self, identifier, replacement, section):
        if identifier == "goblin":
            raise ValueError(
                "goblin est une référence interne du tutoriel ; créez une nouvelle espèce pour un autre identifiant."
            )
        if replacement in self.mobs:
            raise ValueError("Identifiant déjà utilisé.")
        self.mobs[replacement] = self.mobs.pop(identifier)
        self.mobs[replacement]["previous_ids"] = list(
            dict.fromkeys([*self.mobs[replacement].get("previous_ids", []), identifier])
        )
        for species in self.mobs.values():
            if species.get("parent") == identifier:
                species["parent"] = replacement
        for definition in [
            *self.content.get("classes", []),
            *self.content["templates"]["classes"],
            *self.mobs.values(),
        ]:
            for assignment in definition.get("skills", definition.get("abilities", [])):
                reference = assignment.get("skill_id", "")
                if reference.startswith("mob:" + identifier + ":"):
                    assignment["skill_id"] = (
                        "mob:" + replacement + reference[len("mob:" + identifier) :]
                    )
        for reference in list(self.content["templates"]["skills"]):
            if reference.startswith("mob:" + identifier + ":"):
                self.content["templates"]["skills"][
                    "mob:" + replacement + reference[len("mob:" + identifier) :]
                ] = self.content["templates"]["skills"].pop(reference)
        for success in self.content["achievements"]:
            if success.get("target") == identifier and success["condition"] not in (
                "craft",
                "quests",
            ):
                success["target"] = replacement
        for data in self.maps.values():
            for spawn in data.get("spawners", []):
                if spawn["mob_id"] == identifier:
                    spawn["mob_id"] = replacement
        for quest in self.content["quests"]:
            if quest["kind"] == "kill" and quest["target"] == identifier:
                quest["target"] = replacement
        for contract in self.content.get("endgame", []):
            if contract["kind"] == "kill" and contract["target"] == identifier:
                contract["target"] = replacement

    def _rename_npc(self, identifier, replacement, section):
        if identifier in ("mira", "forge"):
            raise ValueError("Cet identifiant est une référence interne du tutoriel.")
        if any(
            site["id"] == replacement
            for data in self.maps.values()
            for site in data["sites"]
        ):
            raise ValueError("Identifiant PNJ déjà utilisé.")
        for data in self.maps.values():
            for site in data["sites"]:
                if site["id"] == identifier:
                    site["id"] = replacement
        for quest in self.content["quests"]:
            if quest["npc"] == identifier:
                quest["npc"] = replacement

    def _rename_map(self, identifier, replacement, section):
        from .map_assembly import CORE

        if identifier in CORE:
            raise ValueError("Cette carte est une référence interne du tutoriel.")
        if replacement in self.maps:
            raise ValueError("Identifiant de carte déjà utilisé.")
        self.maps[replacement] = self.maps.pop(identifier)
        self.maps[replacement]["previous_ids"] = list(
            dict.fromkeys([*self.maps[replacement].get("previous_ids", []), identifier])
        )
        self.maps[replacement]["id"] = "field_" + replacement
        for data in self.maps.values():
            points = data.get("world_view", {}).get("points", {})
            if identifier in points:
                points[replacement] = points.pop(identifier)
            for key in ("zone_id", "world_zone", "fast_travel_origin"):
                if data.get(key) == identifier:
                    data[key] = replacement
            for gate in data["exits"]:
                for key in ("destination", "fast_destination"):
                    if gate.get(key) == identifier:
                        gate[key] = replacement
            for route in data.get("travel_routes", []):
                for key in ("from", "to"):
                    if route[key] == identifier:
                        route[key] = replacement
        for definition in [
            *self.content["quests"],
            *self.content["achievements"],
        ]:
            for field in ("zone", "map"):
                if definition.get(field) == identifier:
                    definition[field] = replacement
        for contract in self.content.get("endgame", []):
            if contract.get("zone") == identifier:
                contract["zone"] = replacement
        start = self.content["gameplay"]["rules"]["start"]
        if start["map"] == identifier:
            start["map"] = replacement

    def _rename_unsupported(self, identifier, replacement, section):
        raise ValueError(
            "Ce type de définition ne possède pas d’identifiant modifiable."
        )

    def duplicate(self, section, identifier, replacement):
        import re

        if section not in (
            "mobs",
            "quests",
            "achievements",
            "endgame",
            "classes",
            "skills",
            "skill_models",
        ):
            raise ValueError("Ce catalogue se duplique depuis son éditeur spécialisé.")
        if not isinstance(replacement, str) or not re.fullmatch(
            r"[a-zA-Z0-9_]{1,64}" if section == "classes" else r"[a-z0-9_]{1,64}",
            replacement,
        ):
            raise ValueError(
                "Identifiant : lettres minuscules, chiffres et underscores."
            )
        before = self.state()
        try:
            if section == "skill_models":
                key = "ability:" + replacement
                if key in self.content["templates"]["skills"]:
                    raise ValueError("Identifiant déjà utilisé.")
                self.content["templates"]["skills"][key] = deepcopy(
                    self.content["templates"]["skills"][identifier]
                )
                self.content["templates"]["skills"][key]["name"] += " · copie"
            elif section == "mobs":
                if replacement in self.mobs:
                    raise ValueError("Identifiant déjà utilisé.")
                value = deepcopy(self.mobs[identifier])
                value["name"] += " · copie"
                value.pop("previous_ids", None)
                self.mobs[replacement] = value
            else:
                values = (
                    self.content["templates"]["classes"]
                    if section == "classes"
                    else self.content.setdefault(section, [])
                )
                if any(
                    item["id"].lower() == replacement.lower()
                    or replacement in item.get("previous_ids", [])
                    for item in values
                ):
                    raise ValueError("Identifiant déjà utilisé.")
                value = deepcopy(
                    next(item for item in values if item["id"] == identifier)
                )
                value.update(id=replacement, name=value["name"] + " · copie")
                for key in ("previous_ids", "table_id", "category", "role"):
                    value.pop(key, None)
                values.append(value)
            self.validate()
        except Exception:
            self.maps, self.mobs, self.content, self.encounters = before
            raise

    def disk_state(self):
        return {
            name: (self.directory / name).read_bytes()
            if (self.directory / name).exists()
            else None
            for name in CATALOG_NAMES
        }

    def save(self):
        from .project_storage import project_lock, recover_project

        before = self.state()
        try:
            with project_lock(self.directory):
                recover_project(self.directory)
                if self.disk_state() != self.disk_snapshot:
                    raise ValueError(
                        "Le projet a été modifié sur disque depuis son ouverture. Rechargez-le avant d’enregistrer."
                    )
                self.validate()
                self._write_catalogs()
                self.disk_snapshot = self.disk_state()
        except Exception:
            self.restore(before)
            raise
        self.snapshot = self.state()

    def _write_catalogs(self):
        from jeuxRPG.catalog_paths import catalog_limit

        payloads = {
            "world.json": self.maps,
            "encounters.json": {"kind": "encounters", "maps": self.encounters},
            "mobs.json": {"kind": "mobs", "maps": self.mobs},
            "content.json": {
                "kind": "content",
                "maps": {},
                "content": {
                    key: value
                    for key, value in self.content.items()
                    if key != "templates"
                },
            },
            "classes.json": self.content["templates"],
        }
        serialized = {
            name: (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode(
                "utf-8"
            )
            for name, value in payloads.items()
        }
        for name, value in serialized.items():
            if len(value) > catalog_limit(name):
                raise ValueError(
                    f"{name} : catalogue trop volumineux pour être rouvert ({len(value)} octets, limite {catalog_limit(name)})."
                )
        from .project_storage import (
            finish_recovery,
            prepare_recovery,
            recover_project,
            sync_directory,
        )

        originals, staged = self.disk_state(), {}
        try:
            for name, value in serialized.items():
                descriptor, path = tempfile.mkstemp(
                    prefix=name + ".", suffix=".controller.tmp", dir=self.directory
                )
                staged[name] = Path(path)
                with os.fdopen(descriptor, "wb") as output:
                    output.write(value)
                    output.flush()
                    os.fsync(output.fileno())
            prepare_recovery(self.directory, originals)
            for name, temporary in staged.items():
                os.replace(temporary, self.directory / name)
            sync_directory(self.directory)
            finish_recovery(self.directory)
        except Exception:
            recover_project(self.directory)
            raise
        finally:
            for temporary in staged.values():
                temporary.unlink(missing_ok=True)
