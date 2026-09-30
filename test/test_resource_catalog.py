import json
from pathlib import Path

import pytest

from jeuxRPG.adventure import Adventure
from jeuxRPG.adventure.catalog import default_catalog, load_catalog
from jeuxRPG.adventure.equipment import Gear, Inventory, material_name, parse_recipe


def extra_resources():
    return {
        "slots": {"shoulders": "Épaulières"},
        "creatures": {"Spider": {"name": "araignée", "character_class": "Goblin", "drops": [{"material": "Spider:silk", "minimum": 2, "maximum": 2}]}},
        "materials": {"Spider:silk": {"name": "Soie d'araignée"}},
        "equipment": {"Spider:shoulders": {"name": "Épaulières de soie", "family": "Spider", "slot": "shoulders", "bonuses": {"HP": 8, "Force": 2}}},
        "recipes": {"Spider:shoulders": {"equipment": "Spider:shoulders", "ingredients": {"Spider:silk": 2}}},
        "sets": {"silk": {"name": "Panoplie de soie", "equipment": ["Spider:shoulders"], "bonuses": {"Endurance": 3}}},
    }


def catalog_directory(tmp_path):
    directory = tmp_path / "resources"
    directory.mkdir()
    (directory / "00-core.json").write_text(default_catalog().model_dump_json(), encoding="utf-8")
    (directory / "10-spider.json").write_text(json.dumps(extra_resources(), ensure_ascii=False), encoding="utf-8")
    return directory


def test_new_creature_material_slot_set_and_recipe_without_engine_changes(tmp_path, monkeypatch):
    directory = catalog_directory(tmp_path)
    session = Adventure(tmp_path / "player.json", resources=directory)
    monkeypatch.setattr(session.rng, "choice", lambda sequence: "Spider")
    result = session.encounter(auto_craft=True)
    assert result["enemy"] == "Spider"
    assert result["outcome"] == "victory"
    assert result["loot"]["materials"] == {"Spider:1:silk": 2}
    assert len(result["crafted"]) == 1
    identifier = result["crafted"][0]
    assert session.inventory.equipped["shoulders"] == identifier
    assert session.inventory.items[identifier].name == "Épaulières de soie (rang 1)"
    assert session.inventory.bonuses() == {"HP": 8, "Force": 2, "Endurance": 3}
    restored = Adventure(session.path, resources=directory)
    assert restored.status() == session.status()
    assert restored.inventory.model_dump() == session.inventory.model_dump()
    assert restored.inventory.items[identifier].name == session.inventory.items[identifier].name
    restored.unequip("shoulders")
    assert restored.inventory.bonuses() == {}
    assert default_catalog().slots.get("shoulders") is None


def test_catalog_changes_control_costs_bonuses_and_drops(tmp_path):
    data = default_catalog().model_dump()
    data["equipment"]["Goblin:helmet"]["bonuses"] = {"HP": 13}
    data["recipes"]["Goblin:helmet"]["ingredients"] = {"Goblin:hide": 5}
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    catalog = load_catalog(path)
    gear = parse_recipe("Goblin:2:helmet", catalog)
    assert gear.bonuses == {"HP": 26}
    assert gear.ingredients == {"Goblin:2:hide": 5}
    inventory = Inventory.for_catalog(catalog)
    inventory.add_materials({"Goblin:2:hide": 5})
    item = inventory.craft(gear.recipe_id)
    inventory.equip(item)
    assert inventory.bonuses() == {"HP": 26}
    assert material_name("Goblin:2:hide", catalog) == "cuir de gobelin (rang 2)"


@pytest.mark.parametrize("modify", [
    lambda data: data["recipes"]["Goblin:helmet"].update(equipment="missing"),
    lambda data: data["recipes"]["Goblin:helmet"].update(ingredients={"missing:hide": 2}),
    lambda data: data["recipes"]["Goblin:helmet"].update(ingredients={"Goblin:hide": -1}),
    lambda data: data["creatures"]["Goblin"].update(character_class="Missing"),
    lambda data: data["creatures"]["Goblin"].update(character_class="Knight"),
    lambda data: data["creatures"]["Goblin"].update(module="os"),
    lambda data: data["creatures"]["Goblin"].update(module="jeuxRPG.nonexistent"),
    lambda data: data["creatures"]["Goblin"]["drops"][0].update(minimum=5, maximum=2),
    lambda data: data["creatures"]["Goblin"]["drops"][0].update(material="missing:hide"),
    lambda data: data["equipment"]["Goblin:helmet"].update(slot="missing"),
    lambda data: data["equipment"]["Goblin:helmet"].update(bonuses={"Unknown": 1}),
    lambda data: data["sets"]["Goblin"].update(equipment=["missing"]),
    lambda data: data["sets"]["Goblin"].update(equipment=["Goblin:helmet", "Orc:helmet"]),
    lambda data: data["materials"].update(invalid={"name": "invalid"}),
    lambda data: data["rules"].update(fallback_skill="missing"),
    lambda data: data.update(version=2),
])
def test_invalid_catalog_rejected_before_save_mutation(tmp_path, modify):
    save = tmp_path / "player.json"
    session = Adventure(save)
    session.save()
    before = save.read_bytes()
    data = default_catalog().model_dump()
    modify(data)
    resource = tmp_path / "invalid.json"
    resource.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        Adventure(save, resources=resource)
    assert save.read_bytes() == before


def test_duplicate_and_empty_catalog_directory_rejected(tmp_path):
    directory = tmp_path / "empty"
    directory.mkdir()
    with pytest.raises(ValueError):
        load_catalog(directory)
    directory = catalog_directory(tmp_path)
    (directory / "20-duplicate.json").write_text(json.dumps(extra_resources()))
    with pytest.raises(ValueError, match="dupliquées"):
        load_catalog(directory)


def test_legacy_save_loads_with_predefined_resources(tmp_path):
    session = Adventure(tmp_path / "player.json")
    session.inventory.add_loot("Goblin", 1, 2, 1)
    item = session.craft("Goblin:1:helmet")
    session.equip(item)
    data = json.loads(session.path.read_text())
    assert data["version"] == 1
    assert data["inventory"]["items"][item] == {"family": "Goblin", "tier": 1, "slot": "helmet"}
    assert Adventure(session.path).status() == session.status()


def test_missing_equipment_definition_in_save_is_not_recreated(tmp_path):
    session = Adventure(tmp_path / "player.json")
    session.inventory.add_loot("Goblin", 1, 2, 1)
    session.craft("Goblin:1:helmet")
    data = default_catalog().model_dump()
    data["equipment"].pop("Goblin:helmet")
    data["recipes"].pop("Goblin:helmet")
    data["sets"].pop("Goblin")
    path = tmp_path / "reduced.json"
    path.write_text(json.dumps(data))
    before = session.path.read_bytes()
    with pytest.raises(ValueError):
        Adventure(session.path, resources=path)
    assert session.path.read_bytes() == before


def test_registered_creature_and_player_modules_loaded_from_resources(tmp_path, monkeypatch):
    import jeuxRPG._class.sub_character as package
    from jeuxRPG._class.character import CharacterMeta
    directory = catalog_directory(tmp_path)
    module_name = "jeuxRPG._class.sub_character.resource_catalog_test"
    module = tmp_path / "resource_catalog_test.py"
    module.write_text("from jeuxRPG._class.sub_character.goblin import Goblin\nfrom jeuxRPG._class.sub_character.knight import Knight\n\nclass CatalogBeast(Goblin):\n    pass\n\nclass CatalogHero(Knight):\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(package, "__path__", [*package.__path__, str(tmp_path)])
    extension = {"character_modules": [module_name], "creatures": {"Beast": {"name": "Bête", "character_class": "CatalogBeast", "module": module_name, "drops": [{"material": "Goblin:hide", "minimum": 1, "maximum": 1}]}}}
    (directory / "20-beast.json").write_text(json.dumps(extension), encoding="utf-8")
    try:
        session = Adventure(tmp_path / "player.json", class_name="CatalogHero", resources=directory)
        assert session.player.char_class == "CatalogHero"
        assert type(session.create_enemy("Beast", 1)).__name__ == "CatalogBeast"
        session.save()
        assert Adventure(session.path, resources=directory).player.char_class == "CatalogHero"
    finally:
        CharacterMeta._classes.pop("catalogbeast", None)
        CharacterMeta._classes.pop("cataloghero", None)


@pytest.mark.parametrize("data", [[], {"materials": []}, {"character_modules": "module"}])
def test_wrong_catalog_shapes_are_explained(tmp_path, data):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_catalog(path)


def test_extra_slot_does_not_disable_existing_set_bonus(tmp_path):
    catalog = load_catalog(catalog_directory(tmp_path))
    inventory = Inventory.for_catalog(catalog)
    inventory.add_loot("Goblin", 1, 7, 3)
    for slot in ("helmet", "chest", "boots"):
        inventory.equip(inventory.craft(f"Goblin:1:{slot}"))
    before = inventory.bonuses()
    inventory.add_materials({"Spider:1:silk": 2})
    inventory.equip(inventory.craft("Spider:1:shoulders"))
    assert inventory.bonuses()["HP"] == before["HP"] + 8
    assert inventory.bonuses()["Endurance"] == before["Endurance"] + 3
