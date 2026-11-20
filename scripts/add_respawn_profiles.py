"""Install editable respawn presets without changing species or spawn counts."""

from copy import deepcopy

from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.mob_rules import resolve
from jeuxRPG.multiplayer.spawn_cycles import PRESETS


def author(project):
    project.content["gameplay"]["respawn_profiles"] = deepcopy(PRESETS)
    for data in project.maps.values():
        for config in data.get("spawners", []):
            mob = resolve(project.mobs, config["mob_id"])
            kind = (
                "boss"
                if "boss" in config["mob_id"] or mob.get("xp_class") == "boss"
                else "elite"
                if mob.get("xp_class") == "elite"
                else "archer"
                if "archer" in config["mob_id"]
                else "mage"
                if "mage" in config["mob_id"]
                else "civilian"
                if mob.get("hostile") is False
                else "default"
            )
            config.setdefault("respawn_profile", kind)
    project.validate()


if __name__ == "__main__":
    project = Project("projects/authored")
    author(project)
    project.save()
