import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from jeuxRPG._class.res.character.class_models import MODELS
from jeuxRPG.multiplayer import map_building, mob_rules
from jeuxRPG.multiplayer.content import DATA
from jeuxRPG.multiplayer.gameplay_catalog import DEFAULTS, validate_references

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def packaged_bestiary(monkeypatch):
    mobs = json.loads((ROOT / "jeuxRPG/maps/mobs.json").read_text())["maps"]
    monkeypatch.setattr(map_building, "MOBS", mob_rules.validate_mobs(mobs))
    monkeypatch.setitem(DATA, "gameplay", deepcopy(DEFAULTS))


def test_bestiary_covers_ten_levels_and_all_categories():
    mobs = map_building.MOBS
    added = {
        key: value
        for key, value in mobs.items()
        if key not in {"goblin", "orc", "dragon_whelp", "gobelin_boss"}
    }
    assert len(added) == 50
    assert Counter(mob["level"] for mob in added.values()) == dict.fromkeys(
        range(1, 11), 5
    )
    assert {mob["xp_class"] for mob in added.values()} == {
        "normal",
        "warrior",
        "caster",
        "elite",
        "boss",
    }
    validate_references(DATA["gameplay"], mobs, MODELS)
    owners = {}
    for key, mob in mobs.items():
        for drop in mob["drops"]:
            item = drop["item"]
            if item in {"peau", "croc"}:
                assert not drop["rare"]
                continue
            assert key in item
            assert mob["name"] in DATA["gameplay"]["materials"][item]["name"]
            assert item not in owners or owners[item] == key
            owners[item] = key
            assert DATA["gameplay"]["materials"][item]["rare_chance"] == 0


def test_packaged_and_authored_catalogs_match():
    for filename in ["mobs.json"]:
        assert json.loads((ROOT / "jeuxRPG/maps" / filename).read_text()) == json.loads(
            (ROOT / "projects/authored" / filename).read_text()
        )


def test_camp_uses_warriors_and_boss():
    world = json.loads((ROOT / "jeuxRPG/maps/world.json").read_text())
    camp = world["hunt"]["spawners"]
    chief = next(spawn for spawn in camp if spawn["name"] == "Chef Gobelin")
    guards = [spawn for spawn in camp if spawn["name"] == "Garde gobelin"]
    assert chief["mob_id"] == "gobelin_boss"
    assert map_building.MOBS[chief["mob_id"]]["xp_class"] == "boss"
    assert len(guards) == 4
    assert all(
        map_building.MOBS[spawn["mob_id"]]["xp_class"] == "warrior" for spawn in guards
    )


def test_species_level_and_spawner_override():
    maps = {"test": {"level": 4}}
    mob = map_building.create_mob(maps, "test", {"mob_id": "seigneur_gobelin"}, 0)
    assert mob["level"] == 10
    assert mob["phases"]
    low = map_building.create_mob(
        maps, "test", {"mob_id": "seigneur_gobelin", "level": 2}, 0
    )
    assert low["level"] == 2
    assert low["stats"]["hp"]["max"] < mob["stats"]["hp"]["max"]
    legacy = map_building.create_mob(maps, "test", {"mob_id": "goblin"}, 0)
    assert legacy["level"] == 4


@pytest.mark.parametrize("level", [0, 101, True, 1.5, "2"])
def test_invalid_species_level_is_rejected(level):
    mobs = deepcopy(map_building.MOBS)
    mobs["garde_gobelin"]["level"] = level
    with pytest.raises(ValueError, match="Niveau de départ"):
        mob_rules.validate_mobs(mobs)
