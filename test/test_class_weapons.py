from copy import deepcopy
from pathlib import Path

import pytest

from jeuxRPG.multiplayer import forge, tutorial
from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.service import GameError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def weapon_catalogue(monkeypatch):
    project = Project(ROOT / "projects/authored")
    monkeypatch.setattr(forge, "GAMEPLAY", project.content["gameplay"])
    monkeypatch.setattr(forge, "RECIPES", project.content["gameplay"]["recipes"])
    monkeypatch.setattr(forge, "rosee_unlocked", lambda *args: True)
    return project


def party_for(class_name):
    party = tutorial.new_party(
        [{"id": "p", "name": "Artisan", "class_name": class_name}]
    )
    party.update(position="forge", battle=None, transit=None)
    party["inventory"]["p"] = {
        material: 100
        for recipe in forge.RECIPES.values()
        for material in recipe["cost"]
    }
    return party


@pytest.mark.parametrize(
    "class_name,recipe",
    [
        ("Knight", "epee_lisiere"),
        ("Archer", "arc_ronces"),
        *[
            (name, recipe)
            for name in ("Mage", "Priest", "Necromancien")
            for recipe in ("baton_lucioles", "sceptre_veille")
        ],
    ],
)
def test_each_class_can_craft_upgrade_store_and_equip_its_weapon(
    weapon_catalogue, class_name, recipe
):
    party = party_for(class_name)
    base = deepcopy(party["characters"]["p"]["stats"])
    inventory = deepcopy(party["inventory"]["p"])
    forge.execute(party, "p", "craft", recipe, GameError)
    item = party["equipment"]["p"]["weapon"]
    assert item["recipe"] == recipe and class_name in item["classes"]
    for stat in forge.BONUS_STATS:
        assert (
            party["characters"]["p"]["stats"][stat]["max"]
            == base[stat]["max"] + item[stat]
        )
    for material, amount in forge.RECIPES[recipe]["cost"].items():
        assert party["inventory"]["p"][material] == inventory[material] - amount
    forge.change_equipment(party, "p", "unequip", recipe, GameError)
    assert party["characters"]["p"]["stats"] == base
    forge.execute(party, "p", "upgrade", recipe, GameError)
    assert party["characters"]["p"]["stats"] == base
    forge.change_equipment(party, "p", "equip", recipe, GameError)
    assert party["equipment"]["p"]["weapon"]["level"] == 1
    assert next(row for row in forge.catalogue(party, "p") if row["recipe"] == recipe)[
        "compatible"
    ]


@pytest.mark.parametrize(
    "class_name,recipe",
    [
        ("Knight", "baton_lucioles"),
        ("Mage", "epee_lisiere"),
        ("Archer", "sceptre_veille"),
        ("Priest", "arc_ronces"),
        ("Necromancien", "arc_ronces"),
    ],
)
def test_incompatible_class_cannot_spend_materials_or_apply_weapon_bonuses(
    weapon_catalogue, class_name, recipe
):
    party = party_for(class_name)
    before = deepcopy(party)
    with pytest.raises(GameError) as refused:
        forge.execute(party, "p", "craft", recipe, GameError)
    assert refused.value.code == "incompatible_class"
    assert party == before
    party.setdefault("stored_equipment", {})["p"] = {recipe: forge.piece(recipe, 2)}
    before = deepcopy(party)
    with pytest.raises(GameError) as refused:
        forge.change_equipment(party, "p", "equip", recipe, GameError)
    assert refused.value.code == "incompatible_class"
    assert party == before
    row = next(row for row in forge.catalogue(party, "p") if row["recipe"] == recipe)
    assert not row["compatible"] and row["class_names"] and row["compatibility_reason"]


def test_builder_compatibility_changes_store_an_invalid_weapon_once_without_losing_it(
    weapon_catalogue, monkeypatch
):
    party = party_for("Knight")
    base = deepcopy(party["characters"]["p"]["stats"])
    forge.execute(party, "p", "craft", "epee_lisiere", GameError)
    recipes = deepcopy(forge.RECIPES)
    recipes["epee_lisiere"]["classes"] = ["Mage"]
    monkeypatch.setattr(forge, "RECIPES", recipes)
    forge.migrate(party)
    assert "weapon" not in party["equipment"]["p"]
    assert party["stored_equipment"]["p"]["epee_lisiere"]["level"] == 0
    assert party["characters"]["p"]["stats"] == base
    before = deepcopy(party)
    forge.migrate(party)
    assert party == before


@pytest.mark.parametrize(
    "update",
    [
        {"classes": []},
        {"classes": ["Knight", "Knight"]},
        {"classes": ["UnknownClass"]},
        {"weapon_type": "unknown"},
        {"slot": "torso"},
    ],
)
def test_builder_rejects_invalid_weapon_classes_and_types(weapon_catalogue, update):
    content = deepcopy(weapon_catalogue.content)
    content["gameplay"]["recipes"]["epee_lisiere"].update(update)
    from jeuxRPG.multiplayer.content import validate_content

    with pytest.raises(ValueError):
        validate_content(content)


def test_catalogue_is_exported_and_every_playable_class_has_a_weapon(weapon_catalogue):
    shipped = Project(ROOT / "jeuxRPG/maps")
    assert shipped.content == weapon_catalogue.content
    recipes = weapon_catalogue.content["gameplay"]["recipes"]
    weapons = [r for r in recipes.values() if r["slot"] == "weapon"]
    assert len(weapons) >= 4
    assert {"Knight", "Archer", "Mage", "Priest", "Necromancien"} <= {
        name for r in weapons for name in r["classes"]
    }
    assert any(len(r["classes"]) >= 3 for r in weapons)
