import json
import math

import pytest

from jeuxRPG._class.place.biome import Biome
from jeuxRPG._class.place.jobs import npc
from jeuxRPG._class.place.jobs.npc_loader import load_all_npcs
from jeuxRPG._class.place.map_hierarchy import load_map_hierarchy, get_towns_data, get_town_graph
from jeuxRPG._class.res.build.Basic_town import make_basic_town
from jeuxRPG._class.res.build.infrastructures import get_base_buildings


@pytest.mark.parametrize("biome", list(Biome))
def test_terrain_travel_rules_and_labels(biome):
    assert biome.get_name("fr")
    assert biome.get_symbol() != "?"
    assert biome.get_emoji() != "❓"
    assert biome.get_movement_cost() >= 1
    assert biome.is_passable() == math.isfinite(biome.get_movement_cost())
    assert biome.is_passable() == (biome is not Biome.OCEAN)


@pytest.mark.parametrize("factory,job", [(npc.create_blacksmith, "BLACKSMITH"), (npc.create_innkeeper, "INNKEEPER"), (npc.create_merchant, "MERCHANT"), (npc.create_priest, "PRIEST"), (npc.create_mayor, "MAYOR"), (npc.create_guard, "GUARD")])
def test_npc_services_and_quest_idempotence(factory, job):
    character = factory("Service")
    assert character.job.job_type.name == job
    assert not character.has_quests()
    character.add_quest("quest1")
    character.add_quest("quest1")
    assert character.has_quests()
    assert character.get_info()["quests_available"] == 1
    assert character.get_info()["name"] == "Service"
    assert "Service" in repr(character)
    assert job in repr(character.job)


def test_npc_loader_continues_after_corrupt_file(tmp_path, capsys):
    (tmp_path / "good.json").write_text(json.dumps({"name": "Merchant", "job": {"type": "MERCHANT"}}))
    (tmp_path / "bad.json").write_text("{")
    characters = load_all_npcs(tmp_path)
    assert [character.name for character in characters] == ["Merchant"]
    assert "bad.json" in capsys.readouterr().out
    assert load_all_npcs(tmp_path / "missing") == []


def test_map_hierarchy_and_travel_graph(tmp_path):
    towns_file = tmp_path / "towns.json"
    towns_file.write_text(json.dumps({"towns": [{"name": "A", "size": [20, 30]}, {"name": "B"}], "paths": [{"from": "A", "to": "B"}]}))
    structure = tmp_path / "structure.json"
    structure.write_text(json.dumps({"dimensions": [{"name": "World", "continents": [{"name": "Continent", "kingdoms": [{"name": "Kingdom", "towns": ["A"]}]}]}]}))
    root = load_map_hierarchy(structure, get_towns_data(towns_file))
    leaf = root.children[0].children[0].children[0]
    assert leaf.get_full_path() == ["World", "Continent", "Kingdom", "A"]
    assert leaf.size == [20, 30]
    assert "Town" in repr(leaf)
    graph = get_town_graph(str(towns_file))
    assert get_town_graph(str(towns_file)) is graph
    assert graph["A"].can_travel_to("B")


def test_basic_town_and_building_instances_are_independent():
    town = make_basic_town()
    assert len(town.districts) == 4
    first = get_base_buildings()
    second = get_base_buildings()
    assert first.keys() == second.keys()
    assert all(first[name] is not second[name] for name in first)
